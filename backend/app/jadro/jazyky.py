# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Jazyk:
    kod: str
    nazev: str
    genitiv: str
    anglicky: str
    bez_mezer: bool = False


JAZYKY: dict[str, Jazyk] = {
    j.kod: j
    for j in (
        Jazyk("en", "angličtina", "angličtiny", "English"),
        Jazyk("cs", "čeština", "češtiny", "Czech"),
        Jazyk("de", "němčina", "němčiny", "German"),
        Jazyk("it", "italština", "italštiny", "Italian"),
        Jazyk("es", "španělština", "španělštiny", "Spanish"),
        Jazyk("fr", "francouzština", "francouzštiny", "French"),
        Jazyk("zh", "čínština", "čínštiny", "Chinese", bez_mezer=True),
        Jazyk("ja", "japonština", "japonštiny", "Japanese", bez_mezer=True),
    )
}

KODY_JAZYKU: tuple[str, ...] = tuple(JAZYKY)

ZNAKY_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ]")


def je_podporovany(kod: str) -> bool:
    return kod in JAZYKY


def jazyk(kod: str) -> Jazyk:
    if kod not in JAZYKY:
        raise ValueError(
            f"Jazyk „{kod}“ není podporován. Podporované: {', '.join(KODY_JAZYKU)}."
        )
    return JAZYKY[kod]


def obsahuje_cjk(text: str) -> bool:
    return bool(ZNAKY_CJK.search(text))


def pise_bez_mezer(kod: str) -> bool:
    return kod in JAZYKY and JAZYKY[kod].bez_mezer
