# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.config import Nastaveni, aktivni_model, nastaveni

logger = logging.getLogger(__name__)

ZNACKA_ZACATKU = "<<<ZACATEK_TEXTU_KE_ZPRACOVANI>>>"
ZNACKA_KONCE = "<<<KONEC_TEXTU_KE_ZPRACOVANI>>>"


class ChybaLLM(RuntimeError):
    """Chyba při komunikaci s jazykovým modelem."""


@dataclass(frozen=True)
class OdpovedLLM:
    text: str
    model: str
    doba_s: float
    pocet_tokenu_vstup: int | None = None
    pocet_tokenu_vystup: int | None = None


class PoskytovatelLLM(Protocol):
    @property
    def nazev_modelu(self) -> str: ...

    def je_dostupny(self) -> bool: ...

    def generuj(
        self,
        systemova_instrukce: str,
        uzivatelsky_vstup: str,
        temperature: float | None = None,
        model: str | None = None,
        max_tokenu: int | None = None,
        stop: Sequence[str] | None = None,
    ) -> OdpovedLLM: ...


def obal_uzivatelsky_vstup(text: str) -> str:
    ocisteny = text.replace(ZNACKA_ZACATKU, "").replace(ZNACKA_KONCE, "")
    return f"{ZNACKA_ZACATKU}\n{ocisteny}\n{ZNACKA_KONCE}"


class OllamaPoskytovatel:
    def __init__(self, konfigurace: Nastaveni | None = None) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._klient = None

    def _ziskej_klienta(self):
        if self._klient is None:
            from ollama import Client

            self._klient = Client(host=self._nastaveni.ollama_url)
        return self._klient

    @property
    def nazev_modelu(self) -> str:
        return aktivni_model()

    def je_dostupny(self) -> bool:
        try:
            self._ziskej_klienta().list()
            return True
        except Exception:
            return False

    def seznam_modelu(self) -> list[str]:
        try:
            odpoved = self._ziskej_klienta().list()
        except Exception as chyba:
            raise ChybaLLM(f"Nepodařilo se získat seznam modelů: {chyba}") from chyba

        modely: list[str] = []
        for polozka in odpoved.get("models", []):
            nazev = polozka.get("model") or polozka.get("name")
            if nazev:
                modely.append(str(nazev))
        return sorted(modely)

    def generuj(
        self,
        systemova_instrukce: str,
        uzivatelsky_vstup: str,
        temperature: float | None = None,
        model: str | None = None,
        max_tokenu: int | None = None,
        stop: Sequence[str] | None = None,
    ) -> OdpovedLLM:
        pouzity_model = model or aktivni_model()
        pouzita_teplota = (
            self._nastaveni.temperature if temperature is None else temperature
        )

        zpravy = [
            {"role": "system", "content": systemova_instrukce},
            {"role": "user", "content": obal_uzivatelsky_vstup(uzivatelsky_vstup)},
        ]

        volby: dict[str, object] = {
            "temperature": pouzita_teplota,
            "num_predict": max_tokenu or self._nastaveni.max_tokenu_odpovedi,
            "num_ctx": self._nastaveni.kontext_modelu,
        }
        if stop:
            volby["stop"] = list(stop)

        cas_start = time.perf_counter()
        try:
            odpoved = self._ziskej_klienta().chat(
                model=pouzity_model,
                messages=zpravy,
                options=volby,
            )
        except Exception as chyba:
            raise ChybaLLM(
                f"Volání modelu {pouzity_model} selhalo: {chyba}. "
                f"Ověřte, že služba Ollama běží na {self._nastaveni.ollama_url}."
            ) from chyba

        doba = time.perf_counter() - cas_start
        text = (odpoved.get("message") or {}).get("content", "")

        return OdpovedLLM(
            text=text.strip(),
            model=pouzity_model,
            doba_s=doba,
            pocet_tokenu_vstup=odpoved.get("prompt_eval_count"),
            pocet_tokenu_vystup=odpoved.get("eval_count"),
        )


class StubPoskytovatel:
    def __init__(self, odpovedi: dict[str, str] | None = None) -> None:
        self._odpovedi = odpovedi or {}
        self.zaznamenane_vstupy: list[tuple[str, str]] = []
        self.zaznamenane_parametry: list[dict[str, object]] = []

    @property
    def nazev_modelu(self) -> str:
        return "stub"

    def je_dostupny(self) -> bool:
        return True

    def seznam_modelu(self) -> list[str]:
        return ["stub"]

    def generuj(
        self,
        systemova_instrukce: str,
        uzivatelsky_vstup: str,
        temperature: float | None = None,
        model: str | None = None,
        max_tokenu: int | None = None,
        stop: Sequence[str] | None = None,
    ) -> OdpovedLLM:
        self.zaznamenane_vstupy.append((systemova_instrukce, uzivatelsky_vstup))
        self.zaznamenane_parametry.append(
            {"max_tokenu": max_tokenu, "stop": list(stop or []), "model": model}
        )
        for klic, hodnota in self._odpovedi.items():
            if klic in uzivatelsky_vstup:
                return OdpovedLLM(text=hodnota, model="stub", doba_s=0.0)
        return OdpovedLLM(text=uzivatelsky_vstup.strip(), model="stub", doba_s=0.0)

_sdileny_poskytovatel: PoskytovatelLLM | None = None


def poskytovatel_llm(konfigurace: Nastaveni | None = None) -> PoskytovatelLLM:
    global _sdileny_poskytovatel
    if _sdileny_poskytovatel is None:
        _sdileny_poskytovatel = OllamaPoskytovatel(konfigurace)
    return _sdileny_poskytovatel


def nastav_poskytovatele(poskytovatel: PoskytovatelLLM | None) -> None:
    global _sdileny_poskytovatel
    _sdileny_poskytovatel = poskytovatel
