# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from app.config import nastaveni
from app.db import nyni, pripoj
from app.jadro.duplicity import (
    FAZE_DVOJICE,
    FAZE_HLEDANI,
    FAZE_PRIPRAVA,
    FAZE_SHLUKOVANI,
    KROK_HLASENI,
    METODA_HYBRIDNI,
    NastaveniDeduplikace,
    VysledekDeduplikace,
    ZaznamPolozky,
    najdi_duplicity,
)
from app.jadro.postup import SledovaniPostupu
from app.sluzby.katalog import FAZE_INDEX, FAZE_VEKTORY, SluzbaKatalogu, sluzba_katalogu

logger = logging.getLogger(__name__)

FAZE_ULOZENI = "ulozeni"
SEKUND_NA_VEKTOR = 0.016
SEKUND_NA_STAVBU_INDEXU = 0.00015
SEKUND_NA_PRIPRAVU = 0.00006
SEKUND_NA_HLEDANI = 0.00014
SEKUND_NA_DVOJICE = 0.0001
SEKUND_NA_SHLUKOVANI = 0.00002
SEKUND_NA_ULOZENI = 0.00005


def vychozi_nastaveni() -> NastaveniDeduplikace:
    konfigurace = nastaveni()
    return NastaveniDeduplikace(
        metoda=METODA_HYBRIDNI,
        prah_kandidatu=konfigurace.prah_kandidatu,
        prah_rozhodnuti=konfigurace.prah_podobnosti,
        pocet_sousedu=konfigurace.pocet_sousedu,
        uplatnit_atributy=True,
        omezit_na_tridu_iso=konfigurace.omezit_na_tridu_iso,
        prisne_shlukovani=konfigurace.prisne_shlukovani,
    )


def _skore_uplnosti(zaznam: dict[str, Any]) -> tuple:
    vyplnenost = sum(
        1 for klic in ("manufacturer", "model_num", "long_description",
                       "external_ref_id", "vendor")
        if (zaznam.get(klic) or "").strip()
    )
    return (
        1 if (zaznam.get("status") or "").upper() == "ACTIVE" else 0,
        vyplnenost,
        len((zaznam.get("description") or "")),
        zaznam.get("change_date") or "",
    )


def navrhni_zastupce(polozky: list[dict[str, Any]]) -> str:
    if not polozky:
        return ""
    nejlepsi = max(polozky, key=_skore_uplnosti)
    return str(nejlepsi["itemnum"])


