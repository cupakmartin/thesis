# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from app.config import Nastaveni, nastaveni
from app.jadro.atributy import Atributy, porovnej_atributy, vytez_atributy
from app.jadro.embeddingy import SpravceEmbeddingu, spravce_embeddingu
from app.jadro.index_faiss import VektorovyIndex
from app.jadro.lexikalni import podobnost_kombinovana
from app.jadro.normalizace import normalizuj_pro_embedding, normalizuj_pro_lexikalni
from app.jadro.postup import BEZ_SLEDOVANI, SledovaniPostupu
from app.jadro.typy import urci_typ

logger = logging.getLogger(__name__)

FAZE_PRIPRAVA = "priprava"
FAZE_HLEDANI = "hledani"
FAZE_DVOJICE = "dvojice"
FAZE_SHLUKOVANI = "shlukovani"
KROK_HLASENI = 2000

METODA_SEMANTICKA = "semanticka"
METODA_LEXIKALNI = "lexikalni"
METODA_HYBRIDNI = "hybridni"
METODA_PRAVIDLOVA = "pravidlova"

PRAH_PRI_DVOU_ATRIBUTECH = 0.60
PRAH_PRI_JEDNOM_ATRIBUTU = 0.75
PRAH_BEZ_ATRIBUTU = 0.88


@dataclass(frozen=True)
class ZaznamPolozky:
    itemnum: str
    popis: str
    popis_dlouhy: str = ""
    komoditni_skupina: str = ""
    vyrobce: str = ""
    iso_trida: str = ""
    model: str = ""

    def text_pro_porovnani(self) -> str:

        casti = [self.popis]
        if self.komoditni_skupina:
            casti.append(self.komoditni_skupina)
        return " | ".join(c for c in casti if c)


@dataclass(frozen=True)
class NastaveniDeduplikace:
    metoda: str = METODA_HYBRIDNI
    prah_kandidatu: float = 0.55
    prah_rozhodnuti: float = 0.72
    pocet_sousedu: int = 8
    vaha_semanticka: float = 0.50
    vaha_lexikalni: float = 0.20
    vaha_atributu: float = 0.30
    uplatnit_atributy: bool = True
    uplatnit_druh_komponenty: bool = True
    omezit_na_tridu_iso: bool = False
    prisne_shlukovani: bool = False


@dataclass(frozen=True)
class Dvojice:
    index_a: int
    index_b: int
    podobnost_semanticka: float
    podobnost_lexikalni: float
    skore_atributu: float
    skore: float
    prijata: bool
    rozpor_atributu: bool
    vysvetleni: tuple[str, ...] = field(default=())


@dataclass
class Klastr:
    id: int
    indexy: list[int]
    prumerna_podobnost: float
    minimalni_podobnost: float
    dvojice: list[Dvojice] = field(default_factory=list)

    @property
    def velikost(self) -> int:
        return len(self.indexy)


@dataclass
class VysledekDeduplikace:

    klastry: list[Klastr]
    dvojice: list[Dvojice]
    pocet_polozek: int
    doba_s: float
    nastaveni: NastaveniDeduplikace
    statistiky: dict[str, float] = field(default_factory=dict)

    @property
    def pocet_klastru(self) -> int:
        return len(self.klastry)

    @property
    def pocet_duplicitnich_zaznamu(self) -> int:
        return sum(k.velikost - 1 for k in self.klastry)

class UnionFind:

    def __init__(self, pocet: int) -> None:
        self._rodic = list(range(pocet))
        self._velikost = [1] * pocet

    def najdi(self, prvek: int) -> int:
        koren = prvek
        while self._rodic[koren] != koren:
            koren = self._rodic[koren]
        while self._rodic[prvek] != koren:
            self._rodic[prvek], prvek = koren, self._rodic[prvek]
        return koren

    def spoj(self, prvni: int, druhy: int) -> bool:
        koren_a, koren_b = self.najdi(prvni), self.najdi(druhy)
        if koren_a == koren_b:
            return False
        if self._velikost[koren_a] < self._velikost[koren_b]:
            koren_a, koren_b = koren_b, koren_a
        self._rodic[koren_b] = koren_a
        self._velikost[koren_a] += self._velikost[koren_b]
        return True

    def skupiny(self) -> dict[int, list[int]]:
        vysledek: dict[int, list[int]] = {}
        for prvek in range(len(self._rodic)):
            vysledek.setdefault(self.najdi(prvek), []).append(prvek)
        return vysledek


