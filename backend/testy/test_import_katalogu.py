# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import pytest

from app.jadro.csv_import import nacti_csv


@pytest.fixture
def prostredi(tmp_path, monkeypatch):
    from app.config import nastaveni

    monkeypatch.setenv("MRO_SOUBOR_DATABAZE", str(tmp_path / "test.db"))
    monkeypatch.setenv("MRO_SOUBOR_KATALOGU", str(tmp_path / "vstup" / "katalog.csv"))
    monkeypatch.setenv("MRO_ADRESAR_CACHE", str(tmp_path / "cache"))
    nastaveni.cache_clear()
    from app.db import inicializuj_schema

    inicializuj_schema()
    yield tmp_path
    nastaveni.cache_clear()


def _metadata() -> dict:
    from app.sluzby.import_katalogu import metadata

    meta = metadata()
    assert meta is not None
    return meta


def _polozky() -> list[dict]:
    from app.db import pripoj

    with pripoj(pouze_cteni=True) as spojeni:
        return [dict(r) for r in spojeni.execute("SELECT * FROM polozky ORDER BY poradi")]


def _nastaveni(obsah, **zmeny):
    from app.sluzby.import_katalogu import nastaveni_podle_navrhu

    nast = nastaveni_podle_navrhu(obsah)
    for klic, hodnota in zmeny.items():
        setattr(nast, klic, hodnota)
    return nast


VLASTNI = (
    "Kód;Název;Doplněk;Jazyk;Dodavatel\n"
    "A-1;Ložisko kuličkové;6204 2RS;CZ;Alfa\n"
    "A-2;Ball bearing;6204 2RS;EN;Beta\n"
).encode("utf-8")


