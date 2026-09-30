# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.config import Nastaveni, nastaveni
from app.db import pripoj
from app.jadro.duplicity import ZaznamPolozky
from app.jadro.embeddingy import SpravceEmbeddingu, spravce_embeddingu
from app.jadro.index_faiss import VektorovyIndex
from app.jadro.normalizace import normalizuj_pro_embedding
from app.jadro.taxonomie import zarad_pravidlove

logger = logging.getLogger(__name__)

SLOUPCE_MAXIMO = {
    "itemnum": "ITEMNUM",
    "description": "DESCRIPTION",
    "long_description": "DESCRIPTION_LONGDESCRIPTION",
    "itemtype": "ITEMTYPE",
    "commodity_group": "COMMODITYGROUP",
    "order_unit": "ORDERUNIT",
    "issue_unit": "ISSUEUNIT",
    "status": "STATUS",
    "rotating": "ROTATING",
    "manufacturer": "MANUFACTURER",
    "model_num": "MODELNUM",
    "vendor": "VENDOR",
    "external_ref_id": "EXTERNALREFID",
    "iso_class": "ISOCLASS",
    "lang_code": "LANGCODE",
    "change_date": "CHANGEDATE",
    "change_by": "CHANGEBY",
}


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

    def nacti_z_csv(
        self,
        cesta: Path | None = None,
        kdo: str = "systém",
        oddelovac: str = ";",
    ) -> int:
        cilova_cesta = cesta or self._nastaveni.soubor_katalogu
        if not cilova_cesta.exists():
            raise FileNotFoundError(
                f"Soubor katalogu nebyl nalezen: {cilova_cesta}. "
                f"Spusťte nejprve skripty/generuj_dataset.py."
            )

        with cilova_cesta.open(encoding="utf-8-sig") as soubor:
            radky = list(csv.DictReader(soubor, delimiter=oddelovac))

        if not radky:
            raise ValueError("Soubor katalogu neobsahuje žádné záznamy.")

        chybejici = {"ITEMNUM", "DESCRIPTION"} - set(radky[0].keys())
        if chybejici:
            raise ValueError(
                f"V exportu chybí povinné sloupce: {', '.join(sorted(chybejici))}."
            )

        pripravene: list[tuple[Any, ...]] = []
        for poradi, radek in enumerate(radky):
            hodnoty = {
                klic: (radek.get(sloupec) or "").strip()
                for klic, sloupec in SLOUPCE_MAXIMO.items()
            }
            if not hodnoty["itemnum"]:
                continue

            if not hodnoty["iso_class"]:
                zarazeni = zarad_pravidlove(
                    hodnoty["description"], hodnoty["commodity_group"]
                )
                hodnoty["iso_class"] = zarazeni.kod if zarazeni else ""

            pripravene.append((
                hodnoty["itemnum"], hodnoty["description"], hodnoty["long_description"],
                hodnoty["itemtype"], hodnoty["commodity_group"], hodnoty["order_unit"],
                hodnoty["issue_unit"], hodnoty["status"],
                1 if hodnoty["rotating"] in {"1", "true", "True"} else 0,
                hodnoty["manufacturer"], hodnoty["model_num"], hodnoty["vendor"],
                hodnoty["external_ref_id"], hodnoty["iso_class"], hodnoty["lang_code"],
                hodnoty["change_date"], hodnoty["change_by"], poradi,
            ))

        with pripoj() as spojeni:
            spojeni.execute("DELETE FROM polozky")
            spojeni.executemany(
                """
                INSERT INTO polozky (
                    itemnum, description, long_description, itemtype,
                    commodity_group, order_unit, issue_unit, status, rotating,
                    manufacturer, model_num, vendor, external_ref_id, iso_class,
                    lang_code, change_date, change_by, poradi
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                pripravene,
            )

        self.invaliduj_index()
        logger.info("Načteno %d položek katalogu z %s.", len(pripravene), cilova_cesta)
        return len(pripravene)

    def pocet(self) -> int:
        with pripoj(pouze_cteni=True) as spojeni:
            return int(spojeni.execute("SELECT COUNT(*) FROM polozky").fetchone()[0])

    def _sestav_podminky(self, filtr: FiltrKatalogu) -> tuple[str, list[Any]]:
        podminky: list[str] = []
        parametry: list[Any] = []

        if filtr.hledany_text:
            podminky.append(
                "(description LIKE ? OR itemnum LIKE ? OR manufacturer LIKE ? "
                "OR model_num LIKE ?)"
            )
            vzor = f"%{filtr.hledany_text}%"
            parametry.extend([vzor, vzor, vzor, vzor])
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

        return [dict(r) for r in radky], celkem

    def detail(self, itemnum: str) -> dict[str, Any] | None:
        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                "SELECT * FROM polozky WHERE itemnum = ?", (itemnum,)
            ).fetchone()
        return dict(radek) if radek else None

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

    def export_do_csv(self, cesta: Path, filtr: FiltrKatalogu | None = None) -> int:
        polozky, _ = self.seznam(filtr, limit=1_000_000, odsazeni=0)
        cesta.parent.mkdir(parents=True, exist_ok=True)
        with cesta.open("w", encoding="utf-8", newline="") as soubor:
            zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            zapisovac.writerow(list(SLOUPCE_MAXIMO.values()))
            for p in polozky:
                zapisovac.writerow([p.get(klic, "") for klic in SLOUPCE_MAXIMO])
        return len(polozky)

_sdilena_sluzba: SluzbaKatalogu | None = None

def sluzba_katalogu() -> SluzbaKatalogu:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaKatalogu()
    return _sdilena_sluzba
