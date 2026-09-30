# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from app.db import nyni, pripoj
from app.jadro.duplicity import (
    NastaveniDeduplikace,
    ZaznamPolozky,
    zkontroluj_novou_polozku,
)
from app.sluzby.katalog import SluzbaKatalogu, sluzba_katalogu

logger = logging.getLogger(__name__)

JMENNY_PROSTOR = "http://www.ibm.com/maximo"

UDALOST_AKTUALIZACE = "MXITEM_UPDATED"
UDALOST_VYTVORENI = "MXITEM_CREATED"

POLE_MXITEM: tuple[str, ...] = (
    "ITEMNUM", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "ITEMTYPE",
    "COMMODITYGROUP", "ORDERUNIT", "ISSUEUNIT", "STATUS", "ROTATING",
    "MANUFACTURER", "MODELNUM", "VENDOR", "EXTERNALREFID", "LANGCODE",
)


@dataclass
class ObjektovaStruktura:
    nazev: str = "MXITEM"
    hlavni_objekt: str = "ITEM"
    popis: str = "Kmenová data položek katalogu náhradních dílů"
    pole: tuple[str, ...] = field(default=POLE_MXITEM)
    podporovane_udalosti: tuple[str, ...] = (UDALOST_VYTVORENI, UDALOST_AKTUALIZACE)

    def jako_slovnik(self) -> dict[str, Any]:
        return {
            "nazev": self.nazev,
            "hlavni_objekt": self.hlavni_objekt,
            "popis": self.popis,
            "pole": list(self.pole),
            "podporovane_udalosti": list(self.podporovane_udalosti),
            "jmenny_prostor": JMENNY_PROSTOR,
        }


def polozka_do_xml(polozka: dict[str, Any]) -> str:
    koren = ET.Element(f"{{{JMENNY_PROSTOR}}}MXITEMSet")
    prvek_polozky = ET.SubElement(koren, f"{{{JMENNY_PROSTOR}}}ITEM")

    mapa = {
        "ITEMNUM": "itemnum",
        "DESCRIPTION": "description",
        "DESCRIPTION_LONGDESCRIPTION": "long_description",
        "ITEMTYPE": "itemtype",
        "COMMODITYGROUP": "commodity_group",
        "ORDERUNIT": "order_unit",
        "ISSUEUNIT": "issue_unit",
        "STATUS": "status",
        "ROTATING": "rotating",
        "MANUFACTURER": "manufacturer",
        "MODELNUM": "model_num",
        "VENDOR": "vendor",
        "EXTERNALREFID": "external_ref_id",
        "LANGCODE": "lang_code",
    }
    for nazev_pole, klic in mapa.items():
        hodnota = polozka.get(klic)
        if hodnota is None or hodnota == "":
            continue
        prvek = ET.SubElement(prvek_polozky, f"{{{JMENNY_PROSTOR}}}{nazev_pole}")
        prvek.text = str(hodnota)

    ET.register_namespace("mx", JMENNY_PROSTOR)
    return ET.tostring(koren, encoding="unicode", xml_declaration=True)


def xml_do_polozek(obsah: str) -> list[dict[str, str]]:
    try:
        koren = ET.fromstring(obsah)
    except ET.ParseError as chyba:
        raise ValueError(f"Neplatné XML: {chyba}") from chyba

    def _bez_jmenneho_prostoru(znacka: str) -> str:
        return znacka.split("}")[-1]

    polozky: list[dict[str, str]] = []
    for prvek in koren.iter():
        if _bez_jmenneho_prostoru(prvek.tag) != "ITEM":
            continue
        zaznam: dict[str, str] = {}
        for pole in prvek:
            nazev = _bez_jmenneho_prostoru(pole.tag)
            if pole.text:
                zaznam[nazev] = pole.text.strip()
        if zaznam.get("ITEMNUM"):
            polozky.append(zaznam)

    return polozky


