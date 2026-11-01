# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import Nastaveni, nastaveni
from app.jadro.embeddingy import SpravceEmbeddingu, spravce_embeddingu
from app.jadro.index_faiss import VektorovyIndex
from app.jadro.jazyky import KODY_JAZYKU, obsahuje_cjk
from app.jadro.normalizace import normalizuj_pro_embedding, odstran_diakritiku

logger = logging.getLogger(__name__)

ZPUSOB_PRIMY = "přímý výskyt"
ZPUSOB_VEKTOROVY = "vektorové vyhledávání"
KATEGORIE_DRUHU_PORUCHY = "ISO 14224 - druh poruchy"
KATEGORIE_UDRZBOVE_CINNOSTI = "ISO 14224 - údržbová činnost"


def _ocisti(hodnoty: dict[str, str] | None) -> dict[str, str]:
    return {
        k: v.strip()
        for k, v in (hodnoty or {}).items()
        if k in KODY_JAZYKU and v and v.strip()
    }


class PolozkaGlosare:
    def __init__(
        self,
        id: str,
        termin_en: str = "",
        termin_cs: str = "",
        kategorie: str = "",
        definice: str = "",
        nespravne: str = "",
        zdroj: str = "firemní glosář",
        terminy: dict[str, str] | None = None,
        nespravne_podle_jazyka: dict[str, str] | None = None,
        strojove: set[str] | None = None,
    ) -> None:
        self.id = id
        self.terminy = _ocisti(terminy)
        if termin_en.strip():
            self.terminy["en"] = termin_en.strip()
        if termin_cs.strip():
            self.terminy["cs"] = termin_cs.strip()
        self.nespravne_podle_jazyka = _ocisti(nespravne_podle_jazyka)
        if nespravne.strip():
            self.nespravne_podle_jazyka["cs"] = nespravne.strip()
        self.kategorie = kategorie
        self.definice = definice
        self.zdroj = zdroj
        self.strojove = {k for k in (strojove or set()) if k in self.terminy}

    def __eq__(self, jina: object) -> bool:
        if not isinstance(jina, PolozkaGlosare):
            return NotImplemented
        return vars(self) == vars(jina)

    def __repr__(self) -> str:
        return f"PolozkaGlosare(id={self.id!r}, terminy={self.terminy!r})"

    def termin(self, jazyk: str) -> str:
        return self.terminy.get(jazyk, "")

    def nespravne_v(self, jazyk: str) -> str:
        return self.nespravne_podle_jazyka.get(jazyk, "")

    @property
    def jazyky(self) -> list[str]:
        return [k for k in KODY_JAZYKU if k in self.terminy]

    @property
    def je_udrzbova_cinnost(self) -> bool:
        return self.kategorie == KATEGORIE_UDRZBOVE_CINNOSTI

    @property
    def jen_s_velkym_pismenem(self) -> bool:
        return self.kategorie == KATEGORIE_DRUHU_PORUCHY and all(
            len(t.split()) == 1 for t in self.terminy.values()
        )

    @property
    def termin_en(self) -> str:
        return self.termin("en")

    @termin_en.setter
    def termin_en(self, hodnota: str) -> None:
        self.nastav_termin("en", hodnota)

    @property
    def termin_cs(self) -> str:
        return self.termin("cs")

    @termin_cs.setter
    def termin_cs(self, hodnota: str) -> None:
        self.nastav_termin("cs", hodnota)

    @property
    def nespravne(self) -> str:
        return self.nespravne_v("cs")

    @nespravne.setter
    def nespravne(self, hodnota: str) -> None:
        if hodnota.strip():
            self.nespravne_podle_jazyka["cs"] = hodnota.strip()
        else:
            self.nespravne_podle_jazyka.pop("cs", None)

    def nastav_termin(self, jazyk: str, hodnota: str, strojove: bool = False) -> None:
        if hodnota.strip():
            self.terminy[jazyk] = hodnota.strip()
            if strojove:
                self.strojove.add(jazyk)
            else:
                self.strojove.discard(jazyk)
        else:
            self.terminy.pop(jazyk, None)
            self.strojove.discard(jazyk)

    def jako_dokument(self) -> str:
        casti = [self.terminy[k] for k in self.jazyky]
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
                _polozka_z_radku(radek)
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
                ["ID", "KATEGORIE", "DEFINICE", "ZDROJ"]
                + [f"TERMIN_{k.upper()}" for k in KODY_JAZYKU]
                + [f"NESPRAVNE_{k.upper()}" for k in KODY_JAZYKU]
                + ["STROJOVE"]
            )
            for p in self._polozky:
                zapisovac.writerow(
                    [p.id, p.kategorie, p.definice, p.zdroj]
                    + [p.termin(k) for k in KODY_JAZYKU]
                    + [p.nespravne_v(k) for k in KODY_JAZYKU]
                    + [",".join(k for k in KODY_JAZYKU if k in p.strojove)]
                )

    def _sestav_mapu_tvaru(self) -> None:
        self._podle_tvaru = {}
        for poradi, polozka in enumerate(self._polozky):
            for tvar in polozka.terminy.values():
                klic = odstran_diakritiku(tvar).lower().strip()
                if klic and poradi not in self._podle_tvaru.get(klic, []):
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

        vyskyty: list[tuple[int, int, int, str]] = []
        for tvar, indexy in self._podle_tvaru.items():
            if obsahuje_cjk(tvar):
                if len(tvar) < 2:
                    continue
                vzor = re.escape(tvar)
            else:
                if len(tvar) < 3:
                    continue
                vzor = r"\b" + re.escape(tvar) + r"\w{0,3}\b"
            for shoda in re.finditer(vzor, normalizovany):
                for poradi in indexy:
                    if (
                        self._polozky[poradi].jen_s_velkym_pismenem
                        and not obsahuje_cjk(tvar)
                        and len(normalizovany) == len(text)
                        and not text[shoda.start()].isupper()
                    ):
                        continue
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

    def prepocitej(self) -> None:
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

def _polozka_z_radku(radek: dict[str, str]) -> PolozkaGlosare:
    terminy = {k: radek.get(f"TERMIN_{k.upper()}") or "" for k in KODY_JAZYKU}
    nespravne = {k: radek.get(f"NESPRAVNE_{k.upper()}") or "" for k in KODY_JAZYKU}
    if radek.get("NESPRAVNE"):
        nespravne["cs"] = radek["NESPRAVNE"]
    strojove = {k.strip() for k in (radek.get("STROJOVE") or "").split(",") if k.strip()}
    return PolozkaGlosare(
        id=radek["ID"],
        kategorie=radek.get("KATEGORIE") or "",
        definice=radek.get("DEFINICE") or "",
        zdroj=radek.get("ZDROJ") or "",
        terminy=terminy,
        nespravne_podle_jazyka=nespravne,
        strojove=strojove,
    )


_sdileny_glosar: Glosar | None = None


def glosar() -> Glosar:
    global _sdileny_glosar
    if _sdileny_glosar is None:
        _sdileny_glosar = Glosar()
        _sdileny_glosar.nacti_z_csv()
    return _sdileny_glosar