class TestImport:
    def test_vlastni_sloupce_a_preklad_jazyka(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah, metadata

        obsah = nacti_csv(VLASTNI)
        nast = _nastaveni(obsah)
        nast.sloupce[2].role = "popis"
        nast.sloupce[4].nazev = "Dodavatel dílu"
        vysledek = importuj_obsah(obsah, nast, "moje.csv")

        polozky = _polozky()
        assert vysledek["pocet_polozek"] == 2
        assert [p["itemnum"] for p in polozky] == ["A-1", "A-2"]
        assert polozky[0]["description"] == "Ložisko kuličkové 6204 2RS"
        assert [p["lang_code"] for p in polozky] == ["CS", "EN"]
        assert json.loads(polozky[0]["data_json"])["Dodavatel dílu"] == "Alfa"
        meta = _metadata()
        assert [s["nazev"] for s in meta["sloupce"]] == ["Kód", "Název", "Doplněk", "Jazyk", "Dodavatel dílu"]
        assert meta["nazev_souboru"] == "moje.csv"

    def test_bez_id_se_vygeneruje_prvni_sloupec(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah, metadata

        obsah = nacti_csv(b"popis;cena\nVentil;10\nCerpadlo;20\n")
        importuj_obsah(obsah, _nastaveni(obsah, ma_id=False), "bez_id.csv")

        assert [p["itemnum"] for p in _polozky()] == ["0001", "0002"]
        sloupce = _metadata()["sloupce"]
        assert sloupce[0]["nazev"] == "ID" and sloupce[0]["role"] == "id"
        assert json.loads(_polozky()[1]["data_json"]) == {"ID": "0002", "popis": "Cerpadlo", "cena": "20"}

    def test_duplicitni_id(self, prostredi):
        from app.sluzby.import_katalogu import ChybaImportu, importuj_obsah

        obsah = nacti_csv(b"id;popis\n1;a\n1;b\n2;c\n")
        with pytest.raises(ChybaImportu, match="nejsou jedinečná"):
            importuj_obsah(obsah, _nastaveni(obsah), "x.csv")

    def test_bez_popisu(self, prostredi):
        from app.sluzby.import_katalogu import ChybaImportu, importuj_obsah

        obsah = nacti_csv(b"id;cena\n1;10\n")
        with pytest.raises(ChybaImportu, match="popisem"):
            importuj_obsah(obsah, _nastaveni(obsah), "x.csv")

    def test_neprirazena_hodnota_jazyka(self, prostredi):
        from app.sluzby.import_katalogu import ChybaImportu, importuj_obsah

        obsah = nacti_csv(b"id;popis;lang\n1;a;CS\n2;b;XX\n")
        nast = _nastaveni(obsah)
        nast.mapa_jazyku = {"CS": "cs"}
        with pytest.raises(ChybaImportu, match="XX"):
            importuj_obsah(obsah, nast, "x.csv")

    def test_jazyky_ve_sloupcich(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah

        obsah = nacti_csv(b"ID;DESCRIPTION_EN;DESCRIPTION_CS\n1;Ball bearing;Lozisko\n")
        nast = _nastaveni(obsah, vicejazycny="sloupce")
        importuj_obsah(obsah, nast, "x.csv")

        polozka = _polozky()[0]
        assert polozka["description"] == "Ball bearing"
        assert polozka["lang_code"] == "EN"
        assert json.loads(polozka["data_json"])["DESCRIPTION_CS"] == "Lozisko"

    def test_jednojazycny_katalog(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah

        obsah = nacti_csv(b"id;popis\n1;Mutter M10\n")
        importuj_obsah(obsah, _nastaveni(obsah, jazyk_katalogu="de"), "x.csv")
        assert _polozky()[0]["lang_code"] == "DE"

    def test_radek_bez_popisu_se_preskoci(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah

        obsah = nacti_csv(b"id;popis\n1;a\n2;\n3;c\n")
        vysledek = importuj_obsah(obsah, _nastaveni(obsah), "x.csv")
        assert vysledek["preskoceno"] == 1
        assert [p["itemnum"] for p in _polozky()] == ["1", "3"]

    def test_maximo_pole_podle_nazvu(self, prostredi):
        from app.sluzby.import_katalogu import importuj_obsah

        obsah = nacti_csv(b"ITEMNUM;DESCRIPTION;MANUFACTURER;ROTATING\n1;Ventil;KSB;1\n")
        importuj_obsah(obsah, _nastaveni(obsah), "x.csv")
        polozka = _polozky()[0]
        assert polozka["manufacturer"] == "KSB"
        assert polozka["rotating"] == 1


class TestNahrazeniASmazani:
    def _beh(self):
        from app.db import nyni, pripoj

        with pripoj() as spojeni:
            spojeni.execute(
                "INSERT INTO behy (zalozeno, stav, metoda, nastaveni_json) "
                "VALUES (?, 'dokonceno', 'hybridni', '{}')", (nyni(),),
            )

    def test_import_nahradi_katalog_i_behy(self, prostredi):
        from app.db import pripoj
        from app.sluzby.import_katalogu import importuj_obsah

        prvni = nacti_csv(b"id;popis\n1;a\n2;b\n")
        importuj_obsah(prvni, _nastaveni(prvni), "prvni.csv")
        self._beh()
        druhy = nacti_csv(b"id;popis\n9;z\n")
        vysledek = importuj_obsah(druhy, _nastaveni(druhy), "druhy.csv")

        assert vysledek["smazano"] == {"polozek": 2, "behu": 1, "udalosti": 0}
        assert [p["itemnum"] for p in _polozky()] == ["9"]
        with pripoj(pouze_cteni=True) as spojeni:
            assert spojeni.execute("SELECT COUNT(*) FROM behy").fetchone()[0] == 0

    def test_smazany_katalog_se_pri_startu_nenacte(self, prostredi):
        from app.sluzby.import_katalogu import metadata, pri_startu, smaz_katalog

        cesta = prostredi / "vstup" / "katalog.csv"
        cesta.parent.mkdir()
        cesta.write_text("ITEMNUM;DESCRIPTION\n1;Ventil\n", encoding="utf-8")
        pri_startu()
        assert len(_polozky()) == 1

        smaz_katalog()
        pri_startu()
        assert _polozky() == [] and metadata() is None


class TestNahled:
    def test_nahrani_a_import_pres_token(self, prostredi):
        from app.sluzby.import_katalogu import (
            SloupecKatalogu,
            NastaveniImportu,
            importuj_nahled,
            uloz_nahled,
        )

        nahled = uloz_nahled(VLASTNI, "moje.csv")
        assert nahled["pocet_radku"] == 2
        assert [s["navrh_role"] for s in nahled["sloupce"]] == ["id", "popis", "", "jazyk", ""]
        assert nahled["navrh"]["mapa_jazyku"] == {"CZ": "cs", "EN": "en"}

        nast = NastaveniImportu(
            sloupce=[SloupecKatalogu(nazev=s["puvodni"], role=s["navrh_role"], index=s["index"])
                     for s in nahled["sloupce"]],
            ma_id=True, vicejazycny="sloupec", mapa_jazyku=nahled["navrh"]["mapa_jazyku"],
        )
        assert importuj_nahled(nahled["token"], nast)["pocet_polozek"] == 2


class TestGenerovaniAMigrace:
    def test_vygenerovany_katalog(self, prostredi):
        from app.sluzby.import_katalogu import generuj, metadata

        vysledek = generuj(pocet=200)
        assert vysledek["pocet_polozek"] == 200
        assert _metadata()["zdroj"] == "generovany"
        assert (prostredi / "vstup" / "ground_truth.csv").exists()
        role = {s["nazev"]: s["role"] for s in _metadata()["sloupce"]}
        assert role["ITEMNUM"] == "id" and role["LANGCODE"] == "jazyk"

    def test_puvodni_databaze_dostane_metadata(self, prostredi):
        from app.db import pripoj
        from app.sluzby.import_katalogu import metadata, zajisti_metadata

        with pripoj() as spojeni:
            spojeni.execute(
                "INSERT INTO polozky (itemnum, description, manufacturer, lang_code) "
                "VALUES ('100001', 'Ložisko 6204', 'SKF', 'CS')"
            )
        assert zajisti_metadata() is True
        data = json.loads(_polozky()[0]["data_json"])
        assert data["DESCRIPTION"] == "Ložisko 6204" and data["MANUFACTURER"] == "SKF"
        assert _metadata()["zdroj"] == "puvodni"
        assert zajisti_metadata() is False


class TestRozhrani:
    @pytest.fixture
    def klient(self, prostredi):
        from fastapi.testclient import TestClient

        from app.main import vytvor_aplikaci

        with TestClient(vytvor_aplikaci()) as testovaci_klient:
            yield testovaci_klient

    def test_cely_postup_importu(self, klient):
        assert klient.get("/api/katalog").json()["existuje"] is False

        nahled = klient.post("/api/katalog/nahled?nazev=moje.csv", content=VLASTNI,
                             headers={"Content-Type": "text/csv"}).json()
        sloupce = [{"index": s["index"], "nazev": s["puvodni"], "role": s["navrh_role"]}
                   for s in nahled["sloupce"]]
        odpoved = klient.post("/api/katalog/import", json={
            "token": nahled["token"], "sloupce": sloupce, "ma_id": True,
            "vicejazycny": "sloupec", "mapa_jazyku": nahled["navrh"]["mapa_jazyku"],
        })
        assert odpoved.status_code == 200, odpoved.text

        prubeh = klient.get("/api/katalog/import/prubeh").json()
        assert prubeh["stav"] == "dokonceno"
        assert prubeh["faze"] == "Zápis do databáze"
        assert prubeh["hotovo"] == prubeh["celkem"] == 2

        stav = klient.get("/api/katalog").json()
        assert stav["existuje"] is True and stav["pocet_polozek"] == 2
        polozky = klient.get("/api/polozky").json()["polozky"]
        assert polozky[0]["data"]["Dodavatel"] == "Alfa"

        assert klient.delete("/api/katalog").json()["polozek"] == 2
        assert klient.get("/api/katalog").json()["existuje"] is False

    def test_chybne_nastaveni_vrati_srozumitelnou_chybu(self, klient):
        nahled = klient.post("/api/katalog/nahled", content=b"id;cena\n1;10\n").json()
        odpoved = klient.post("/api/katalog/import", json={
            "token": nahled["token"], "ma_id": True,
            "sloupce": [{"index": 0, "nazev": "id", "role": "id"},
                        {"index": 1, "nazev": "cena", "role": ""}],
        })
        assert odpoved.status_code == 400
        assert "popisem" in odpoved.json()["detail"]

    def test_soubor_ktery_neni_csv(self, klient):
        odpoved = klient.post("/api/katalog/nahled", content=b"")
        assert odpoved.status_code == 422

    def test_id_s_lomitkem_a_mezerou(self, klient):
        nahled = klient.post("/api/katalog/nahled",
                             content="id;popis\nSKF/6204;Ložisko\nA 1;Ventil\n".encode()).json()
        klient.post("/api/katalog/import", json={
            "token": nahled["token"], "ma_id": True,
            "sloupce": [{"index": 0, "nazev": "id", "role": "id"},
                        {"index": 1, "nazev": "popis", "role": "popis"}],
        })
        assert klient.get("/api/polozky/SKF/6204").json()["description"] == "Ložisko"
        assert klient.get("/api/polozky/A%201").json()["description"] == "Ventil"
        assert "SKF/6204" in klient.get("/api/polozky/SKF/6204/xml").text