class SluzbaMIF:
    def __init__(self, katalog: SluzbaKatalogu | None = None) -> None:
        self._katalog = katalog or sluzba_katalogu()

    def objektova_struktura(self) -> dict[str, Any]:
        return ObjektovaStruktura().jako_slovnik()

    def prijmi_udalost(
        self,
        typ_udalosti: str,
        obsah: dict[str, Any],
        kdo: str = "MIF",
        pocet_kandidatu: int = 10,
    ) -> dict[str, Any]:
        itemnum = str(obsah.get("ITEMNUM") or obsah.get("itemnum") or "").strip()
        popis = str(obsah.get("DESCRIPTION") or obsah.get("description") or "").strip()

        with pripoj() as spojeni:
            kurzor = spojeni.execute(
                "INSERT INTO mif_udalosti (prijato, typ_udalosti, itemnum, obsah_json) "
                "VALUES (?, ?, ?, ?)",
                (nyni(), typ_udalosti, itemnum or None,
                 json.dumps(obsah, ensure_ascii=False)),
            )
            udalost_id = int(kurzor.lastrowid or 0)

        try:
            if typ_udalosti not in {UDALOST_VYTVORENI, UDALOST_AKTUALIZACE}:
                raise ValueError(
                    f"Nepodporovaný typ události {typ_udalosti!r}. "
                    f"Podporovány jsou {UDALOST_VYTVORENI} a {UDALOST_AKTUALIZACE}."
                )
            if not popis:
                raise ValueError("Událost neobsahuje pole DESCRIPTION.")

            kandidati = self._zkontroluj_duplicity(
                itemnum, popis, obsah, pocet_kandidatu
            )
            vysledek = {
                "udalost_id": udalost_id,
                "itemnum": itemnum,
                "typ_udalosti": typ_udalosti,
                "pocet_kandidatu": len(kandidati),
                "upozorneni": bool(kandidati),
                "kandidati": kandidati,
            }

            with pripoj() as spojeni:
                spojeni.execute(
                    "UPDATE mif_udalosti SET zpracovano = 1, vysledek_json = ? WHERE id = ?",
                    (json.dumps(vysledek, ensure_ascii=False), udalost_id),
                )
            return vysledek

        except Exception as chyba:
            with pripoj() as spojeni:
                spojeni.execute(
                    "UPDATE mif_udalosti SET zpracovano = 1, chyba = ? WHERE id = ?",
                    (str(chyba), udalost_id),
                )
            raise

    def _zkontroluj_duplicity(
        self,
        itemnum: str,
        popis: str,
        obsah: dict[str, Any],
        pocet_kandidatu: int,
    ) -> list[dict[str, Any]]:
        zaznamy = self._katalog.zaznamy()
        if not zaznamy:
            return []

        vektory, index = self._katalog.zajisti_index()
        nova = ZaznamPolozky(
            itemnum=itemnum or "NOVA",
            popis=popis,
            komoditni_skupina=str(
                obsah.get("COMMODITYGROUP") or obsah.get("commodity_group") or ""
            ),
        )

        dvojice = zkontroluj_novou_polozku(
            nova=nova,
            zaznamy=zaznamy,
            vektory_katalogu=vektory,
            index=index,
            konfigurace=NastaveniDeduplikace(),
            pocet_kandidatu=pocet_kandidatu,
        )

        kandidati: list[dict[str, Any]] = []
        for d in dvojice:
            kandidat = zaznamy[d.index_a]
            if itemnum and kandidat.itemnum == itemnum:
                continue
            kandidati.append({
                "itemnum": kandidat.itemnum,
                "popis": kandidat.popis,
                "podobnost_semanticka": round(d.podobnost_semanticka, 4),
                "podobnost_lexikalni": round(d.podobnost_lexikalni, 4),
                "skore": round(d.skore, 4),
                "je_duplicita": d.prijata,
                "rozpor_atributu": d.rozpor_atributu,
                "vysvetleni": list(d.vysvetleni),
            })
        return kandidati

    def historie_udalosti(
        self, limit: int = 50, odsazeni: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute(
                "SELECT COUNT(*) FROM mif_udalosti"
            ).fetchone()[0])
            radky = spojeni.execute(
                "SELECT * FROM mif_udalosti ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, odsazeni),
            ).fetchall()
        return [dict(r) for r in radky], celkem


_sdilena_sluzba: SluzbaMIF | None = None


def sluzba_mif() -> SluzbaMIF:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaMIF()
    return _sdilena_sluzba
