# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def klient(tmp_path_factory) -> Iterator[TestClient]:
    docasny = tmp_path_factory.mktemp("mro")

    import os

    os.environ["MRO_SOUBOR_DATABAZE"] = str(docasny / "test.db")
    os.environ["MRO_ADRESAR_VYSTUPU"] = str(docasny / "vystup")

    from app.config import nastaveni

    nastaveni.cache_clear()

    katalog = docasny / "katalog.csv"
    _zapis_testovaci_katalog(katalog)
    os.environ["MRO_SOUBOR_KATALOGU"] = str(katalog)
    nastaveni.cache_clear()

    from app.db import inicializuj_schema, smaz_vse
    from app.main import vytvor_aplikaci

    inicializuj_schema()
    smaz_vse()

    aplikace = vytvor_aplikaci()
    with TestClient(aplikace) as testovaci_klient:
        yield testovaci_klient


def _zapis_testovaci_katalog(cesta: Path) -> None:
    radky = [
        ["ITEMNUM", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "ITEMTYPE",
         "COMMODITYGROUP", "ORDERUNIT", "ISSUEUNIT", "STATUS", "ROTATING",
         "MANUFACTURER", "MODELNUM", "VENDOR", "EXTERNALREFID", "ISOCLASS",
         "LANGCODE", "CHANGEDATE", "CHANGEBY"],
        ["10001", "Ložisko kuličkové 6204 2RS", "", "ITEM", "BEARINGS", "EA", "EA",
         "ACTIVE", "0", "SKF", "LOZ-6204", "ALFA", "SKF123456", "PU", "CS",
         "2024-01-01", "TEST"],
        ["10002", "Ball bearing 6204 2RS", "", "ITEM", "BEARINGS", "EA", "EA",
         "ACTIVE", "0", "FAG", "BRG-6204", "BETA", "FAG654321", "PU", "EN",
         "2024-02-01", "TEST"],
        ["10003", "Ložisko kuličkové 6205 2RS", "", "ITEM", "BEARINGS", "EA", "EA",
         "ACTIVE", "0", "SKF", "LOZ-6205", "ALFA", "SKF111111", "PU", "CS",
         "2024-01-01", "TEST"],
        ["10004", "Ventil kulový DN50 PN16 nerez", "", "ITEM", "VALVES", "EA", "EA",
         "ACTIVE", "0", "Danfoss", "VEN-50", "GAMA", "DAN999", "VA", "CS",
         "2024-03-01", "TEST"],
    ]
    with cesta.open("w", encoding="utf-8", newline="") as soubor:
        csv.writer(soubor, delimiter=";").writerows(radky)


class TestStavSystemu:
    def test_zdravi(self, klient):
        odpoved = klient.get("/api/zdravi")
        assert odpoved.status_code == 200
        assert odpoved.json()["stav"] == "v pořádku"

    def test_stav_systemu(self, klient):
        odpoved = klient.get("/api/system/stav")
        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["pocet_polozek"] == 4
        assert data["katalog_nacten"] is True

    def test_prehled(self, klient):
        odpoved = klient.get("/api/system/prehled")
        assert odpoved.status_code == 200
        assert "katalog" in odpoved.json()


class TestKatalog:
    def test_seznam_polozek(self, klient):
        odpoved = klient.get("/api/polozky?limit=10")
        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["celkem"] == 4
        assert len(data["polozky"]) == 4

    def test_fulltextove_hledani(self, klient):
        odpoved = klient.get("/api/polozky?hledany_text=Ventil")
        assert odpoved.json()["celkem"] == 1

    def test_filtr_podle_skupiny(self, klient):
        odpoved = klient.get("/api/polozky?komoditni_skupina=BEARINGS")
        assert odpoved.json()["celkem"] == 3

    def test_strankovani(self, klient):
        odpoved = klient.get("/api/polozky?limit=2&odsazeni=2")
        data = odpoved.json()
        assert data["celkem"] == 4
        assert len(data["polozky"]) == 2

    def test_detail_polozky_obsahuje_zarazeni(self, klient):
        odpoved = klient.get("/api/polozky/10001")
        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["itemnum"] == "10001"
        assert data["zarazeni_iso"]["kod"] == "PU"

    def test_neexistujici_polozka(self, klient):
        assert klient.get("/api/polozky/99999").status_code == 404

    def test_export_do_xml(self, klient):
        odpoved = klient.get("/api/polozky/10001/xml")
        assert odpoved.status_code == 200
        assert "MXITEMSet" in odpoved.text
        assert "6204" in odpoved.text

    def test_hodnoty_filtru(self, klient):
        data = klient.get("/api/polozky/filtry").json()
        assert "BEARINGS" in data["komoditni_skupiny"]


