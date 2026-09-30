# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import aktivni_model, nastav_aktivni_model, nastaveni, vychozi_model
from app.db import precti_volbu, smaz_volbu, uloz_volbu
from app.jadro.llm import OllamaPoskytovatel

logger = logging.getLogger(__name__)

KLIC_VOLBY = "aktivni_model_llm"


class ChybaVolbyModelu(Exception):
    """Požadovaný model nelze nastavit."""


@dataclass(frozen=True)
class StavVolbyModelu:
    aktivni: str
    vychozi: str
    dostupne: list[str]
    ollama_dostupna: bool
    prepnuto_uzivatelem: bool
    nainstalovan: bool

    def jako_slovnik(self) -> dict[str, object]:
        return {
            "aktivni": self.aktivni,
            "vychozi": self.vychozi,
            "dostupne": self.dostupne,
            "ollama_dostupna": self.ollama_dostupna,
            "prepnuto_uzivatelem": self.prepnuto_uzivatelem,
            "nainstalovan": self.nainstalovan,
            "doporucene": [
                model
                for model in nastaveni().modely_pro_benchmark
                if model in self.dostupne
            ],
        }


def _seznam_modelu() -> tuple[bool, list[str]]:
    poskytovatel = OllamaPoskytovatel(nastaveni())
    if not poskytovatel.je_dostupny():
        return False, []
    try:
        return True, poskytovatel.seznam_modelu()
    except Exception as chyba:
        logger.warning("Seznam modelů se nepodařilo načíst: %s", chyba)
        return True, []


def obnov_ulozenou_volbu() -> str:
    try:
        ulozeny = precti_volbu(KLIC_VOLBY)
    except Exception as chyba:
        logger.warning("Uloženou volbu modelu se nepodařilo načíst: %s", chyba)
        return aktivni_model()

    if ulozeny:
        nastav_aktivni_model(ulozeny)
        logger.info("Obnovena uložená volba jazykového modelu: %s", ulozeny)
    return aktivni_model()


def zjisti_stav() -> StavVolbyModelu:
    dostupna, modely = _seznam_modelu()
    aktivni = aktivni_model()
    try:
        ulozeny = precti_volbu(KLIC_VOLBY)
    except Exception:
        ulozeny = None

    return StavVolbyModelu(
        aktivni=aktivni,
        vychozi=vychozi_model(),
        dostupne=modely,
        ollama_dostupna=dostupna,
        prepnuto_uzivatelem=bool(ulozeny),
        nainstalovan=(aktivni in modely) if modely else dostupna is False,
    )


def zmen_model(nazev: str | None, kdo: str = "neznámý") -> StavVolbyModelu:
    pozadovany = (nazev or "").strip()
    puvodni = aktivni_model()

    if not pozadovany:
        smaz_volbu(KLIC_VOLBY)
        novy = nastav_aktivni_model(None)
        logger.info("Jazykový model vrácen na výchozí hodnotu %s.", novy)
        return zjisti_stav()

    dostupna, modely = _seznam_modelu()
    if not dostupna:
        raise ChybaVolbyModelu(
            "Služba Ollama neodpovídá, model proto nelze přepnout. "
            f"Očekávána na adrese {nastaveni().ollama_url}."
        )
    if modely and pozadovany not in modely:
        raise ChybaVolbyModelu(
            f"Model {pozadovany} není v lokální instalaci k dispozici. "
            f"Nainstalujte jej příkazem: ollama pull {pozadovany}"
        )

    novy = nastav_aktivni_model(pozadovany)
    uloz_volbu(KLIC_VOLBY, novy, kdo=kdo)
    logger.info("Jazykový model přepnut z %s na %s (%s).", puvodni, novy, kdo)
    return zjisti_stav()