class SluzbaDeduplikace:
    def __init__(self, katalog: SluzbaKatalogu | None = None) -> None:
        self._katalog = katalog or sluzba_katalogu()
        self.postup = SledovaniPostupu()

    def smaz_vsechny_behy(self) -> int:
        with pripoj() as spojeni:
            pocet = int(spojeni.execute("SELECT COUNT(*) FROM behy").fetchone()[0])
            spojeni.execute("DELETE FROM behy")
            spojeni.execute(
                "UPDATE polozky SET stav_konsolidace = 'aktivni', slouceno_do = NULL"
            )
        logger.info("Odstraněno %d běhů deduplikace.", pocet)
        return pocet

    def spust(
        self,
        konfigurace: NastaveniDeduplikace | None = None,
        kdo: str = "systém",
        nahradit: bool = True,
    ) -> int:
        konfigurace = konfigurace or vychozi_nastaveni()
        zaznamy = self._katalog.zaznamy()
        if not zaznamy:
            raise RuntimeError("Katalog je prázdný, deduplikaci nelze spustit.")

        pocet, chybejici, stavet_index = self._katalog.odhad_prace()
        faze: list[tuple[str, str, float]] = []
        if chybejici:
            faze.append((FAZE_VEKTORY, "Výpočet vektorových reprezentací",
                         chybejici * SEKUND_NA_VEKTOR))
        if stavet_index:
            faze.append((FAZE_INDEX, "Stavba indexu HNSW", pocet * SEKUND_NA_STAVBU_INDEXU))
        faze += [
            (FAZE_PRIPRAVA, "Příprava popisů a atributů", pocet * SEKUND_NA_PRIPRAVU),
            (FAZE_HLEDANI, "Hledání kandidátů v indexu", pocet * SEKUND_NA_HLEDANI),
            (FAZE_DVOJICE, "Posouzení kandidátních dvojic", pocet * SEKUND_NA_DVOJICE),
            (FAZE_SHLUKOVANI, "Sestavení skupin", pocet * SEKUND_NA_SHLUKOVANI),
            (FAZE_ULOZENI, "Uložení skupin", pocet * SEKUND_NA_ULOZENI),
        ]
        self.postup.zacni("deduplikace", faze)

        try:
            beh_id = self._spust_se_sledovanim(konfigurace, zaznamy, kdo, nahradit)
        except Exception as chyba:
            self.postup.selhej(str(chyba))
            raise
        self.postup.dokonci()
        return beh_id

    def _spust_se_sledovanim(
        self,
        konfigurace: NastaveniDeduplikace,
        zaznamy: list[ZaznamPolozky],
        kdo: str,
        nahradit: bool,
    ) -> int:
        vektory, index = self._katalog.zajisti_index(self.postup)
        if nahradit:
            self.smaz_vsechny_behy()

        with pripoj() as spojeni:
            kurzor = spojeni.execute(
                "INSERT INTO behy (zalozeno, stav, metoda, nastaveni_json, "
                "pocet_polozek, spustil) VALUES (?, 'probiha', ?, ?, ?, ?)",
                (nyni(), konfigurace.metoda,
                 json.dumps(asdict(konfigurace), ensure_ascii=False),
                 len(zaznamy), kdo),
            )
            beh_id = int(kurzor.lastrowid or 0)

        try:
            vysledek = najdi_duplicity(
                zaznamy, konfigurace, vektory=vektory, index=index, postup=self.postup
            )
        except Exception as chyba:
            with pripoj() as spojeni:
                spojeni.execute(
                    "UPDATE behy SET stav = 'chyba', dokonceno = ?, chyba = ? WHERE id = ?",
                    (nyni(), str(chyba), beh_id),
                )
            raise

        self._uloz_vysledek(beh_id, vysledek, zaznamy, kdo)
        return beh_id

    def _uloz_vysledek(
        self,
        beh_id: int,
        vysledek: VysledekDeduplikace,
        zaznamy: list[ZaznamPolozky],
        kdo: str,
    ) -> None:
        with pripoj(pouze_cteni=True) as spojeni:
            podrobnosti = {
                r["itemnum"]: dict(r)
                for r in spojeni.execute("SELECT * FROM polozky").fetchall()
            }

        self.postup.faze(FAZE_ULOZENI, len(vysledek.klastry))
        with pripoj() as spojeni:
            for poradi, klastr in enumerate(vysledek.klastry):
                if poradi % KROK_HLASENI == 0:
                    self.postup.posun(poradi)
                cisla_polozek = [zaznamy[i].itemnum for i in klastr.indexy]
                zastupce = navrhni_zastupce(
                    [podrobnosti[c] for c in cisla_polozek if c in podrobnosti]
                )

                kurzor = spojeni.execute(
                    "INSERT INTO klastry (beh_id, poradi, velikost, "
                    "prumerna_podobnost, minimalni_podobnost, navrzeny_zastupce) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (beh_id, klastr.id, klastr.velikost, klastr.prumerna_podobnost,
                     klastr.minimalni_podobnost, zastupce),
                )
                klastr_id = int(kurzor.lastrowid or 0)

                spojeni.executemany(
                    "INSERT INTO klastr_cleny (klastr_id, itemnum) VALUES (?, ?)",
                    [(klastr_id, c) for c in cisla_polozek],
                )

                spojeni.executemany(
                    "INSERT INTO dvojice (klastr_id, itemnum_a, itemnum_b, "
                    "podobnost_semanticka, podobnost_lexikalni, skore_atributu, "
                    "skore, vysvetleni) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (klastr_id, zaznamy[d.index_a].itemnum, zaznamy[d.index_b].itemnum,
                         d.podobnost_semanticka, d.podobnost_lexikalni,
                         d.skore_atributu, d.skore,
                         "; ".join(d.vysvetleni) if d.vysvetleni else None)
                        for d in klastr.dvojice
                    ],
                )

            spojeni.execute(
                "UPDATE behy SET stav = 'dokonceno', dokonceno = ?, pocet_klastru = ?, "
                "pocet_duplicit = ?, doba_s = ? WHERE id = ?",
                (nyni(), vysledek.pocet_klastru,
                 vysledek.pocet_duplicitnich_zaznamu, vysledek.doba_s, beh_id),
            )

        logger.info(
            "Běh %d dokončen: %d klastrů, %d duplicitních záznamů.",
            beh_id, vysledek.pocet_klastru, vysledek.pocet_duplicitnich_zaznamu,
        )

    def seznam_behu(self, limit: int = 50) -> list[dict[str, Any]]:
        with pripoj(pouze_cteni=True) as spojeni:
            radky = spojeni.execute(
                "SELECT * FROM behy ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in radky]

    def posledni_beh(self) -> dict[str, Any] | None:
        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                "SELECT * FROM behy WHERE stav = 'dokonceno' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(radek) if radek else None

    def klastry(
        self,
        beh_id: int,
        stav: str = "",
        limit: int = 50,
        odsazeni: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        podminky = ["beh_id = ?"]
        parametry: list[Any] = [beh_id]
        if stav:
            podminky.append("stav = ?")
            parametry.append(stav)
        klauzule = " WHERE " + " AND ".join(podminky)

        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute(
                f"SELECT COUNT(*) FROM klastry{klauzule}", parametry
            ).fetchone()[0])
            radky = spojeni.execute(
                f"SELECT * FROM klastry{klauzule} "
                f"ORDER BY poradi, id LIMIT ? OFFSET ?",
                [*parametry, limit, odsazeni],
            ).fetchall()

            vysledek: list[dict[str, Any]] = []
            for radek in radky:
                klastr = dict(radek)
                klastr["cleny"] = [
                    dict(r) for r in spojeni.execute(
                        "SELECT p.* FROM klastr_cleny k "
                        "JOIN polozky p ON p.itemnum = k.itemnum "
                        "WHERE k.klastr_id = ?", (klastr["id"],)
                    ).fetchall()
                ]
                klastr["dvojice"] = [
                    dict(r) for r in spojeni.execute(
                        "SELECT * FROM dvojice WHERE klastr_id = ? ORDER BY skore DESC",
                        (klastr["id"],)
                    ).fetchall()
                ]
                klastr["rozhodnuti"] = [
                    dict(r) for r in spojeni.execute(
                        "SELECT * FROM rozhodnuti WHERE klastr_id = ? AND vzato_zpet = 0 "
                        "ORDER BY id DESC", (klastr["id"],)
                    ).fetchall()
                ]
                vysledek.append(klastr)

        return vysledek, celkem

    def detail_klastru(self, klastr_id: int) -> dict[str, Any] | None:
        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                "SELECT * FROM klastry WHERE id = ?", (klastr_id,)
            ).fetchone()
            if not radek:
                return None
            klastr = dict(radek)
            klastr["cleny"] = [
                dict(r) for r in spojeni.execute(
                    "SELECT p.* FROM klastr_cleny k JOIN polozky p "
                    "ON p.itemnum = k.itemnum WHERE k.klastr_id = ?", (klastr_id,)
                ).fetchall()
            ]
            klastr["dvojice"] = [
                dict(r) for r in spojeni.execute(
                    "SELECT * FROM dvojice WHERE klastr_id = ? ORDER BY skore DESC",
                    (klastr_id,)
                ).fetchall()
            ]
            klastr["rozhodnuti"] = [
                dict(r) for r in spojeni.execute(
                    "SELECT * FROM rozhodnuti WHERE klastr_id = ? ORDER BY id DESC",
                    (klastr_id,)
                ).fetchall()
            ]
        return klastr


_sdilena_sluzba: SluzbaDeduplikace | None = None


def sluzba_deduplikace() -> SluzbaDeduplikace:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaDeduplikace()
    return _sdilena_sluzba
