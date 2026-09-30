# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.jadro.normalizace import normalizuj_jednotky, odstran_diakritiku

_VZOR_DN = re.compile(r"\bdn\s*(\d+)\b")
_VZOR_PN = re.compile(r"\bpn\s*(\d+)\b")
_VZOR_IP = re.compile(r"\bip\s*(\d{2})\b")

_VZOR_ZAVIT = re.compile(r"\b(m\d+(?:x\d+(?:\.\d+)?)?|g\d+/\d+)\b")
_VZOR_ROZMER = re.compile(r"\b(\d+(?:\.\d+)?(?:\s*[x/]\s*\d+(?:\.\d+)?)+)\b")
_VZOR_VELICINA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[,;/-]?\s*(mm|cm|kw|kg|bar|psi|rpm|m3/h|um|w|v|a|k|t|l|m)\b"
)
_VZOR_NORMA = re.compile(r"\b(din|iso|en|csn)\s*(\d{2,5})\b")
_VZOR_KOD_ALFANUM = re.compile(r"\b([a-z]{2,4}\d{1,6}[a-z]?|\d{2,3}[a-z]{1,2})\b")
_VZOR_KOD_CISELNY = re.compile(r"\b(\d{4,6})\b")

MATERIALOVE_KODY: frozenset[str] = frozenset({
    "a2", "a4", "nbr", "fpm", "fkm", "epdm", "ptfe",
    "gg", "am", "b3", "b5", "b14",
})
_VZOR_MATERIAL = re.compile(
    r"\b(" + "|".join(sorted(MATERIALOVE_KODY, key=len, reverse=True)) + r")\b"
)
SJEDNOCENI_JEDNOTEK: dict[str, str] = {
    "rpm": "rpm",
    "um": "um",
    "m3/h": "m3/h",
}

KANONICKE_PROVEDENI: dict[str, str] = {
    "nerezova ocel": "nerez", "stainless steel": "nerez", "stainless": "nerez",
    "nerez": "nerez",
    "litina": "litina", "cast iron": "litina",
    "mosaz": "mosaz", "brass": "mosaz",
    "bronz": "bronz", "bronze": "bronz",
    "uhlikova ocel": "ocel_uhlikova", "carbon steel": "ocel_uhlikova",
    "pozink": "pozink", "pozinkovany": "pozink", "zinc plated": "pozink",
    "grafit": "grafit", "graphite": "grafit",
    "klingerit": "klingerit",
    "silikon": "silikon", "silicone": "silikon",
    "prime": "prime", "straight": "prime",
    "koleno": "koleno", "elbow": "koleno",
    "t-kus": "tkus", "tee": "tkus",
    "krkova": "krkova", "weld neck": "krkova",
    "plocha": "plocha", "slip on": "plocha",
    "valec": "valec", "cylinder": "valec",
    "cerpadlo": "cerpadlo", "pump": "cerpadlo",
    "otevrene": "kryti_otevrene", "open": "kryti_otevrene",
    "2rs": "kryti_2rs", "zz": "kryti_zz",
    "vnejsi": "vnejsi", "external": "vnejsi",
    "vnitrni": "vnitrni", "internal": "vnitrni",
    "pravotocive": "pravotocive", "right hand": "pravotocive",
    "levotocive": "levotocive", "left hand": "levotocive",
}

_VZOR_PROVEDENI = re.compile(
    r"(?<![a-z])(" + "|".join(
        re.escape(k) for k in sorted(KANONICKE_PROVEDENI, key=len, reverse=True)
    ) + r")(?![a-z])"
)

_NEKODY: frozenset[str] = frozenset({
    "din", "iso", "en", "csn", "dn", "pn", "ip", "m3", "mm", "cm", "kw",
})


