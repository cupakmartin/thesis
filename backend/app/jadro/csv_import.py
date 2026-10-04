# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from app.jadro.normalizace import odstran_diakritiku

ODDELOVACE = ";,\t|"
MAX_HODNOT = 30
POCET_PRIKLADU = 3

ROLE_ID = "id"
ROLE_POPIS = "popis"
ROLE_JAZYK = "jazyk"
ROLE_SKUPINA = "skupina"
ROLE_TRIDA = "trida"
ROLE: tuple[str, ...] = (ROLE_ID, ROLE_POPIS, ROLE_JAZYK, ROLE_SKUPINA, ROLE_TRIDA)

NAZVY_ID = {
    "itemnum", "id", "kod", "code", "itemid", "cislo", "cislopolozky", "partnumber",
    "partno", "pn", "sku", "material", "materialnumber", "artikel", "artikelnummer",
}
ZACATKY_POPISU = (
    "description", "popis", "nazev", "name", "bezeichnung", "descrizione",
    "descripcion", "designation", "libelle",
)
NAZVY_JAZYKA = {
    "langcode", "lang", "language", "jazyk", "kodjazyka", "sprache", "lingua",
    "idioma", "langue",
}
NAZVY_SKUPINY = {
    "commoditygroup", "commodity", "kategorie", "category", "skupina", "group",
    "warengruppe", "kategorie polozky",
}
NAZVY_TRIDY = {"isoclass", "iso", "isotrida", "iso14224", "tridaiso"}

PRIPONA_JAZYKA = re.compile(
    r"[\s_\-\(\[\.](en|cs|cz|de|it|es|fr|zh|cn|ja|jp)[\)\]]?$", re.IGNORECASE
)
PREVOD_PRIPONY = {"cz": "cs", "cn": "zh", "jp": "ja"}

ZNAMENI_JAZYKA: dict[str, set[str]] = {
    "cs": {"cs", "cz", "cze", "ces", "czech", "cestina", "cesky"},
    "en": {"en", "eng", "english", "anglictina", "anglicky", "gb", "uk", "us"},
    "de": {"de", "ger", "deu", "german", "deutsch", "nemcina", "nemecky"},
    "it": {"it", "ita", "italian", "italiano", "italstina", "italsky"},
    "es": {"es", "spa", "spanish", "espanol", "spanelstina", "spanelsky"},
    "fr": {"fr", "fre", "fra", "french", "francais", "francouzstina", "francouzsky"},
    "zh": {"zh", "cn", "chi", "zho", "chinese", "cinstina", "cinsky", "中文", "汉语", "漢語"},
    "ja": {"ja", "jp", "jpn", "japanese", "japonstina", "japonsky", "日本語"},
}


class ChybaCsv(ValueError):
    pass


@dataclass
class ObsahCsv:
    sloupce: list[str]
    radky: list[list[str]]
    kodovani: str
    oddelovac: str
    radku_s_prebytkem: int = 0


@dataclass
class NavrhSloupce:
    index: int
    puvodni: str
    navrh_role: str
    navrh_jazyk: str
    priklady: list[str]
    hodnoty: list[str] | None
    unikatni: bool
    prazdnych: int


def _klic(nazev: str) -> str:
    return re.sub(r"[^a-z0-9]", "", odstran_diakritiku(nazev).lower())


def _dekoduj(data: bytes, kodovani: str | None) -> tuple[str, str]:
    if kodovani:
        try:
            text = data.decode(kodovani)
        except (UnicodeDecodeError, LookupError) as chyba:
            raise ChybaCsv(f"Soubor nelze přečíst v kódování {kodovani}.") from chyba
        return text.lstrip("﻿"), kodovani
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1250", errors="replace"), "cp1250"


def _odhadni_oddelovac(text: str) -> str:
    radky = text.splitlines()
    hlavicka = radky[0] if radky else ""
    try:
        oddelovac = csv.Sniffer().sniff("\n".join(radky[:20]), delimiters=ODDELOVACE).delimiter
        if oddelovac in hlavicka:
            return oddelovac
    except csv.Error:
        pass
    pocty = {o: hlavicka.count(o) for o in ODDELOVACE}
    nejcastejsi = max(pocty, key=lambda o: pocty[o])
    return nejcastejsi if pocty[nejcastejsi] else ";"


