# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

STAV_NECINNY = "necinny"
STAV_BEZI = "bezi"
STAV_DOKONCENO = "dokonceno"
STAV_CHYBA = "chyba"

MIN_DOBA_PRO_MERENI_S = 1.5
MIN_PODIL_PRO_MERENI = 0.02
MEZE_KALIBRACE = (0.2, 5.0)


@dataclass
class _Faze:
    klic: str
    nazev: str
    odhad_s: float
    skutecnost_s: float | None = None


class SledovaniPostupu:
    def __init__(self, hodiny: Callable[[], float] = time.monotonic) -> None:
        self._hodiny = hodiny
        self._zamek = threading.Lock()
        self._uloha = ""
        self._stav = STAV_NECINNY
        self._faze: list[_Faze] = []
        self._aktualni = -1
        self._hotovo = 0
        self._celkem = 0
        self._zahajeno = 0.0
        self._zahajeni_faze = 0.0
        self._ukonceno: float | None = None
        self._chyba = ""

    @property
    def bezi(self) -> bool:
        with self._zamek:
            return self._stav == STAV_BEZI

    def zacni(self, uloha: str, faze: list[tuple[str, str, float]]) -> None:
        with self._zamek:
            if self._stav == STAV_BEZI:
                raise RuntimeError(f"Úloha „{self._uloha}“ již probíhá, počkejte na její dokončení.")
            ted = self._hodiny()
            self._uloha = uloha
            self._stav = STAV_BEZI
            self._faze = [_Faze(k, n, max(0.0, o)) for k, n, o in faze]
            self._aktualni = -1
            self._hotovo = 0
            self._celkem = 0
            self._zahajeno = ted
            self._zahajeni_faze = ted
            self._ukonceno = None
            self._chyba = ""

    def faze(self, klic: str, celkem: int = 0) -> None:
        with self._zamek:
            if self._stav != STAV_BEZI:
                return
            ted = self._hodiny()
            self._uzavri_aktualni(ted)
            poradi = next((i for i, f in enumerate(self._faze) if f.klic == klic), None)
            if poradi is None:
                self._faze.append(_Faze(klic, klic, 0.0))
                poradi = len(self._faze) - 1
            self._aktualni = poradi
            self._zahajeni_faze = ted
            self._hotovo = 0
            self._celkem = max(0, celkem)

    def posun(self, hotovo: int, celkem: int | None = None) -> None:
        with self._zamek:
            if celkem is not None:
                self._celkem = max(0, celkem)
            self._hotovo = max(0, min(hotovo, self._celkem) if self._celkem else hotovo)

    def dokonci(self) -> None:
        with self._zamek:
            ted = self._hodiny()
            self._uzavri_aktualni(ted)
            self._stav = STAV_DOKONCENO
            self._ukonceno = ted

    def selhej(self, chyba: str) -> None:
        with self._zamek:
            self._stav = STAV_CHYBA
            self._chyba = chyba
            self._ukonceno = self._hodiny()

    def _uzavri_aktualni(self, ted: float) -> None:
        if 0 <= self._aktualni < len(self._faze):
            self._faze[self._aktualni].skutecnost_s = ted - self._zahajeni_faze

    def _kalibrace(self) -> float:
        odhad = sum(f.odhad_s for f in self._faze if f.skutecnost_s is not None and f.odhad_s > 0)
        skutecnost = sum(
            f.skutecnost_s for f in self._faze
            if f.skutecnost_s is not None and f.odhad_s > 0
        )
        if odhad <= 0:
            return 1.0
        return min(MEZE_KALIBRACE[1], max(MEZE_KALIBRACE[0], skutecnost / odhad))

    def _zbyva(self, ted: float) -> tuple[float | None, bool]:
        if self._aktualni < 0:
            soucet = sum(f.odhad_s for f in self._faze)
            return (soucet if soucet > 0 else None), False

        kalibrace = self._kalibrace()
        faze = self._faze[self._aktualni]
        uplynulo_faze = ted - self._zahajeni_faze
        merene = (
            self._celkem > 0
            and self._hotovo > 0
            and self._hotovo / self._celkem >= MIN_PODIL_PRO_MERENI
            and uplynulo_faze >= MIN_DOBA_PRO_MERENI_S
        )
        if merene:
            zbyva_faze = uplynulo_faze / self._hotovo * (self._celkem - self._hotovo)
        elif faze.odhad_s > 0:
            zbyva_faze = max(faze.odhad_s * kalibrace - uplynulo_faze, 0.0)
        else:
            zbyva_faze = 0.0

        nasledujici = sum(f.odhad_s for f in self._faze[self._aktualni + 1:]) * kalibrace
        if not merene and faze.odhad_s <= 0 and nasledujici <= 0:
            return None, False
        return zbyva_faze + nasledujici, merene

    def snimek(self) -> dict[str, Any]:
        with self._zamek:
            ted = self._hodiny()
            konec = self._ukonceno if self._ukonceno is not None else ted
            if self._stav == STAV_BEZI:
                zbyva, merene = self._zbyva(ted)
            else:
                zbyva, merene = (0.0 if self._stav == STAV_DOKONCENO else None), True
            faze = self._faze[self._aktualni] if 0 <= self._aktualni < len(self._faze) else None
            return {
                "uloha": self._uloha,
                "stav": self._stav,
                "faze": faze.nazev if faze else "",
                "faze_poradi": self._aktualni + 1,
                "pocet_fazi": len(self._faze),
                "hotovo": self._hotovo,
                "celkem": self._celkem,
                "uplynulo_s": round(konec - self._zahajeno, 1) if self._uloha else 0.0,
                "zbyva_s": round(zbyva, 1) if zbyva is not None else None,
                "odhad_z_mereni": merene,
                "chyba": self._chyba,
            }


class _BezSledovani(SledovaniPostupu):
    def faze(self, klic: str, celkem: int = 0) -> None:
        return

    def posun(self, hotovo: int, celkem: int | None = None) -> None:
        return


BEZ_SLEDOVANI: SledovaniPostupu = _BezSledovani()