class TestDeduplikace:
    def test_spusteni_a_nalezeni_duplicity(self, klient):
        odpoved = klient.post("/api/deduplikace/spustit", json={
            "metoda": "hybridni", "prah_rozhodnuti": 0.60,
            "prah_kandidatu": 0.40, "pocet_sousedu": 5, "kdo": "test",
        })
        assert odpoved.status_code == 200
        beh_id = odpoved.json()["podrobnosti"]["beh_id"]

        klastry = klient.get(f"/api/deduplikace/behy/{beh_id}/klastry").json()
        assert klastry["celkem"] >= 1

        cisla_v_klastrech = {
            clen["itemnum"]
            for klastr in klastry["polozky"] for clen in klastr["cleny"]
        }
        assert {"10001", "10002"} <= cisla_v_klastrech
        for klastr in klastry["polozky"]:
            cisla = {c["itemnum"] for c in klastr["cleny"]}
            assert not ({"10001", "10003"} <= cisla)

    def test_prubeh_dokonceneho_behu(self, klient):
        prubeh = klient.get("/api/deduplikace/prubeh").json()
        assert prubeh["stav"] == "dokonceno"
        assert prubeh["uloha"] == "deduplikace"
        assert prubeh["zbyva_s"] == 0.0
        assert prubeh["pocet_fazi"] >= 4
        assert prubeh["faze"] == "Uložení skupin"

    def test_historie_behu(self, klient):
        odpoved = klient.get("/api/deduplikace/behy")
        assert odpoved.status_code == 200
        assert len(odpoved.json()) >= 1

    def test_kontrola_nove_polozky(self, klient):
        odpoved = klient.post("/api/deduplikace/kontrola-polozky", json={
            "popis": "Lozisko kulickove 6204 2RS",
            "komoditni_skupina": "BEARINGS",
            "pocet_kandidatu": 5,
        })
        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["pocet_kandidatu"] > 0
        assert data["kandidati"][0]["itemnum"] in {"10001", "10002"}

    def test_kontrola_odlisne_polozky_hlasi_rozpor(self, klient):
        odpoved = klient.post("/api/deduplikace/kontrola-polozky", json={
            "popis": "Ložisko kuličkové 6206 2RS", "pocet_kandidatu": 5,
        })
        kandidati = odpoved.json()["kandidati"]
        shodne = [k for k in kandidati if k["itemnum"] in {"10001", "10003"}]
        assert shodne
        assert all(k["rozpor_atributu"] for k in shodne)


class TestSlucovani:
    def test_schvaleni_a_zruseni(self, klient):
        beh = klient.get("/api/deduplikace/behy").json()[0]
        klastry = klient.get(f"/api/deduplikace/behy/{beh['id']}/klastry").json()
        klastr = klastry["polozky"][0]
        zastupce = klastr["navrzeny_zastupce"]

        odpoved = klient.post(
            f"/api/slucovani/klastry/{klastr['id']}/rozhodnout",
            json={"vysledek": "schvaleno", "zastupce": zastupce,
                  "poznamka": "Testovací sloučení", "kdo": "tester"},
        )
        assert odpoved.status_code == 200

        for clen in klastr["cleny"]:
            detail = klient.get(f"/api/polozky/{clen['itemnum']}").json()
            if clen["itemnum"] == zastupce:
                assert detail["stav_konsolidace"] == "aktivni"
            else:
                assert detail["stav_konsolidace"] == "slouceno"
                assert detail["slouceno_do"] == zastupce

        znovu = klient.post(
            f"/api/slucovani/klastry/{klastr['id']}/rozhodnout",
            json={"vysledek": "zamitnuto", "kdo": "tester"},
        )
        assert znovu.status_code == 400

        zruseni = klient.post(
            f"/api/slucovani/klastry/{klastr['id']}/zrusit?kdo=tester"
        )
        assert zruseni.status_code == 200
        for clen in klastr["cleny"]:
            detail = klient.get(f"/api/polozky/{clen['itemnum']}").json()
            assert detail["stav_konsolidace"] == "aktivni"
            assert detail["slouceno_do"] is None

    def test_neplatny_vysledek(self, klient):
        odpoved = klient.post(
            "/api/slucovani/klastry/1/rozhodnout",
            json={"vysledek": "nesmysl", "kdo": "tester"},
        )
        assert odpoved.status_code == 400


class TestGlosar:
    def test_seznam(self, klient):
        odpoved = klient.get("/api/glosar?limit=5")
        assert odpoved.status_code == 200
        assert odpoved.json()["celkem"] > 0

    def test_hledani(self, klient):
        odpoved = klient.get("/api/glosar?hledany_text=impeller")
        polozky = odpoved.json()["polozky"]
        assert any(p["terminy"].get("cs") == "oběžné kolo" for p in polozky)

    def test_kategorie(self, klient):
        assert len(klient.get("/api/glosar/kategorie").json()) > 0


class TestMIF:
    def test_objektova_struktura(self, klient):
        data = klient.get("/api/mif/objektova-struktura").json()
        assert data["nazev"] == "MXITEM"
        assert "ITEMNUM" in data["pole"]

    def test_udalost_vyvola_kontrolu_duplicit(self, klient):
        odpoved = klient.post("/api/mif/udalost", json={
            "typ_udalosti": "MXITEM_UPDATED",
            "obsah": {"ITEMNUM": "20001", "DESCRIPTION": "Ball bearing 6204 2RS",
                      "COMMODITYGROUP": "BEARINGS"},
            "kdo": "MIF",
        })
        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["upozorneni"] is True
        assert data["pocet_kandidatu"] > 0

    def test_nepodporovana_udalost(self, klient):
        odpoved = klient.post("/api/mif/udalost", json={
            "typ_udalosti": "NEZNAMA", "obsah": {"ITEMNUM": "1", "DESCRIPTION": "x"},
        })
        assert odpoved.status_code == 400

    def test_historie_udalosti(self, klient):
        assert klient.get("/api/mif/udalosti").json()["celkem"] >= 1