@dataclass(frozen=True)
class Atributy:
    dn: frozenset[str] = field(default_factory=frozenset)
    pn: frozenset[str] = field(default_factory=frozenset)
    ip: frozenset[str] = field(default_factory=frozenset)
    zavity: frozenset[str] = field(default_factory=frozenset)
    rozmery: frozenset[str] = field(default_factory=frozenset)
    normy: frozenset[str] = field(default_factory=frozenset)
    kody: frozenset[str] = field(default_factory=frozenset)
    materialy: frozenset[str] = field(default_factory=frozenset)
    provedeni: frozenset[str] = field(default_factory=frozenset)
    veliciny: frozenset[tuple[str, float]] = field(default_factory=frozenset)
    cisla: frozenset[float] = field(default_factory=frozenset)

    def je_prazdna(self) -> bool:
        return not any((
            self.dn, self.pn, self.ip, self.zavity, self.rozmery,
            self.normy, self.kody, self.materialy, self.provedeni,
            self.veliciny, self.cisla,
        ))

    def pocet(self) -> int:
        return (
            len(self.dn) + len(self.pn) + len(self.ip) + len(self.zavity)
            + len(self.rozmery) + len(self.normy) + len(self.kody)
            + len(self.materialy) + len(self.provedeni) + len(self.veliciny)
            + len(self.cisla)
        )

    def jako_slovnik(self) -> dict[str, list]:
        return {
            "dn": sorted(self.dn),
            "pn": sorted(self.pn),
            "ip": sorted(self.ip),
            "zavity": sorted(self.zavity),
            "rozmery": sorted(self.rozmery),
            "normy": sorted(self.normy),
            "kody": sorted(self.kody),
            "materialy": sorted(self.materialy),
            "provedeni": sorted(self.provedeni),
            "veliciny": sorted(f"{h} {j}" for j, h in self.veliciny),
            "cisla": sorted(self.cisla),
        }


def _normalizuj_rozmer(text: str) -> str:
    bez_mezer = re.sub(r"\s*([x/])\s*", r"\1", text)
    return bez_mezer.replace("/", "x")


def _hodnota_cisla(text: str) -> float:
    return float(text.replace(",", "."))


def vytez_atributy(popis: str) -> Atributy:
    if not popis:
        return Atributy()
    text = odstran_diakritiku(normalizuj_jednotky(str(popis))).lower()
    text = text.replace("ot/min", "rpm").replace("µm", "um")

    zbytek = text

    def _vyber(vzor: re.Pattern[str]) -> list[re.Match[str]]:

        nonlocal zbytek
        shody = list(vzor.finditer(zbytek))
        if shody:
            zbytek = vzor.sub(" ", zbytek)
        return shody

    dn = {s.group(1) for s in _vyber(_VZOR_DN)}
    pn = {s.group(1) for s in _vyber(_VZOR_PN)}
    ip = {s.group(1) for s in _vyber(_VZOR_IP)}
    normy = {f"{s.group(1)}{s.group(2)}" for s in _vyber(_VZOR_NORMA)}
    provedeni = {KANONICKE_PROVEDENI[s.group(1)] for s in _vyber(_VZOR_PROVEDENI)}
    materialy = {s.group(1) for s in _vyber(_VZOR_MATERIAL)}
    zavity = {s.group(1).replace(" ", "") for s in _vyber(_VZOR_ZAVIT)}
    rozmery = {_normalizuj_rozmer(s.group(1)) for s in _vyber(_VZOR_ROZMER)}

    veliciny: set[tuple[str, float]] = set()
    for shoda in _vyber(_VZOR_VELICINA):
        jednotka = SJEDNOCENI_JEDNOTEK.get(shoda.group(2), shoda.group(2))
        veliciny.add((jednotka, _hodnota_cisla(shoda.group(1))))

    kody = {s.group(1) for s in _vyber(_VZOR_KOD_ALFANUM)}
    kody |= {s.group(1) for s in _vyber(_VZOR_KOD_CISELNY)}
    kody = {k for k in kody if k not in _NEKODY and k not in MATERIALOVE_KODY}
    cisla = {_hodnota_cisla(s) for s in re.findall(r"\b\d+(?:[.,]\d+)?\b", zbytek)}

    return Atributy(
        dn=frozenset(dn),
        pn=frozenset(pn),
        ip=frozenset(ip),
        zavity=frozenset(zavity),
        rozmery=frozenset(rozmery),
        normy=frozenset(normy),
        kody=frozenset(kody),
        materialy=frozenset(materialy),
        provedeni=frozenset(provedeni),
        veliciny=frozenset(veliciny),
        cisla=frozenset(cisla),
    )


