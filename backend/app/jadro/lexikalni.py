# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, process

from app.jadro.normalizace import normalizuj_pro_lexikalni

logger = logging.getLogger(__name__)


def podobnost_levenshtein(prvni: str, druhy: str) -> float:
    return float(fuzz.ratio(prvni, druhy)) / 100.0


def podobnost_token_set(prvni: str, druhy: str) -> float:
    return float(fuzz.token_set_ratio(prvni, druhy)) / 100.0


def podobnost_kombinovana(prvni: str, druhy: str) -> float:
    return max(podobnost_levenshtein(prvni, druhy), podobnost_token_set(prvni, druhy))


@dataclass(frozen=True)
class LexikalniDvojice:
    index_a: int
    index_b: int
    podobnost: float


def najdi_dvojice_lexikalne(
    popisy: list[str],
    prah: float = 0.85,
    normalizovat: bool = True,
    velikost_bloku: int = 512,
) -> list[LexikalniDvojice]:
    if normalizovat:
        texty = [normalizuj_pro_lexikalni(p) for p in popisy]
    else:
        texty = list(popisy)

    pocet = len(texty)
    prah_procenta = prah * 100.0
    nalezene: list[LexikalniDvojice] = []

    for zacatek in range(0, pocet, velikost_bloku):
        konec = min(zacatek + velikost_bloku, pocet)
        blok = texty[zacatek:konec]

        matice = process.cdist(
            blok,
            texty[zacatek:],
            scorer=fuzz.token_set_ratio,
            workers=-1,
            score_cutoff=prah_procenta,
        )
        radky, sloupce = np.nonzero(matice)
        for radek, sloupec in zip(radky, sloupce):
            index_a = zacatek + int(radek)
            index_b = zacatek + int(sloupec)
            if index_a >= index_b:
                continue
            nalezene.append(LexikalniDvojice(
                index_a=index_a,
                index_b=index_b,
                podobnost=float(matice[radek, sloupec]) / 100.0,
            ))

    logger.info("Lexikální metoda nalezla %d dvojic nad prahem %.2f", len(nalezene), prah)
    return nalezene