def _pojmenuj(hlavicka: list[str]) -> list[str]:
    nazvy: list[str] = []
    for poradi, nazev in enumerate(hlavicka):
        zaklad = nazev.strip().lstrip("﻿") or f"Sloupec {poradi + 1}"
        kandidat, cislo = zaklad, 2
        while kandidat in nazvy:
            kandidat = f"{zaklad} ({cislo})"
            cislo += 1
        nazvy.append(kandidat)
    return nazvy


def nacti_csv(
    data: bytes,
    kodovani: str | None = None,
    oddelovac: str | None = None,
) -> ObsahCsv:
    if not data.strip():
        raise ChybaCsv("Soubor je prázdný.")
    text, pouzite_kodovani = _dekoduj(data, kodovani)
    pouzity_oddelovac = oddelovac or _odhadni_oddelovac(text)

    radky = [
        radek for radek in csv.reader(io.StringIO(text), delimiter=pouzity_oddelovac)
        if any(bunka.strip() for bunka in radek)
    ]
    if not radky:
        raise ChybaCsv("Soubor je prázdný.")

    sloupce = _pojmenuj(radky[0])
    pocet = len(sloupce)
    telo = [
        [b.strip() for b in radek[:pocet]] + [""] * (pocet - len(radek))
        for radek in radky[1:]
    ]
    if not telo:
        raise ChybaCsv("Soubor obsahuje jen řádek s názvy sloupců, žádný záznam.")
    prebytek = sum(1 for radek in radky[1:] if len(radek) > pocet)
    return ObsahCsv(sloupce, telo, pouzite_kodovani, pouzity_oddelovac, prebytek)


def rozpoznej_jazyk(hodnota: str) -> str:
    cista = hodnota.strip()
    if not cista:
        return ""
    for kandidat in (cista, re.split(r"[-_\s]", cista)[0]):
        klic = odstran_diakritiku(kandidat).lower()
        for kod, znameni in ZNAMENI_JAZYKA.items():
            if klic in znameni or kandidat in znameni:
                return kod
    return ""


def _navrhni_roli(nazev: str, popis_uz_je: bool) -> str:
    klic = _klic(nazev)
    if klic in NAZVY_ID:
        return ROLE_ID
    if klic in NAZVY_JAZYKA:
        return ROLE_JAZYK
    if klic in NAZVY_TRIDY:
        return ROLE_TRIDA
    if klic in {_klic(n) for n in NAZVY_SKUPINY}:
        return ROLE_SKUPINA
    if not popis_uz_je and klic.startswith(ZACATKY_POPISU):
        return ROLE_POPIS
    return ""


def _navrhni_jazyk(nazev: str) -> str:
    shoda = PRIPONA_JAZYKA.search(nazev.strip())
    if not shoda:
        return ""
    kod = shoda.group(1).lower()
    return PREVOD_PRIPONY.get(kod, kod)


def navrhni_sloupce(obsah: ObsahCsv) -> list[NavrhSloupce]:
    navrhy: list[NavrhSloupce] = []
    popis_uz_je = False
    for index, nazev in enumerate(obsah.sloupce):
        hodnoty = [radek[index] for radek in obsah.radky]
        neprazdne = [h for h in hodnoty if h]
        ruzne = sorted(set(neprazdne))
        role = _navrhni_roli(nazev, popis_uz_je)
        popis_uz_je = popis_uz_je or role == ROLE_POPIS
        navrhy.append(NavrhSloupce(
            index=index,
            puvodni=nazev,
            navrh_role=role,
            navrh_jazyk=_navrhni_jazyk(nazev),
            priklady=neprazdne[:POCET_PRIKLADU],
            hodnoty=ruzne if len(ruzne) <= MAX_HODNOT else None,
            unikatni=len(neprazdne) == len(hodnoty) and len(ruzne) == len(hodnoty),
            prazdnych=len(hodnoty) - len(neprazdne),
        ))
    return navrhy