def _rozloz_na_uplne_skupiny(
    komponenta: list[int],
    prijate_dvojice: dict[tuple[int, int], "Dvojice"],
) -> list[list[int]]:
    if len(komponenta) < 3:
        return [komponenta]

    sousede: dict[int, set[int]] = {prvek: set() for prvek in komponenta}
    hrany: list[tuple[float, int, int]] = []
    for (a, b), dvojice in prijate_dvojice.items():
        if a in sousede and b in sousede:
            sousede[a].add(b)
            sousede[b].add(a)
            hrany.append((dvojice.skore, a, b))

    hrany.sort(key=lambda h: -h[0])

    skupiny: list[list[int]] = []
    zarazeno: set[int] = set()

    for _, a, b in hrany:
        if a in zarazeno or b in zarazeno:
            continue
        skupiny.append([a, b])
        zarazeno.update((a, b))

    for prvek in sorted(set(komponenta) - zarazeno):
        for skupina in skupiny:
            if all(clen in sousede[prvek] for clen in skupina):
                skupina.append(prvek)
                zarazeno.add(prvek)
                break

    return [sorted(s) for s in skupiny if len(s) >= 2]

def _vyhodnot_dvojici(
    index_a: int,
    index_b: int,
    podobnost: float,
    texty_lexikalni: Sequence[str],
    atributy: Sequence[Atributy],
    zaznamy: Sequence[ZaznamPolozky],
    konfigurace: NastaveniDeduplikace,
    druhy: Sequence[str | None] | None = None,
) -> Dvojice:
    lexikalni = podobnost_kombinovana(texty_lexikalni[index_a], texty_lexikalni[index_b])

    rozpor = False
    skore_atributu = 0.5
    vysvetleni: tuple[str, ...] = ()

    if konfigurace.uplatnit_atributy:
        porovnani = porovnej_atributy(atributy[index_a], atributy[index_b])
        rozpor = porovnani.rozpor
        skore_atributu = porovnani.skore
        vysvetleni = porovnani.vysvetleni

    if konfigurace.uplatnit_druh_komponenty and druhy is not None:
        druh_a, druh_b = druhy[index_a], druhy[index_b]
        if druh_a and druh_b and druh_a != druh_b:
            rozpor = True
            vysvetleni = vysvetleni + (
                f"druh komponenty: {druh_a} proti {druh_b}",
            )

    if konfigurace.omezit_na_tridu_iso:
        trida_a, trida_b = zaznamy[index_a].iso_trida, zaznamy[index_b].iso_trida
        if trida_a and trida_b and trida_a != trida_b:
            rozpor = True
            vysvetleni = vysvetleni + (f"třída ISO 14224: {trida_a} proti {trida_b}",)

    if konfigurace.metoda == METODA_SEMANTICKA:
        skore = podobnost
        prijata = skore >= konfigurace.prah_rozhodnuti
        return Dvojice(index_a, index_b, podobnost, lexikalni, skore_atributu,
                       skore, prijata, False, ())

    if konfigurace.metoda == METODA_LEXIKALNI:
        skore = lexikalni
        prijata = skore >= konfigurace.prah_rozhodnuti
        return Dvojice(index_a, index_b, podobnost, lexikalni, skore_atributu,
                       skore, prijata, False, ())

    if konfigurace.metoda == METODA_PRAVIDLOVA:
        zaklad = max(podobnost, lexikalni)
        if rozpor:
            pozadovany_prah = 2.0
        elif skore_atributu >= 0.7:
            pozadovany_prah = PRAH_PRI_DVOU_ATRIBUTECH
        elif skore_atributu > 0.5:
            pozadovany_prah = PRAH_PRI_JEDNOM_ATRIBUTU
        else:
            pozadovany_prah = PRAH_BEZ_ATRIBUTU

        posun = konfigurace.prah_rozhodnuti - 0.72
        prijata = (not rozpor) and zaklad >= (pozadovany_prah + posun)
        return Dvojice(index_a, index_b, podobnost, lexikalni, skore_atributu,
                       zaklad, prijata, rozpor, vysvetleni)

    soucet_vah = (konfigurace.vaha_semanticka + konfigurace.vaha_lexikalni
                  + konfigurace.vaha_atributu)
    skore = (
        konfigurace.vaha_semanticka * podobnost
        + konfigurace.vaha_lexikalni * lexikalni
        + konfigurace.vaha_atributu * skore_atributu
    ) / (soucet_vah if soucet_vah else 1.0)

    prijata = (not rozpor) and skore >= konfigurace.prah_rozhodnuti
    return Dvojice(index_a, index_b, podobnost, lexikalni, skore_atributu,
                   skore, prijata, rozpor, vysvetleni)


