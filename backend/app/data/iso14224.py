# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TridaZarizeni:
    kod: str
    nazev_en: str
    nazev_cs: str
    kategorie: str
    podtridy: tuple[str, ...] = field(default=())


TRIDY_ZARIZENI: tuple[TridaZarizeni, ...] = (
    TridaZarizeni("CO", "Compressors", "Kompresory", "rotační",
                  ("centrifugal", "reciprocating", "screw", "axial")),
    TridaZarizeni("PU", "Pumps", "Čerpadla", "rotační",
                  ("centrifugal", "reciprocating", "rotary")),
    TridaZarizeni("GT", "Gas turbines", "Plynové turbíny", "rotační",
                  ("industrial", "aeroderivative")),
    TridaZarizeni("ST", "Steam turbines", "Parní turbíny", "rotační",
                  ("condensing", "back pressure")),
    TridaZarizeni("CE", "Combustion engines", "Spalovací motory", "rotační",
                  ("diesel", "gas", "dual fuel")),
    TridaZarizeni("EG", "Electric generators", "Elektrické generátory", "rotační",
                  ("synchronous", "asynchronous")),
    TridaZarizeni("EM", "Electric motors", "Elektromotory", "rotační",
                  ("induction", "synchronous", "dc")),
    TridaZarizeni("TE", "Turboexpanders", "Turboexpandéry", "rotační", ()),
    TridaZarizeni("FN", "Fans", "Ventilátory", "rotační",
                  ("axial", "centrifugal")),

    TridaZarizeni("HE", "Heat exchangers", "Výměníky tepla", "mechanická",
                  ("shell and tube", "plate", "air cooled")),
    TridaZarizeni("VE", "Vessels", "Tlakové nádoby", "mechanická",
                  ("separator", "column", "tank")),
    TridaZarizeni("PI", "Piping", "Potrubí", "mechanická",
                  ("pipe", "flange", "fitting")),
    TridaZarizeni("VA", "Valves", "Armatury", "mechanická",
                  ("ball", "gate", "globe", "check", "butterfly", "safety")),
    TridaZarizeni("HB", "Heaters and boilers", "Ohříváky a kotle", "mechanická",
                  ("fired heater", "boiler")),
    TridaZarizeni("CR", "Cranes", "Jeřáby", "mechanická",
                  ("gantry", "jib", "overhead")),
    TridaZarizeni("WI", "Winches", "Navijáky", "mechanická", ()),
    TridaZarizeni("FI", "Filters", "Filtry", "mechanická",
                  ("oil", "air", "fuel", "hydraulic")),
    TridaZarizeni("GB", "Gearboxes", "Převodovky", "mechanická",
                  ("helical", "worm", "planetary")),

    TridaZarizeni("PT", "Power transformers", "Výkonové transformátory", "elektrická",
                  ("oil immersed", "dry type")),
    TridaZarizeni("FC", "Frequency converters", "Frekvenční měniče", "elektrická", ()),
    TridaZarizeni("SG", "Switchgear", "Rozváděče", "elektrická",
                  ("low voltage", "medium voltage", "high voltage")),
    TridaZarizeni("UP", "Uninterruptible power supplies", "Zdroje nepřerušovaného napájení",
                  "elektrická", ()),

    TridaZarizeni("PS", "Process sensors", "Procesní snímače", "řídicí",
                  ("pressure", "temperature", "flow", "level")),
    TridaZarizeni("FG", "Fire and gas detectors", "Detektory požáru a plynu", "bezpečnostní",
                  ("flame", "smoke", "gas", "heat")),
    TridaZarizeni("CL", "Control logic units", "Řídicí jednotky", "řídicí", ()),
    TridaZarizeni("VS", "Valve actuators", "Pohony armatur", "řídicí",
                  ("electric", "pneumatic", "hydraulic")),
)

TRIDY_PODLE_KODU: dict[str, TridaZarizeni] = {t.kod: t for t in TRIDY_ZARIZENI}

DRUHY_PORUCH: tuple[tuple[str, str, str], ...] = (
    ("AIR", "Abnormal instrument reading", "Abnormální údaj přístroje"),
    ("BRD", "Breakdown", "Havárie"),
    ("ELF", "External leakage - fuel", "Vnější únik - palivo"),
    ("ELP", "External leakage - process medium", "Vnější únik - procesní médium"),
    ("ELU", "External leakage - utility medium", "Vnější únik - pomocné médium"),
    ("ERO", "Erratic output", "Kolísavý výstup"),
    ("FTS", "Fail to start on demand", "Nespuštění na vyžádání"),
    ("HIO", "High output", "Zvýšený výstup"),
    ("INL", "Internal leakage", "Vnitřní netěsnost"),
    ("LOO", "Low output", "Snížený výstup"),
    ("NOI", "Noise", "Hluk"),
    ("OHE", "Overheating", "Přehřívání"),
    ("PDE", "Parameter deviation", "Odchylka parametru"),
    ("PLU", "Plugged / choked", "Ucpání"),
    ("SER", "Minor in-service problems", "Drobné provozní závady"),
    ("STD", "Structural deficiency", "Konstrukční nedostatek"),
    ("STP", "Fail to stop on demand", "Nezastavení na vyžádání"),
    ("UST", "Spurious stop", "Neplánované zastavení"),
    ("VIB", "Vibration", "Vibrace"),
    ("OTH", "Other", "Jiné"),
    ("UNK", "Unknown", "Neznámé"),
)

UDRZBOVE_CINNOSTI: tuple[tuple[str, str, str], ...] = (
    ("RPR", "Repair", "Oprava"),
    ("RPL", "Replace", "Výměna"),
    ("ADJ", "Adjust", "Seřízení"),
    ("CHE", "Check", "Kontrola"),
    ("SER", "Service", "Servis"),
    ("TES", "Test", "Zkouška"),
    ("INS", "Inspection", "Inspekce"),
    ("OVH", "Overhaul", "Generální oprava"),
    ("COM", "Combination", "Kombinovaný zásah"),
    ("OTH", "Other", "Jiné"),
)


def trida_podle_kodu(kod: str) -> TridaZarizeni | None:
    return TRIDY_PODLE_KODU.get(kod.strip().upper())


def seznam_kodu() -> list[str]:
    return [t.kod for t in TRIDY_ZARIZENI]


def popis_tridy(kod: str, jazyk: str = "cs") -> str:
    trida = trida_podle_kodu(kod)
    if trida is None:
        return kod
    return trida.nazev_cs if jazyk == "cs" else trida.nazev_en


def prehled_pro_prompt() -> str:
    radky = [f"{t.kod} = {t.nazev_en} / {t.nazev_cs}" for t in TRIDY_ZARIZENI]
    return "\n".join(radky)
