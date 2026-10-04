# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.config import Nastaveni, nastaveni
from app.jadro.embeddingy import SpravceEmbeddingu, spravce_embeddingu
from app.jadro.index_faiss import VektorovyIndex
from app.jadro.normalizace import normalizuj_pro_embedding, odstran_diakritiku

logger = logging.getLogger(__name__)

ZPUSOB_PRIMY = "přímý výskyt"
ZPUSOB_VEKTOROVY = "vektorové vyhledávání"


@dataclass
class PolozkaGlosare:

    id: str
    termin_en: str
    termin_cs: str
    kategorie: str = ""
    definice: str = ""
    nespravne: str = ""
    zdroj: str = "firemní glosář"

    def termin(self, jazyk: str) -> str:
        return self.termin_en if jazyk == "en" else self.termin_cs

    def jako_dokument(self) -> str:
        casti = [self.termin_en, self.termin_cs]
        if self.definice:
            casti.append(self.definice)
        return " | ".join(casti)


@dataclass(frozen=True)
class NalezenyTermin:
    polozka: PolozkaGlosare
    skore: float
    zpusob: str

    @property
    def je_primy(self) -> bool:
        return self.zpusob == ZPUSOB_PRIMY


class Glosar:
    def __init__(
        self,
        konfigurace: Nastaveni | None = None,
        spravce: SpravceEmbeddingu | None = None,
    ) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._spravce = spravce or spravce_embeddingu()
        self._polozky: list[PolozkaGlosare] = []
        self._index: VektorovyIndex | None = None
        self._podle_tvaru: dict[str, list[int]] = {}

    def nacti_z_csv(self, cesta: Path | None = None) -> int:

        cilova_cesta = cesta or self._nastaveni.soubor_glosare
        if not cilova_cesta.exists():
            raise FileNotFoundError(
                f"Glosář nebyl nalezen na cestě {cilova_cesta}. "
                f"Spusťte nejprve skripty/generuj_glosar.py."
            )

        with cilova_cesta.open(encoding="utf-8") as soubor:
            self._polozky = [
                PolozkaGlosare(
                    id=radek["ID"],
                    termin_en=radek["TERMIN_EN"].strip(),
                    termin_cs=radek["TERMIN_CS"].strip(),
                    kategorie=radek.get("KATEGORIE", ""),
                    definice=radek.get("DEFINICE", ""),
                    nespravne=radek.get("NESPRAVNE", ""),
                    zdroj=radek.get("ZDROJ", ""),
                )
                for radek in csv.DictReader(soubor, delimiter=";")
            ]

        self._sestav_mapu_tvaru()
        self._index = None
        logger.info("Načteno %d položek glosáře.", len(self._polozky))
        return len(self._polozky)

    def uloz_do_csv(self, cesta: Path | None = None) -> None:

        cilova_cesta = cesta or self._nastaveni.soubor_glosare
        cilova_cesta.parent.mkdir(parents=True, exist_ok=True)
        with cilova_cesta.open("w", encoding="utf-8", newline="") as soubor:
            zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            zapisovac.writerow(
                ["ID", "TERMIN_EN", "TERMIN_CS", "KATEGORIE", "DEFINICE", "NESPRAVNE", "ZDROJ"]
            )
            for p in self._polozky:
                zapisovac.writerow([
                    p.id, p.termin_en, p.termin_cs, p.kategorie,
                    p.definice, p.nespravne, p.zdroj,
                ])

    def _sestav_mapu_tvaru(self) -> None:

        self._podle_tvaru = {}
        for poradi, polozka in enumerate(self._polozky):
            for tvar in (polozka.termin_en, polozka.termin_cs):
                if not tvar:
                    continue
                klic = odstran_diakritiku(tvar).lower().strip()
                if klic:
                    self._podle_tvaru.setdefault(klic, []).append(poradi)

    def zaindexuj(self) -> None:

        if not self._polozky:
            raise RuntimeError("Glosář je prázdný, není co indexovat.")

        dokumenty = [normalizuj_pro_embedding(p.jako_dokument()) for p in self._polozky]
        vektory = self._spravce.zakoduj(dokumenty)
        self._spravce.uloz_cache()

        self._index = VektorovyIndex(dimenze=vektory.shape[1], konfigurace=self._nastaveni)
        self._index.postav(vektory)
        logger.info("Vektorový index glosáře postaven nad %d termíny.", len(self._polozky))

    def _najdi_prime_vyskyty(self, text: str) -> list[tuple[int, float]]:
        normalizovany = odstran_diakritiku(text).lower()

        vyskyty: list[tuple[int, int, int, str]] = []  # (zacatek, konec, poradi, tvar)
        for tvar, indexy in self._podle_tvaru.items():
            if len(tvar) < 3:
                continue

            vzor = r"\b" + re.escape(tvar) + r"\w{0,3}\b"
            for shoda in re.finditer(vzor, normalizovany):
                for poradi in indexy:
                    vyskyty.append((shoda.start(), shoda.end(), poradi, tvar))

        vyskyty.sort(key=lambda v: (-(v[1] - v[0]), v[0]))

        obsazene: list[tuple[int, int]] = []
        nalezene: list[tuple[int, float]] = []
        videne: set[int] = set()

        for zacatek, konec, poradi, tvar in vyskyty:
            if any(zacatek < o_konec and konec > o_zacatek
                   for o_zacatek, o_konec in obsazene):
                continue
            obsazene.append((zacatek, konec))
            if poradi in videne:
                continue
            videne.add(poradi)
            nalezene.append((poradi, min(1.0, 0.90 + 0.01 * len(tvar.split()))))

        return nalezene

    def najdi_presnou_shodu(
        self, text: str, zdrojovy_jazyk: str
    ) -> PolozkaGlosare | None:
        klic = odstran_diakritiku(text).lower().strip()
        for poradi in self._podle_tvaru.get(klic, []):
            polozka = self._polozky[poradi]
            zdroj = polozka.termin(zdrojovy_jazyk)
            if zdroj and odstran_diakritiku(zdroj).lower().strip() == klic:
                return polozka
        return None

    def najdi_doslovne(self, text: str) -> list[NalezenyTermin]:
        return [
            NalezenyTermin(self._polozky[poradi], skore, ZPUSOB_PRIMY)
            for poradi, skore in self._najdi_prime_vyskyty(text)
        ]

    def najdi_relevantni(
        self,
        text: str,
        pocet: int | None = None,
        prah: float | None = None,
    ) -> list[NalezenyTermin]:

        if not self._polozky:
            return []

        pozadovany_pocet = pocet or self._nastaveni.pocet_termu_z_glosare
        pozadovany_prah = (
            self._nastaveni.prah_relevance_glosare if prah is None else prah
        )

        vysledky: dict[int, NalezenyTermin] = {}

        for poradi, skore in self._najdi_prime_vyskyty(text):
            vysledky[poradi] = NalezenyTermin(self._polozky[poradi], skore, ZPUSOB_PRIMY)

        if self._index is None:
            self.zaindexuj()

        assert self._index is not None
        vektor = self._spravce.zakoduj([normalizuj_pro_embedding(text)])
        podobnosti, indexy = self._index.hledej(
            vektor, pocet_sousedu=min(pozadovany_pocet * 3, len(self._polozky))
        )
        for poradi_vysledku in range(indexy.shape[1]):
            poradi = int(indexy[0, poradi_vysledku])
            if poradi < 0 or poradi in vysledky:
                continue
            skore = float(podobnosti[0, poradi_vysledku])
            if skore < pozadovany_prah:
                continue
            vysledky[poradi] = NalezenyTermin(
                self._polozky[poradi], skore, ZPUSOB_VEKTOROVY
            )

        serazene = sorted(
            vysledky.values(),
            key=lambda n: (0 if n.je_primy else 1, -n.skore),
        )
        return serazene[:pozadovany_pocet]

    def pridej(self, polozka: PolozkaGlosare) -> None:
        self._polozky.append(polozka)
        self._sestav_mapu_tvaru()
        self._index = None

    def uprav(self, id_polozky: str, **zmeny: str) -> bool:
        for polozka in self._polozky:
            if polozka.id == id_polozky:
                for klic, hodnota in zmeny.items():
                    if hasattr(polozka, klic):
                        setattr(polozka, klic, hodnota)
                self._sestav_mapu_tvaru()
                self._index = None
                return True
        return False

    def smaz(self, id_polozky: str) -> bool:
        puvodni_pocet = len(self._polozky)
        self._polozky = [p for p in self._polozky if p.id != id_polozky]
        if len(self._polozky) == puvodni_pocet:
            return False
        self._sestav_mapu_tvaru()
        self._index = None
        return True

    def najdi_podle_id(self, id_polozky: str) -> PolozkaGlosare | None:
        for polozka in self._polozky:
            if polozka.id == id_polozky:
                return polozka
        return None

    @property
    def polozky(self) -> list[PolozkaGlosare]:
        return list(self._polozky)

    @property
    def velikost(self) -> int:
        return len(self._polozky)

_sdileny_glosar: Glosar | None = None


def glosar() -> Glosar:
    global _sdileny_glosar
    if _sdileny_glosar is None:
        _sdileny_glosar = Glosar()
        _sdileny_glosar.nacti_z_csv()
    return _sdileny_glosar