def najdi_duplicity(
    zaznamy: Sequence[ZaznamPolozky],
    konfigurace: NastaveniDeduplikace | None = None,
    spravce: SpravceEmbeddingu | None = None,
    globalni_nastaveni: Nastaveni | None = None,
    vektory: np.ndarray | None = None,
    index: VektorovyIndex | None = None,
    postup: SledovaniPostupu = BEZ_SLEDOVANI,
) -> VysledekDeduplikace:
    konfigurace = konfigurace or NastaveniDeduplikace()
    spravce = spravce or spravce_embeddingu()
    globalni = globalni_nastaveni or nastaveni()
    cas_start = time.perf_counter()

    pocet = len(zaznamy)
    if pocet == 0:
        return VysledekDeduplikace([], [], 0, 0.0, konfigurace)

    postup.faze(FAZE_PRIPRAVA, pocet)
    texty_lexikalni: list[str] = []
    atributy: list[Atributy] = []
    urcene_druhy: list[str | None] = []
    for poradi_zaznamu, zaznam in enumerate(zaznamy):
        texty_lexikalni.append(normalizuj_pro_lexikalni(zaznam.popis))
        atributy.append(vytez_atributy(zaznam.popis))
        if konfigurace.uplatnit_druh_komponenty:
            typ = urci_typ(zaznam.popis)
            urcene_druhy.append(typ.identifikator if typ else None)
        if poradi_zaznamu % KROK_HLASENI == 0:
            postup.posun(poradi_zaznamu)
    postup.posun(pocet)
    druhy: list[str | None] | None = (
        urcene_druhy if konfigurace.uplatnit_druh_komponenty else None
    )

    if vektory is None:
        texty_embedding = [
            normalizuj_pro_embedding(z.text_pro_porovnani()) for z in zaznamy
        ]
        vektory = spravce.zakoduj(texty_embedding, zobrazit_prubeh=False)
        spravce.uloz_cache()

    if index is None or index.velikost != len(vektory):
        index = VektorovyIndex(dimenze=vektory.shape[1], konfigurace=globalni)
        index.postav(vektory)

    postup.faze(FAZE_HLEDANI, pocet)
    podobnosti, sousede = index.hledej(
        vektory,
        pocet_sousedu=konfigurace.pocet_sousedu,
        vynechat_sebe=True,
        postup=lambda hotovo, celkem: postup.posun(hotovo, celkem),
    )

    postup.faze(FAZE_DVOJICE, pocet)
    posouzene: dict[tuple[int, int], Dvojice] = {}
    for index_a in range(pocet):
        if index_a % KROK_HLASENI == 0:
            postup.posun(index_a)
        for poradi in range(sousede.shape[1]):
            index_b = int(sousede[index_a, poradi])
            if index_b < 0:
                continue
            podobnost = float(podobnosti[index_a, poradi])
            if podobnost < konfigurace.prah_kandidatu:
                continue
            klic = (min(index_a, index_b), max(index_a, index_b))
            if klic in posouzene:
                continue
            posouzene[klic] = _vyhodnot_dvojici(
                klic[0], klic[1], podobnost, texty_lexikalni,
                atributy, zaznamy, konfigurace, druhy,
            )

    postup.posun(pocet)
    dvojice = list(posouzene.values())
    prijate = [d for d in dvojice if d.prijata]

    struktura = UnionFind(pocet)
    for d in prijate:
        struktura.spoj(d.index_a, d.index_b)

    podobnost_dvojic = {(d.index_a, d.index_b): d for d in prijate}

    def _dvojice_klastru(cleny: list[int]) -> list[Dvojice]:
        return [
            podobnost_dvojic[(a, b)]
            for i, a in enumerate(cleny)
            for b in cleny[i + 1:]
            if (a, b) in podobnost_dvojic
        ]

    dvojice_podle_komponenty: dict[int, dict[tuple[int, int], Dvojice]] = {}
    for klic, d in podobnost_dvojic.items():
        dvojice_podle_komponenty.setdefault(struktura.najdi(d.index_a), {})[klic] = d

    komponenty = [k for k in struktura.skupiny().items() if len(k[1]) >= 2]
    postup.faze(FAZE_SHLUKOVANI, len(komponenty))
    klastry: list[Klastr] = []
    for poradi_komponenty, (koren, komponenta) in enumerate(komponenty):
        if poradi_komponenty % KROK_HLASENI == 0:
            postup.posun(poradi_komponenty)
        komponenta = sorted(komponenta)

        if konfigurace.prisne_shlukovani:
            skupiny_k_zapisu = _rozloz_na_uplne_skupiny(
                komponenta, dvojice_podle_komponenty.get(koren, {})
            )
        else:
            skupiny_k_zapisu = [komponenta]

        for cleny in skupiny_k_zapisu:
            if len(cleny) < 2:
                continue
            vnitrni = _dvojice_klastru(cleny)
            skore_dvojic = [d.skore for d in vnitrni] or [0.0]
            klastry.append(Klastr(
                id=len(klastry) + 1,
                indexy=cleny,
                prumerna_podobnost=float(np.mean(skore_dvojic)),
                minimalni_podobnost=float(np.min(skore_dvojic)),
                dvojice=vnitrni,
            ))

    klastry.sort(key=lambda k: (-k.velikost, -k.prumerna_podobnost))
    for poradi, klastr in enumerate(klastry, start=1):
        klastr.id = poradi

    doba = time.perf_counter() - cas_start
    statistiky = {
        "posouzenych_dvojic": float(len(dvojice)),
        "prijatych_dvojic": float(len(prijate)),
        "zamitnuto_rozporem": float(sum(1 for d in dvojice if d.rozpor_atributu)),
        "klastru": float(len(klastry)),
        "duplicitnich_zaznamu": float(sum(k.velikost - 1 for k in klastry)),
    }
    logger.info(
        "Deduplikace dokončena za %.2f s: %d dvojic posouzeno, %d přijato, %d klastrů.",
        doba, len(dvojice), len(prijate), len(klastry),
    )

    return VysledekDeduplikace(
        klastry=klastry,
        dvojice=dvojice,
        pocet_polozek=pocet,
        doba_s=doba,
        nastaveni=konfigurace,
        statistiky=statistiky,
    )