@dataclass(frozen=True)
class VysledekPorovnani:
    rozpor: bool
    pocet_shod: int
    pocet_rozporu: int

    vysvetleni: tuple[str, ...] = field(default=())

    @property
    def skore(self) -> float:

        if self.rozpor:
            return 0.0
        if self.pocet_shod == 0:
            return 0.5
        return min(1.0, 0.5 + 0.1 * self.pocet_shod)

_NAZVY_ATRIBUTU: dict[str, str] = {
    "dn": "jmenovitá světlost",
    "pn": "jmenovitý tlak",
    "ip": "stupeň krytí",
    "zavity": "závit",
    "rozmery": "rozměr",
    "normy": "norma",
    "kody": "typové označení",
    "materialy": "materiálový kód",
    "provedeni": "materiál nebo provedení",
}


def porovnej_atributy(prvni: Atributy, druhy: Atributy) -> VysledekPorovnani:
    shody = 0
    rozpory = 0
    vysvetleni: list[str] = []

    for nazev_pole, popis_pole in _NAZVY_ATRIBUTU.items():
        hodnoty_a: frozenset[str] = getattr(prvni, nazev_pole)
        hodnoty_b: frozenset[str] = getattr(druhy, nazev_pole)
        if not hodnoty_a or not hodnoty_b:
            continue
        chybi_v_b = hodnoty_a - hodnoty_b
        chybi_v_a = hodnoty_b - hodnoty_a
        if chybi_v_a and chybi_v_b:
            rozpory += 1
            vysvetleni.append(
                f"{popis_pole}: {'/'.join(sorted(hodnoty_a))} "
                f"proti {'/'.join(sorted(hodnoty_b))}"
            )
        else:
            shody += len(hodnoty_a & hodnoty_b)

    jednotky_a = {j for j, _ in prvni.veliciny}
    jednotky_b = {j for j, _ in druhy.veliciny}
    for jednotka in jednotky_a & jednotky_b:
        hodnoty_a_v = {h for j, h in prvni.veliciny if j == jednotka}
        hodnoty_b_v = {h for j, h in druhy.veliciny if j == jednotka}
        if (hodnoty_a_v - hodnoty_b_v) and (hodnoty_b_v - hodnoty_a_v):
            rozpory += 1
            vysvetleni.append(
                f"hodnota v {jednotka}: "
                f"{'/'.join(str(h) for h in sorted(hodnoty_a_v))} proti "
                f"{'/'.join(str(h) for h in sorted(hodnoty_b_v))}"
            )
        else:
            shody += 1

    if prvni.cisla and druhy.cisla:
        chybi_v_b = prvni.cisla - druhy.cisla
        chybi_v_a = druhy.cisla - prvni.cisla
        if chybi_v_a and chybi_v_b:
            rozpory += 1
            vysvetleni.append(
                f"číselný údaj: {'/'.join(str(c) for c in sorted(prvni.cisla))} "
                f"proti {'/'.join(str(c) for c in sorted(druhy.cisla))}"
            )
        else:
            shody += len(prvni.cisla & druhy.cisla)

    return VysledekPorovnani(
        rozpor=rozpory > 0,
        pocet_shod=shody,
        pocet_rozporu=rozpory,
        vysvetleni=tuple(vysvetleni),
    )
