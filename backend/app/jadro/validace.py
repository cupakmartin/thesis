# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.jadro.atributy import vytez_atributy
from app.jadro.glosar import NalezenyTermin
from app.jadro.jazyky import obsahuje_cjk
from app.jadro.normalizace import odstran_diakritiku

DELKA_KONCOVKY_PODLE_DELKY: tuple[tuple[int, int], ...] = (
    (6, 2),
    (4, 1),
    (0, 0),
)

MAXIMALNI_ROZDIL_KMENU = 2
MINIMALNI_DELKA_PRO_POMER = 20

NEVYZNAMOVA_SLOVA: frozenset[str] = frozenset({
    "a", "i", "o", "u", "v", "s", "z", "k", "na", "pro", "do", "od", "se", "je",
    "the", "a", "an", "of", "for", "to", "in", "on", "and", "or",
})


def _kmen(slovo: str) -> str:
    for minimalni_delka, koncovka in DELKA_KONCOVKY_PODLE_DELKY:
        if len(slovo) >= minimalni_delka:
            return slovo[: len(slovo) - koncovka] if koncovka else slovo
    return slovo


def _kmeny_odpovidaji(prvni: str, druhy: str) -> bool:
    if prvni == druhy:
        return True
    if abs(len(prvni) - len(druhy)) > MAXIMALNI_ROZDIL_KMENU:
        return False
    return prvni.startswith(druhy) or druhy.startswith(prvni)


def _slova(text: str) -> list[str]:
    normalizovany = odstran_diakritiku(text.replace("ß", "ss")).lower()
    return [s for s in re.findall(r"[a-z0-9]+", normalizovany) if s]


def obsahuje_termin(text: str, termin: str) -> bool:
    if obsahuje_cjk(termin):
        return termin.strip() in text
    slova_terminu = [s for s in _slova(termin) if s not in NEVYZNAMOVA_SLOVA]
    if not slova_terminu:
        return False

    kmeny_textu = [_kmen(s) for s in _slova(text)]
    if not kmeny_textu:
        return False

    for slovo in slova_terminu:
        kmen_hledany = _kmen(slovo)
        if not any(_kmeny_odpovidaji(kmen_textu, kmen_hledany)
                   for kmen_textu in kmeny_textu):
            return False
    return True


@dataclass(frozen=True)
class KontrolaTerminu:
    termin_zdroj: str
    termin_cil: str
    ocekavan: bool
    dodrzen: bool
    nespravna_varianta: str = ""
    nespravna_varianta_pouzita: bool = False


@dataclass
class VysledekValidace:
    kontroly: list[KontrolaTerminu] = field(default_factory=list)
    chybejici_identifikatory: list[str] = field(default_factory=list)
    varovani: list[str] = field(default_factory=list)

    @property
    def pocet_ocekavanych(self) -> int:
        return sum(1 for k in self.kontroly if k.ocekavan)

    @property
    def pocet_dodrzenych(self) -> int:
        return sum(1 for k in self.kontroly if k.ocekavan and k.dodrzen)

    @property
    def mira_dodrzeni_glosare(self) -> float:
        ocekavano = self.pocet_ocekavanych
        if ocekavano == 0:
            return 1.0
        return self.pocet_dodrzenych / ocekavano

    @property
    def pocet_nespravnych_variant(self) -> int:
        return sum(1 for k in self.kontroly if k.nespravna_varianta_pouzita)

    @property
    def identifikatory_zachovany(self) -> bool:
        return not self.chybejici_identifikatory

    @property
    def je_v_poradku(self) -> bool:
        return (
            self.mira_dodrzeni_glosare >= 1.0
            and self.pocet_nespravnych_variant == 0
            and self.identifikatory_zachovany
        )

    def souhrn(self) -> str:
        if self.je_v_poradku:
            return "Překlad splňuje všechny kontrolované podmínky."
        casti: list[str] = []
        if self.pocet_ocekavanych and self.pocet_dodrzenych < self.pocet_ocekavanych:
            casti.append(
                f"dodrženo {self.pocet_dodrzenych} z {self.pocet_ocekavanych} termínů glosáře"
            )
        if self.pocet_nespravnych_variant:
            casti.append(f"použito {self.pocet_nespravnych_variant} nesprávných variant")
        if self.chybejici_identifikatory:
            casti.append(
                f"v překladu chybí identifikátory: {', '.join(self.chybejici_identifikatory)}"
            )
        return "; ".join(casti)


def _identifikatory(text: str) -> set[str]:
    atributy = vytez_atributy(text)
    hodnoty: set[str] = set()
    hodnoty |= {f"DN{v}" for v in atributy.dn}
    hodnoty |= {f"PN{v}" for v in atributy.pn}
    hodnoty |= {f"IP{v}" for v in atributy.ip}
    hodnoty |= set(atributy.kody)
    hodnoty |= set(atributy.zavity)
    hodnoty |= set(atributy.rozmery)
    return hodnoty


def zvaliduj_preklad(
    zdrojovy_text: str,
    preklad: str,
    nalezene_terminy: list[NalezenyTermin],
    zdrojovy_jazyk: str = "en",
    cilovy_jazyk: str = "cs",
) -> VysledekValidace:
    vysledek = VysledekValidace()

    for nalezeny in nalezene_terminy:
        polozka = nalezeny.polozka
        termin_zdroj = polozka.termin(zdrojovy_jazyk)
        termin_cil = polozka.termin(cilovy_jazyk)
        if not termin_zdroj or not termin_cil:
            continue

        ocekavan = obsahuje_termin(zdrojovy_text, termin_zdroj)
        dodrzen = obsahuje_termin(preklad, termin_cil) if ocekavan else False

        nespravna = polozka.nespravne_v(cilovy_jazyk)
        nespravna_pouzita = bool(nespravna and obsahuje_termin(preklad, nespravna))

        vysledek.kontroly.append(KontrolaTerminu(
            termin_zdroj=termin_zdroj,
            termin_cil=termin_cil,
            ocekavan=ocekavan,
            dodrzen=dodrzen,
            nespravna_varianta=nespravna,
            nespravna_varianta_pouzita=nespravna_pouzita,
        ))

    ve_zdroji = _identifikatory(zdrojovy_text)
    v_prekladu = _identifikatory(preklad)
    chybejici = sorted(ve_zdroji - v_prekladu)
    vysledek.chybejici_identifikatory = chybejici
    if chybejici:
        vysledek.varovani.append(
            "Překlad nezachoval všechny technické identifikátory ze zdrojového textu."
        )

    if len(zdrojovy_text.strip()) >= MINIMALNI_DELKA_PRO_POMER and preklad.strip():
        pomer = len(preklad) / len(zdrojovy_text)
        if pomer < 0.4:
            vysledek.varovani.append(
                "Překlad je výrazně kratší než zdrojový text; mohla být vynechána část obsahu."
            )
        elif pomer > 2.5:
            vysledek.varovani.append(
                "Překlad je výrazně delší než zdrojový text; model mohl doplnit informace navíc."
            )

    return vysledek
