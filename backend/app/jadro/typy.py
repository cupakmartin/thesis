# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass

from app.jadro.normalizace import odstran_diakritiku
from app.jadro.validace import MAXIMALNI_ROZDIL_KMENU, _kmen, _slova

logger = logging.getLogger(__name__)

KATEGORIE_KOMPONENT: frozenset[str] = frozenset({
    "komponenta", "armatura", "ložisko", "čerpadlo", "těsnění", "elektro",
    "přenos výkonu", "spojovací materiál", "filtr", "hydraulika", "měření",
    "potrubí", "ventilátor", "mazivo", "strojní součást", "nástroj",
})

FUNKCNI_VARIANTY: dict[str, str] = {
    "2/2 nc": "F_2_2_NC", "2/2 no": "F_2_2_NO",
    "3/2 nc": "F_3_2_NC", "3/2 no": "F_3_2_NO",
    "5/2": "F_5_2",
    "nc": "F_NC", "no": "F_NO",
}


VELIKOST_MEZIPAMETI = 250_000


@dataclass(frozen=True)
class UrcenyTyp:
    identifikator: str
    nazev: str
    zdroj_terminu: str

    def __str__(self) -> str:
        return f"{self.nazev} ({self.identifikator})"


class SlovnikTypu:
    def __init__(self) -> None:
        self._podle_tvaru: dict[str, tuple[str, str]] = {}
        self._tvary: list[tuple[int, frozenset[str], str, str, str]] = []
        self._tvary_podle_kmene: dict[str, list[int]] = {}
        self._prodlouzeni: dict[str, set[str]] = {}
        self._mezipamet: dict[str, UrcenyTyp | None] = {}
        self._pripraven = False
        self._zamek = threading.Lock()

    def priprav(self, polozky_glosare: list | None = None) -> None:
        with self._zamek:
            if polozky_glosare is None:
                from app.jadro.glosar import glosar

                polozky_glosare = glosar().polozky

            self._podle_tvaru = {}
            for polozka in polozky_glosare:
                if polozka.kategorie not in KATEGORIE_KOMPONENT:
                    continue
                identifikator = "T_" + re.sub(
                    r"[^a-z0-9]+", "_", polozka.termin_en.strip().lower()
                ).strip("_").upper()
                for tvar in (polozka.termin_en, polozka.termin_cs):
                    if not tvar or len(tvar.strip()) < 3:
                        continue
                    klic = odstran_diakritiku(tvar).lower().strip()
                    stavajici = self._podle_tvaru.get(klic)
                    if stavajici is None:
                        self._podle_tvaru[klic] = (identifikator, polozka.termin_cs)

            for tvar, identifikator in FUNKCNI_VARIANTY.items():
                self._podle_tvaru.setdefault(tvar, (identifikator, tvar))

            self._sestav_rejstrik()
            self._pripraven = True
            logger.info("Slovník druhů komponent obsahuje %d tvarů.",
                        len(self._podle_tvaru))

    def _sestav_rejstrik(self) -> None:
        self._tvary = []
        self._tvary_podle_kmene = {}
        self._prodlouzeni = {}
        self._mezipamet = {}

        for tvar, (identifikator, nazev) in self._podle_tvaru.items():
            slova = _slova(tvar)
            if not slova:
                continue
            kmeny = frozenset(_kmen(s) for s in slova)
            poradi = len(self._tvary)
            self._tvary.append((len(slova), kmeny, identifikator, nazev, tvar))
            for kmen in kmeny:
                self._tvary_podle_kmene.setdefault(kmen, []).append(poradi)
                for rozdil in range(1, MAXIMALNI_ROZDIL_KMENU + 1):
                    if len(kmen) - rozdil >= 1:
                        self._prodlouzeni.setdefault(kmen[:-rozdil], set()).add(kmen)

    def _odpovidajici_kmeny(self, kmen_popisu: str) -> set[str]:
        shody = set(self._prodlouzeni.get(kmen_popisu, ()))
        for delka in range(max(1, len(kmen_popisu) - MAXIMALNI_ROZDIL_KMENU),
                           len(kmen_popisu) + 1):
            predpona = kmen_popisu[:delka]
            if predpona in self._tvary_podle_kmene:
                shody.add(predpona)
        return shody

    def urci(self, popis: str) -> UrcenyTyp | None:
        if not self._pripraven:
            self.priprav()
        if not popis:
            return None
        if popis in self._mezipamet:
            return self._mezipamet[popis]

        vysledek = self._urci_bez_mezipameti(popis)
        if len(self._mezipamet) >= VELIKOST_MEZIPAMETI:
            self._mezipamet.clear()
        self._mezipamet[popis] = vysledek
        return vysledek

    def _urci_bez_mezipameti(self, popis: str) -> UrcenyTyp | None:
        kmeny_popisu = {_kmen(s) for s in _slova(popis)}
        if not kmeny_popisu:
            return None

        nalezene: set[str] = set()
        for kmen_popisu in kmeny_popisu:
            nalezene |= self._odpovidajici_kmeny(kmen_popisu)

        kandidati = {
            poradi for kmen in nalezene for poradi in self._tvary_podle_kmene.get(kmen, ())
        }
        nejlepsi: tuple[int, frozenset[str], str, str, str] | None = None
        nejlepsi_poradi = -1
        for poradi in sorted(kandidati):
            tvar = self._tvary[poradi]
            if nejlepsi is not None and tvar[0] <= nejlepsi[0]:
                continue
            if tvar[1] <= nalezene:
                nejlepsi, nejlepsi_poradi = tvar, poradi

        if nejlepsi is None or nejlepsi_poradi < 0:
            return None
        return UrcenyTyp(identifikator=nejlepsi[2], nazev=nejlepsi[3],
                         zdroj_terminu=nejlepsi[4])

    @property
    def velikost(self) -> int:
        return len(self._podle_tvaru)


_sdileny_slovnik: SlovnikTypu | None = None


def slovnik_typu() -> SlovnikTypu:
    global _sdileny_slovnik
    if _sdileny_slovnik is None:
        _sdileny_slovnik = SlovnikTypu()
    return _sdileny_slovnik


def urci_typ(popis: str) -> UrcenyTyp | None:
    return slovnik_typu().urci(popis)
