from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Mapping

ZKRATKY_CS: dict[str, str] = {
    "cerp": "čerpadlo",
    "loz": "ložisko",
    "lozis": "ložisko",
    "vent": "ventil",
    "tesn": "těsnění",
    "srb": "šroub",
    "sroub": "šroub",
    "mtc": "matice",
    "podl": "podložka",
    "hydr": "hydraulický",
    "pneum": "pneumatický",
    "elektr": "elektrický",
    "el": "elektrický",
    "vysokotl": "vysokotlaký",
    "nizkotl": "nízkotlaký",
    "kul": "kuličkový",
    "val": "válečkový",
    "prevod": "převodovka",
    "prevodov": "převodovka",
    "mot": "motor",
    "prum": "průměr",
    "dl": "délka",
    "sir": "šířka",
    "tl": "tloušťka",
    "nerez": "nerezový",
    "poj": "pojistný",
    "spoj": "spojka",
    "man": "manometr",
    "ozn": "označení",
    "zpetn": "zpětný",
}

ZKRATKY_EN: dict[str, str] = {
    "brg": "bearing",
    "bear": "bearing",
    "vlv": "valve",
    "pmp": "pump",
    "mtr": "motor",
    "cyl": "cylinder",
    "hyd": "hydraulic",
    "pneu": "pneumatic",
    "elec": "electric",
    "elect": "electric",
    "ss": "stainless steel",
    "cs": "carbon steel",
    "dia": "diameter",
    "lg": "length",
    "thk": "thickness",
    "asm": "assembly",
    "assy": "assembly",
    "gskt": "gasket",
    "gsk": "gasket",
    "brkt": "bracket",
    "flg": "flange",
    "conn": "connector",
    "htr": "heater",
    "swtch": "switch",
    "sw": "switch",
    "temp": "temperature",
    "press": "pressure",
    "hd": "head",
    "scr": "screw",
    "wshr": "washer",
    "blt": "bolt",
}

ZKRATKY: dict[str, str] = {**ZKRATKY_CS, **ZKRATKY_EN}

KANONICKE_JEDNOTKY: dict[str, str] = {
    "mm": "mm", "milimetr": "mm", "milimetru": "mm", "milimetrů": "mm", "millimeter": "mm",
    "cm": "cm", "centimetr": "cm", "centimetru": "cm", "centimeter": "cm",
    "m": "m", "metr": "m", "metru": "m", "meter": "m",
    "kg": "kg", "kilogram": "kg", "kilogramu": "kg",
    "g": "g", "gram": "g", "gramu": "g",
    "l": "l", "litr": "l", "litru": "l", "liter": "l",
    "bar": "bar", "baru": "bar", "barů": "bar",
    "psi": "psi",
    "v": "v", "volt": "v", "voltu": "v",
    "a": "a", "amper": "a", "ampere": "a",
    "w": "w", "watt": "w", "wattu": "w",
    "kw": "kw", "kilowatt": "kw",
    "nm": "nm", "newtonmetr": "nm",
    "rpm": "rpm",
    "ot/min": "rpm", "otmin": "rpm",
}

MM_NA_PALEC: float = 25.4

_VZOR_CISLO_JEDNOTKA = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*"
    r"(mm|cm|m|kg|g|l|bar|psi|v|a|w|kw|nm|rpm|"
    r"milimetr[uů]?|centimetr[uů]?|metr[uů]?|kilogram[uů]?|gram[uů]?|litr[uů]?|"
    r"bar[uů]?|volt[uů]?|amper[eu]?|watt[uů]?|kilowatt|ot/min)"
    r"(?![\w])",
    flags=re.IGNORECASE,
)

_VZOR_PALEC = re.compile(
    r"(?<![\w])(?:(\d+)\s*/\s*(\d+)|(\d+(?:[.,]\d+)?))\s*(?:\"|''|in\b|inch(?:es)?\b|palec\w*)",
    flags=re.IGNORECASE,
)

_VZOR_ZAVIT = re.compile(r"(?<![\w])m\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", flags=re.IGNORECASE)

_VZOR_ZKRATKA = re.compile(r"\b([a-zA-Zá-žÁ-Ž]{1,9})\.", flags=re.UNICODE)

