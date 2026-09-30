# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import nastaveni

logger = logging.getLogger(__name__)

_zamek_zapisu = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS polozky (
    itemnum            TEXT PRIMARY KEY,
    description        TEXT NOT NULL,
    long_description   TEXT,
    itemtype           TEXT,
    commodity_group    TEXT,
    order_unit         TEXT,
    issue_unit         TEXT,
    status             TEXT,
    rotating           INTEGER DEFAULT 0,
    manufacturer       TEXT,
    model_num          TEXT,
    vendor             TEXT,
    external_ref_id    TEXT,
    iso_class          TEXT,
    lang_code          TEXT,
    change_date        TEXT,
    change_by          TEXT,
    stav_konsolidace   TEXT NOT NULL DEFAULT 'aktivni',
    slouceno_do        TEXT,
    poradi             INTEGER
);

CREATE INDEX IF NOT EXISTS idx_polozky_skupina ON polozky(commodity_group);
CREATE INDEX IF NOT EXISTS idx_polozky_trida   ON polozky(iso_class);
CREATE INDEX IF NOT EXISTS idx_polozky_stav    ON polozky(stav_konsolidace);

CREATE TABLE IF NOT EXISTS behy (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    zalozeno           TEXT NOT NULL,
    dokonceno          TEXT,
    stav               TEXT NOT NULL DEFAULT 'probiha',
    metoda             TEXT NOT NULL,
    nastaveni_json     TEXT NOT NULL,
    pocet_polozek      INTEGER DEFAULT 0,
    pocet_klastru      INTEGER DEFAULT 0,
    pocet_duplicit     INTEGER DEFAULT 0,
    doba_s             REAL DEFAULT 0,
    spustil            TEXT,
    chyba              TEXT
);

CREATE TABLE IF NOT EXISTS klastry (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    beh_id             INTEGER NOT NULL REFERENCES behy(id) ON DELETE CASCADE,
    poradi             INTEGER NOT NULL,
    velikost           INTEGER NOT NULL,
    prumerna_podobnost REAL NOT NULL,
    minimalni_podobnost REAL NOT NULL,
    navrzeny_zastupce  TEXT,
    stav               TEXT NOT NULL DEFAULT 'ke_kontrole'
);

CREATE INDEX IF NOT EXISTS idx_klastry_beh ON klastry(beh_id);

CREATE TABLE IF NOT EXISTS klastr_cleny (
    klastr_id          INTEGER NOT NULL REFERENCES klastry(id) ON DELETE CASCADE,
    itemnum            TEXT NOT NULL,
    PRIMARY KEY (klastr_id, itemnum)
);

CREATE TABLE IF NOT EXISTS dvojice (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    klastr_id          INTEGER NOT NULL REFERENCES klastry(id) ON DELETE CASCADE,
    itemnum_a          TEXT NOT NULL,
    itemnum_b          TEXT NOT NULL,
    podobnost_semanticka REAL NOT NULL,
    podobnost_lexikalni  REAL NOT NULL,
    skore_atributu     REAL NOT NULL,
    skore              REAL NOT NULL,
    vysvetleni         TEXT
);

CREATE INDEX IF NOT EXISTS idx_dvojice_klastr ON dvojice(klastr_id);

CREATE TABLE IF NOT EXISTS rozhodnuti (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    klastr_id          INTEGER NOT NULL REFERENCES klastry(id) ON DELETE CASCADE,
    -- schvaleno | zamitnuto | odlozeno
    vysledek           TEXT NOT NULL,
    zastupce           TEXT,
    upraveny_popis     TEXT,
    poznamka           TEXT,
    rozhodl            TEXT NOT NULL,
    rozhodnuto         TEXT NOT NULL,
    vzato_zpet         INTEGER NOT NULL DEFAULT 0,
    vzal_zpet          TEXT,
    vzato_zpet_kdy     TEXT
);

CREATE INDEX IF NOT EXISTS idx_rozhodnuti_klastr ON rozhodnuti(klastr_id);

CREATE TABLE IF NOT EXISTS preklady (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    vytvoreno          TEXT NOT NULL,
    zdrojovy_text      TEXT NOT NULL,
    preklad            TEXT NOT NULL,
    zdrojovy_jazyk     TEXT NOT NULL,
    cilovy_jazyk       TEXT NOT NULL,
    pouzity_glosar     INTEGER NOT NULL,
    model              TEXT,
    doba_s             REAL,
    terminy_json       TEXT,
    mira_dodrzeni      REAL,
    validace_json      TEXT,
    itemnum            TEXT,
    vytvoril           TEXT
);

CREATE INDEX IF NOT EXISTS idx_preklady_polozka ON preklady(itemnum);

CREATE TABLE IF NOT EXISTS mif_udalosti (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    prijato            TEXT NOT NULL,
    typ_udalosti       TEXT NOT NULL,
    itemnum            TEXT,
    obsah_json         TEXT NOT NULL,
    zpracovano         INTEGER NOT NULL DEFAULT 0,
    vysledek_json      TEXT,
    chyba              TEXT
);

CREATE TABLE IF NOT EXISTS volby (
    klic               TEXT PRIMARY KEY,
    hodnota            TEXT NOT NULL,
    zmeneno            TEXT NOT NULL,
    kdo                TEXT
);
"""


def nyni() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def cesta_databaze() -> Path:
    return nastaveni().soubor_databaze


@contextmanager
def pripoj(pouze_cteni: bool = False) -> Iterator[sqlite3.Connection]:
    cesta = cesta_databaze()
    cesta.parent.mkdir(parents=True, exist_ok=True)

    spojeni = sqlite3.connect(cesta, timeout=30.0)
    spojeni.row_factory = sqlite3.Row
    spojeni.execute("PRAGMA foreign_keys = ON")
    spojeni.execute("PRAGMA journal_mode = WAL")

    try:
        if pouze_cteni:
            yield spojeni
        else:
            with _zamek_zapisu:
                yield spojeni
                spojeni.commit()
    except Exception:
        spojeni.rollback()
        raise
    finally:
        spojeni.close()


def inicializuj_schema() -> None:
    with pripoj() as spojeni:
        spojeni.executescript(SCHEMA)
    logger.info("Schéma databáze připraveno (%s).", cesta_databaze())


def precti_volbu(klic: str) -> str | None:
    with pripoj(pouze_cteni=True) as spojeni:
        radek = spojeni.execute(
            "SELECT hodnota FROM volby WHERE klic = ?", (klic,)
        ).fetchone()
    return radek["hodnota"] if radek else None


def uloz_volbu(klic: str, hodnota: str, kdo: str | None = None) -> None:
    with pripoj() as spojeni:
        spojeni.execute(
            "INSERT INTO volby (klic, hodnota, zmeneno, kdo) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(klic) DO UPDATE SET "
            "hodnota = excluded.hodnota, zmeneno = excluded.zmeneno, kdo = excluded.kdo",
            (klic, hodnota, nyni(), kdo),
        )


def smaz_volbu(klic: str) -> None:
    with pripoj() as spojeni:
        spojeni.execute("DELETE FROM volby WHERE klic = ?", (klic,))


def smaz_vse() -> None:
    with pripoj() as spojeni:
        for tabulka in (
            "mif_udalosti", "preklady", "rozhodnuti", "dvojice",
            "klastr_cleny", "klastry", "behy", "polozky",
        ):
            spojeni.execute(f"DELETE FROM {tabulka}")
