# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import Nastaveni, nastaveni
from app.db import pripoj
from app.jadro.duplicity import ZaznamPolozky
from app.jadro.embeddingy import SpravceEmbeddingu, spravce_embeddingu
from app.jadro.index_faiss import VektorovyIndex
from app.jadro.normalizace import normalizuj_pro_embedding

logger = logging.getLogger(__name__)

@dataclass
class FiltrKatalogu:
    hledany_text: str = ""
    komoditni_skupina: str = ""
    iso_trida: str = ""
    stav: str = ""
    stav_konsolidace: str = ""
    jazyk: str = ""


class SluzbaKatalogu:
    def __init__(
        self,
        konfigurace: Nastaveni | None = None,
        spravce: SpravceEmbeddingu | None = None,
    ) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._spravce = spravce or spravce_embeddingu()
        self._index: VektorovyIndex | None = None
        self._vektory: np.ndarray | None = None
        self._zaznamy: list[ZaznamPolozky] = []
        self._zamek = threading.Lock()

    def nacti_z_csv(self, cesta: Path | None = None, kdo: str = "systém") -> int:
        from app.sluzby.import_katalogu import importuj_soubor

        return int(importuj_soubor(cesta or self._nastaveni.soubor_katalogu, kdo=kdo)["pocet_polozek"])

    def pocet(self) -> int:
        with pripoj(pouze_cteni=True) as spojeni:
            return int(spojeni.execute("SELECT COUNT(*) FROM polozky").fetchone()[0])

    def _sestav_podminky(self, filtr: FiltrKatalogu) -> tuple[str, list[Any]]:
        podminky: list[str] = []
        parametry: list[Any] = []

        if filtr.hledany_text:
            podminky.append("(description LIKE ? OR itemnum LIKE ? OR data_json LIKE ?)")
            vzor = f"%{filtr.hledany_text}%"
            parametry.extend([vzor, vzor, vzor])
        if filtr.komoditni_skupina:
            podminky.append("commodity_group = ?")
            parametry.append(filtr.komoditni_skupina)
        if filtr.iso_trida:
            podminky.append("iso_class = ?")
            parametry.append(filtr.iso_trida)
        if filtr.stav:
            podminky.append("status = ?")
            parametry.append(filtr.stav)
        if filtr.stav_konsolidace:
            podminky.append("stav_konsolidace = ?")
            parametry.append(filtr.stav_konsolidace)
        if filtr.jazyk:
            podminky.append("lang_code = ?")
            parametry.append(filtr.jazyk)

        klauzule = (" WHERE " + " AND ".join(podminky)) if podminky else ""
        return klauzule, parametry

    def seznam(
        self,
        filtr: FiltrKatalogu | None = None,
        limit: int = 50,
        odsazeni: int = 0,
        razeni: str = "poradi",
        sestupne: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        filtr = filtr or FiltrKatalogu()
        klauzule, parametry = self._sestav_podminky(filtr)

        povolene_razeni = {
            "poradi", "itemnum", "description", "commodity_group",
            "iso_class", "status", "manufacturer", "change_date",
        }
        sloupec = razeni if razeni in povolene_razeni else "poradi"
        smer = "DESC" if sestupne else "ASC"

        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute(
                f"SELECT COUNT(*) FROM polozky{klauzule}", parametry
            ).fetchone()[0])
            radky = spojeni.execute(
                f"SELECT * FROM polozky{klauzule} ORDER BY {sloupec} {smer} "
                f"LIMIT ? OFFSET ?",
                [*parametry, limit, odsazeni],
            ).fetchall()

        return [_s_daty(r) for r in radky], celkem

    def detail(self, itemnum: str) -> dict[str, Any] | None:
        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                "SELECT * FROM polozky WHERE itemnum = ?", (itemnum,)
            ).fetchone()
        return _s_daty(radek) if radek else None

    def rozliseni_hodnot(self) -> dict[str, list[str]]:
        with pripoj(pouze_cteni=True) as spojeni:
            def _hodnoty(sloupec: str) -> list[str]:
                radky = spojeni.execute(
                    f"SELECT DISTINCT {sloupec} FROM polozky "
                    f"WHERE {sloupec} IS NOT NULL AND {sloupec} <> '' "
                    f"ORDER BY {sloupec}"
                ).fetchall()
                return [str(r[0]) for r in radky]

            return {
                "komoditni_skupiny": _hodnoty("commodity_group"),
                "iso_tridy": _hodnoty("iso_class"),
                "stavy": _hodnoty("status"),
                "jazyky": _hodnoty("lang_code"),
            }

    def statistiky(self) -> dict[str, Any]:
        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute("SELECT COUNT(*) FROM polozky").fetchone()[0])
            podle_skupiny = [
                {"nazev": r[0], "pocet": r[1]}
                for r in spojeni.execute(
                    "SELECT commodity_group, COUNT(*) FROM polozky "
                    "GROUP BY commodity_group ORDER BY COUNT(*) DESC"
                ).fetchall()
            ]
            podle_tridy = [
                {"nazev": r[0], "pocet": r[1]}
                for r in spojeni.execute(
                    "SELECT iso_class, COUNT(*) FROM polozky "
                    "WHERE iso_class <> '' GROUP BY iso_class ORDER BY COUNT(*) DESC"
                ).fetchall()
            ]
            podle_jazyka = [
                {"nazev": r[0], "pocet": r[1]}
                for r in spojeni.execute(
                    "SELECT lang_code, COUNT(*) FROM polozky "
                    "WHERE lang_code <> '' GROUP BY lang_code"
                ).fetchall()
            ]
            slouceno = int(spojeni.execute(
                "SELECT COUNT(*) FROM polozky WHERE stav_konsolidace = 'slouceno'"
            ).fetchone()[0])

        return {
            "pocet_polozek": celkem,
            "pocet_slouceno": slouceno,
            "podle_komoditni_skupiny": podle_skupiny,
            "podle_iso_tridy": podle_tridy,
            "podle_jazyka": podle_jazyka,
        }

    def kvalita(self) -> dict[str, int]:
        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                """
                SELECT SUM(TRIM(description) = ''),
                       SUM(TRIM(commodity_group) = ''),
                       SUM(TRIM(iso_class) = '')
                FROM polozky
                """
            ).fetchone()
            shodne = spojeni.execute(
                """
                SELECT COALESCE(SUM(pocet), 0), COUNT(*) FROM (
                    SELECT COUNT(*) AS pocet FROM polozky
                    WHERE TRIM(description) <> ''
                    GROUP BY LOWER(TRIM(description)) HAVING COUNT(*) > 1
                )
                """
            ).fetchone()
        return {
            "bez_popisu": int(radek[0] or 0),
            "bez_skupiny": int(radek[1] or 0),
            "bez_iso_tridy": int(radek[2] or 0),
            "se_shodnym_popisem": int(shodne[0] or 0),
            "shodnych_popisu": int(shodne[1] or 0),
        }

    def zaznamy(self) -> list[ZaznamPolozky]:
        self._zajisti_zaznamy()
        return self._zaznamy

    def _zajisti_zaznamy(self) -> None:
        if self._zaznamy:
            return
        with pripoj(pouze_cteni=True) as spojeni:
            radky = spojeni.execute(
                "SELECT itemnum, description, long_description, commodity_group, "
                "manufacturer, iso_class, model_num FROM polozky ORDER BY poradi"
            ).fetchall()
        self._zaznamy = [
            ZaznamPolozky(
                itemnum=r["itemnum"],
                popis=r["description"] or "",
                popis_dlouhy=r["long_description"] or "",
                komoditni_skupina=r["commodity_group"] or "",
                vyrobce=r["manufacturer"] or "",
                iso_trida=r["iso_class"] or "",
                model=r["model_num"] or "",
            )
            for r in radky
        ]

    def zajisti_index(self) -> tuple[np.ndarray, VektorovyIndex]:
        with self._zamek:
            if self._index is not None and self._vektory is not None:
                return self._vektory, self._index

            self._zajisti_zaznamy()
            if not self._zaznamy:
                raise RuntimeError(
                    "Katalog je prázdný. Načtěte nejprve data pomocí importu."
                )

            texty = [
                normalizuj_pro_embedding(z.text_pro_porovnani()) for z in self._zaznamy
            ]
            self._vektory = self._spravce.zakoduj(texty)
            self._spravce.uloz_cache()

            self._index = VektorovyIndex(
                dimenze=self._vektory.shape[1], konfigurace=self._nastaveni
            )
            self._index.postav(self._vektory)
            return self._vektory, self._index

    def invaliduj_index(self) -> None:
        with self._zamek:
            self._index = None
            self._vektory = None
            self._zaznamy = []

    @property
    def je_index_pripraven(self) -> bool:
        return self._index is not None


def _s_daty(radek: Any) -> dict[str, Any]:
    polozka = dict(radek)
    polozka["data"] = json.loads(polozka.pop("data_json", None) or "{}")
    return polozka


_sdilena_sluzba: SluzbaKatalogu | None = None

def sluzba_katalogu() -> SluzbaKatalogu:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaKatalogu()
    return _sdilena_sluzba