def zkontroluj_novou_polozku(
    nova: ZaznamPolozky,
    zaznamy: Sequence[ZaznamPolozky],
    vektory_katalogu: np.ndarray,
    index: VektorovyIndex,
    konfigurace: NastaveniDeduplikace | None = None,
    spravce: SpravceEmbeddingu | None = None,
    pocet_kandidatu: int = 10,
) -> list[Dvojice]:
    konfigurace = konfigurace or NastaveniDeduplikace()
    spravce = spravce or spravce_embeddingu()

    vektor = spravce.zakoduj([normalizuj_pro_embedding(nova.text_pro_porovnani())])
    podobnosti, sousede = index.hledej(vektor, pocet_sousedu=pocet_kandidatu)

    rozsirene = list(zaznamy) + [nova]
    novy_index = len(rozsirene) - 1
    texty_lexikalni = [normalizuj_pro_lexikalni(z.popis) for z in rozsirene]
    atributy = [vytez_atributy(z.popis) for z in rozsirene]

    druhy: list[str | None] | None = None
    if konfigurace.uplatnit_druh_komponenty:
        urcene: list[str | None] = [None] * len(rozsirene)
        typ_noveho = urci_typ(nova.popis)
        urcene[novy_index] = typ_noveho.identifikator if typ_noveho else None
        for poradi in range(sousede.shape[1]):
            kandidat = int(sousede[0, poradi])
            if 0 <= kandidat < len(zaznamy):
                typ_kandidata = urci_typ(zaznamy[kandidat].popis)
                urcene[kandidat] = typ_kandidata.identifikator if typ_kandidata else None
        druhy = urcene

    vysledky: list[Dvojice] = []
    for poradi in range(sousede.shape[1]):
        kandidat = int(sousede[0, poradi])
        if kandidat < 0 or kandidat >= len(zaznamy):
            continue
        podobnost = float(podobnosti[0, poradi])
        vysledky.append(_vyhodnot_dvojici(
            kandidat, novy_index, podobnost, texty_lexikalni,
            atributy, rozsirene, konfigurace, druhy,
        ))

    vysledky.sort(key=lambda d: -d.skore)
    return vysledky
