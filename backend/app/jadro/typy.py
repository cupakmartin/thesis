# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass

from app.jadro.normalizace import odstran_diakritiku
from app.jadro.validace import _kmen, _kmeny_odpovidaji, _slova

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

            self._pripraven = True
            logger.info("Slovník druhů komponent obsahuje %d tvarů.",
                        len(self._podle_tvaru))

    def urci(self, popis: str) -> UrcenyTyp | None:
        if not self._pripraven:
            self.priprav()
        if not popis:
            return None

        kmeny_popisu = {_kmen(s) for s in _slova(popis)}
        if not kmeny_popisu:
            return None

        nejlepsi: tuple[str, str, str] | None = None
        nejlepsi_pocet_slov = 0

        for tvar, (identifikator, nazev) in self._podle_tvaru.items():
            slova_tvaru = _slova(tvar)
            if not slova_tvaru or len(slova_tvaru) <= nejlepsi_pocet_slov:
                continue
            if all(
                any(_kmeny_odpovidaji(kmen_popisu, _kmen(slovo))
                    for kmen_popisu in kmeny_popisu)
                for slovo in slova_tvaru
            ):
                nejlepsi = (identifikator, nazev, tvar)
                nejlepsi_pocet_slov = len(slova_tvaru)

        if nejlepsi is None:
            return None
        return UrcenyTyp(identifikator=nejlepsi[0], nazev=nejlepsi[1],
                         zdroj_terminu=nejlepsi[2])

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
