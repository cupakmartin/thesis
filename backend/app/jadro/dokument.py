# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import re
from dataclasses import dataclass

MAX_ZNAKU_USEKU = 1200
MAX_ZNAKU_DOKUMENTU = 100_000
MAX_VELIKOST_PDF = 15 * 1024 * 1024

ZNACKA_SEZNAMU = re.compile(
    r"^(?:[-–-•●◦▪■□‣⁃∙➢✓✔*·►]|\(?\d{1,3}(?:\.\d{1,3})*[.)]|\(?[a-z]\))\s+"
)

ODRAZKA_PISMA_SYMBOL = re.compile(r"^[-]\s*")
VODICI_TECKY = re.compile(r"\s*(?:[.…·]\s*){4,}\d{0,4}\s*$")
CISLO_STRANY = re.compile(
    r"^[-–\s]*(?:(?:page|strana|str\.?|s\.)\s*)?\d{1,4}"
    r"(?:\s*(?:/|of|z|ze|from)\s*\d{1,4})?[-–\s]*$",
    re.IGNORECASE,
)
KONEC_VETY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9„\"(\[])")
SLOVO = re.compile(r"\b[^\W\d_]{2,}\b")


class ChybaDokumentu(ValueError):
    pass


@dataclass(frozen=True)
class TextDokumentu:
    text: str
    pocet_stran: int


@dataclass(frozen=True)
class Usek:
    poradi: int
    radek: int
    odrazka: str
    text: str
    prelozit: bool


def vytez_text_z_pdf(data: bytes) -> TextDokumentu:
    if len(data) > MAX_VELIKOST_PDF:
        raise ChybaDokumentu(
            f"Soubor PDF je větší než {MAX_VELIKOST_PDF // (1024 * 1024)} MB."
        )
    if not data.lstrip().startswith(b"%PDF-"):
        raise ChybaDokumentu("Soubor není ve formátu PDF.")

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        ctenar = PdfReader(io.BytesIO(data))
        if ctenar.is_encrypted and not ctenar.decrypt(""):
            raise ChybaDokumentu("Soubor PDF je chráněn heslem.")
        stranky = [stranka.extract_text() or "" for stranka in ctenar.pages]
    except PdfReadError as chyba:
        raise ChybaDokumentu(f"Soubor PDF se nepodařilo přečíst: {chyba}") from chyba

    text = normalizuj_text_stranek(stranky)
    if not SLOVO.search(text):
        raise ChybaDokumentu(
            "PDF neobsahuje textovou vrstvu - pravděpodobně jde o naskenovaný "
            "dokument. Rozpoznávání textu z obrázku (OCR) není součástí řešení."
        )
    return TextDokumentu(text=text, pocet_stran=len(stranky))


def _klic_radku(radek: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", radek)).strip().lower()


def _opakovane_okraje(stranky: list[list[str]]) -> set[str]:
    vyskyty: dict[str, int] = {}
    for radky in stranky:
        if not radky:
            continue
        for klic in {_klic_radku(radky[0]), _klic_radku(radky[-1])}:
            if klic:
                vyskyty[klic] = vyskyty.get(klic, 0) + 1
    return {klic for klic, pocet in vyskyty.items() if pocet >= 3}


def _je_pokracovani(predchozi: str, radek: str, plna_sirka: float) -> bool:
    if ZNACKA_SEZNAMU.match(radek):
        return False
    if predchozi.endswith((".", "!", "?", ":", ";")):
        return False
    if radek[:1].islower() or radek[:1] in ",;.)":
        return True
    return len(predchozi) >= plna_sirka


def normalizuj_text_stranek(stranky: list[str]) -> str:
    radky_stran = []
    for stranka in stranky:
        ocistene = [
            ODRAZKA_PISMA_SYMBOL.sub("• ", re.sub(r"[ \t]{2,}", " ", r).strip())
            for r in stranka.splitlines()
        ]
        radky_stran.append([r for r in ocistene if r and not CISLO_STRANY.match(r)])

    okraje = _opakovane_okraje(radky_stran)
    videne_okraje: set[str] = set()
    radky: list[tuple[str, bool]] = []
    for stranka in radky_stran:
        for poradi, radek in enumerate(stranka):
            klic = _klic_radku(radek)
            if poradi in (0, len(stranka) - 1) and klic in okraje:
                if klic not in videne_okraje:
                    videne_okraje.add(klic)
                    radky.append((radek, True))
                continue
            if VODICI_TECKY.search(radek):
                polozka_obsahu = VODICI_TECKY.sub("", radek)
                if polozka_obsahu:
                    radky.append((polozka_obsahu, True))
                continue
            radky.append((radek, False))

    delky = sorted(len(r) for r, pevny in radky if not pevny)
    if not delky:
        return "\n".join(r for r, _ in radky)
    plna_sirka = 0.85 * delky[int(0.8 * (len(delky) - 1))]

    odstavce: list[str] = []
    posledni_radek = ""
    lze_navazat = False
    for radek, pevny in radky:
        if lze_navazat and not pevny and _je_pokracovani(
                posledni_radek, radek, plna_sirka):
            if (posledni_radek.endswith("-") and len(posledni_radek) > 1
                    and posledni_radek[-2].isalpha() and radek[:1].islower()):
                odstavce[-1] = odstavce[-1][:-1] + radek
            else:
                odstavce[-1] = odstavce[-1] + " " + radek
        else:
            odstavce.append(radek)
        posledni_radek = radek
        lze_navazat = not pevny
    return "\n".join(odstavce)


def _rozdel_odstavec(text: str, max_znaku: int) -> list[str]:
    if len(text) <= max_znaku:
        return [text]
    casti: list[str] = []
    aktualni = ""
    for veta in KONEC_VETY.split(text):
        if aktualni and len(aktualni) + 1 + len(veta) > max_znaku:
            casti.append(aktualni)
            aktualni = veta
        else:
            aktualni = f"{aktualni} {veta}" if aktualni else veta
    if aktualni:
        casti.append(aktualni)
    return casti


def rozdel_na_useky(text: str, max_znaku: int = MAX_ZNAKU_USEKU) -> list[Usek]:
    useky: list[Usek] = []
    radky = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for cislo_radku, radek in enumerate(radky):
        obsah = radek.strip()
        shoda = ZNACKA_SEZNAMU.match(obsah)
        odrazka = shoda.group(0) if shoda else ""
        obsah = obsah[len(odrazka):].strip()
        odrazka = radek[: len(radek) - len(radek.lstrip())] + odrazka

        if not SLOVO.search(obsah):
            useky.append(Usek(len(useky), cislo_radku, odrazka, obsah, False))
            continue
        for poradi_casti, cast in enumerate(_rozdel_odstavec(obsah, max_znaku)):
            useky.append(Usek(
                len(useky), cislo_radku, odrazka if poradi_casti == 0 else "",
                cast, True,
            ))
    return useky


def sestav_preklad(useky: list[Usek], preklady: dict[int, str]) -> str:
    if not useky:
        return ""
    radky: dict[int, list[Usek]] = {}
    for usek in useky:
        radky.setdefault(usek.radek, []).append(usek)

    vystup: list[str] = []
    for cislo_radku in range(max(radky) + 1):
        casti = radky.get(cislo_radku, [])
        if not casti:
            vystup.append("")
            continue
        texty = [
            preklady.get(u.poradi, u.text) if u.prelozit else u.text
            for u in casti
        ]
        vystup.append(casti[0].odrazka + " ".join(t for t in texty if t))
    return "\n".join(vystup)