_VZOR_VICE_MEZER = re.compile(r"\s+")
_VZOR_NEALFANUM = re.compile(r"[^\w\s./×-]", flags=re.UNICODE)


def odstran_diakritiku(text: str) -> str:
    rozlozeny = unicodedata.normalize("NFKD", text)
    return "".join(znak for znak in rozlozeny if not unicodedata.combining(znak))


def _cislo_na_text(hodnota: float) -> str:
    if abs(hodnota - round(hodnota)) < 1e-9:
        return str(int(round(hodnota)))
    return f"{hodnota:.2f}".rstrip("0").rstrip(".")


def normalizuj_jednotky(text: str) -> str:
    def _nahrad_palec(shoda: re.Match[str]) -> str:
        citatel, jmenovatel, desetinne = shoda.group(1), shoda.group(2), shoda.group(3)
        if citatel is not None and jmenovatel is not None:
            delitel = float(jmenovatel)
            if delitel == 0:
                return shoda.group(0)
            palce = float(citatel) / delitel
        else:
            palce = float(str(desetinne).replace(",", "."))
        return f"{_cislo_na_text(palce * MM_NA_PALEC)} mm"

    def _nahrad_zavit(shoda: re.Match[str]) -> str:
        prumer = shoda.group(1).replace(",", ".")
        stoupani = shoda.group(2).replace(",", ".")
        return f"m{prumer}x{stoupani}"

    def _nahrad_jednotku(shoda: re.Match[str]) -> str:
        cislo = shoda.group(1).replace(",", ".")
        jednotka = shoda.group(2).lower()
        kanonicka = KANONICKE_JEDNOTKY.get(jednotka, jednotka)
        return f"{cislo} {kanonicka}"

    vysledek = _VZOR_PALEC.sub(_nahrad_palec, text)
    vysledek = _VZOR_ZAVIT.sub(_nahrad_zavit, vysledek)
    vysledek = _VZOR_CISLO_JEDNOTKA.sub(_nahrad_jednotku, vysledek)
    return vysledek


def rozvin_zkratky(text: str, slovnik: Mapping[str, str] | None = None) -> str:
    pouzity_slovnik = ZKRATKY if slovnik is None else slovnik

    def _nahrad_s_teckou(shoda: re.Match[str]) -> str:
        slovo = shoda.group(1)
        klic = odstran_diakritiku(slovo).lower()
        return pouzity_slovnik.get(klic, shoda.group(0))

    vysledek = _VZOR_ZKRATKA.sub(_nahrad_s_teckou, text)

    slova = vysledek.split()
    prelozena: list[str] = []
    for slovo in slova:
        jadro_slova = slovo.strip(".,;:()[]")
        klic = odstran_diakritiku(jadro_slova).lower()
        if klic in pouzity_slovnik and len(klic) <= 6:
            prelozena.append(pouzity_slovnik[klic])
        else:
            prelozena.append(slovo)
    return " ".join(prelozena)


def vycisti_text(text: str) -> str:
    bez_znaku = _VZOR_NEALFANUM.sub(" ", text)
    return _VZOR_VICE_MEZER.sub(" ", bez_znaku).strip()


def normalizuj_pro_embedding(text: str | None) -> str:
    if not text:
        return ""
    vysledek = str(text).strip()
    vysledek = normalizuj_jednotky(vysledek)
    vysledek = rozvin_zkratky(vysledek)
    vysledek = vycisti_text(vysledek)
    return vysledek.lower()


def normalizuj_pro_lexikalni(text: str | None) -> str:
    if not text:
        return ""
    return odstran_diakritiku(normalizuj_pro_embedding(text))


def sestav_reprezentaci(
    zaznam: Mapping[str, object],
    pole: Iterable[str],
    oddelovac: str = " | ",
) -> str:
    casti: list[str] = []
    for nazev_pole in pole:
        hodnota = zaznam.get(nazev_pole)
        if hodnota is None:
            continue
        text = str(hodnota).strip()
        if text and text.lower() not in {"nan", "none", "null"}:
            casti.append(text)
    return oddelovac.join(casti)
