# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import vychozi_model

MODELY = ["gemma2:9b", "mistral:7b", "qwen2.5:7b"]

@pytest.fixture(scope="module")
def prostredi(tmp_path_factory):
    import os

    docasny = tmp_path_factory.mktemp("volba_modelu")
    os.environ["MRO_SOUBOR_DATABAZE"] = str(docasny / "test.db")

    from app.config import nastaveni

    nastaveni.cache_clear()

    from app.db import inicializuj_schema

    inicializuj_schema()
    yield docasny
    nastaveni.cache_clear()


@pytest.fixture(autouse=True)
def _predstirana_ollama(monkeypatch, prostredi):
    from app.jadro.llm import OllamaPoskytovatel

    monkeypatch.setattr(OllamaPoskytovatel, "je_dostupny", lambda self: True)
    monkeypatch.setattr(OllamaPoskytovatel, "seznam_modelu", lambda self: list(MODELY))


@pytest.fixture(autouse=True)
def _vychozi_stav():
    yield
    from app.config import nastav_aktivni_model
    from app.db import smaz_volbu
    from app.sluzby.volba_modelu import KLIC_VOLBY

    smaz_volbu(KLIC_VOLBY)
    nastav_aktivni_model(None)


@pytest.fixture
def klient(prostredi) -> Iterator[TestClient]:
    from app.main import vytvor_aplikaci

    with TestClient(vytvor_aplikaci()) as testovaci_klient:
        yield testovaci_klient


class TestZmenaModelu:
    def test_prepnuti_zmeni_aktivni_model(self, klient):
        odpoved = klient.put(
            "/api/system/model", json={"model": "qwen2.5:7b", "kdo": "Martin Cupák"}
        )
        assert odpoved.status_code == 200
        assert odpoved.json()["aktivni"] == "qwen2.5:7b"
        assert odpoved.json()["prepnuto_uzivatelem"] is True

    def test_volba_se_projevi_v_jadre(self, klient):
        from app.jadro.llm import OllamaPoskytovatel

        klient.put("/api/system/model", json={"model": "gemma2:9b", "kdo": "test"})
        assert OllamaPoskytovatel().nazev_modelu == "gemma2:9b"

    def test_stav_systemu_hlasi_prepnuti(self, klient):
        klient.put("/api/system/model", json={"model": "qwen2.5:7b", "kdo": "test"})
        stav = klient.get("/api/system/stav").json()
        assert stav["aktivni_model"] == "qwen2.5:7b"
        assert stav["vychozi_model"] == vychozi_model()
        assert stav["model_prepnut_uzivatelem"] is True

    def test_prazdna_hodnota_vraci_vychozi_model(self, klient):
        klient.put("/api/system/model", json={"model": "qwen2.5:7b", "kdo": "test"})
        odpoved = klient.put("/api/system/model", json={"model": None, "kdo": "test"})
        assert odpoved.status_code == 200
        assert odpoved.json()["aktivni"] == vychozi_model()
        assert odpoved.json()["prepnuto_uzivatelem"] is False


class TestOvereniModelu:
    def test_nenainstalovany_model_je_odmitnut(self, klient):
        odpoved = klient.put(
            "/api/system/model", json={"model": "neexistuje:1b", "kdo": "test"}
        )
        assert odpoved.status_code == 400
        assert "ollama pull" in odpoved.json()["detail"]

    def test_odmitnuti_nezmeni_aktivni_model(self, klient):
        klient.put("/api/system/model", json={"model": "neexistuje:1b", "kdo": "test"})
        assert klient.get("/api/system/model").json()["aktivni"] == vychozi_model()

    def test_nedostupna_ollama_zabrani_prepnuti(self, klient, monkeypatch):
        from app.jadro.llm import OllamaPoskytovatel

        monkeypatch.setattr(OllamaPoskytovatel, "je_dostupny", lambda self: False)
        odpoved = klient.put(
            "/api/system/model", json={"model": "qwen2.5:7b", "kdo": "test"}
        )
        assert odpoved.status_code == 400
        assert "Ollama" in odpoved.json()["detail"]


class TestTrvalostVolby:
    def test_volba_prezije_restart(self, prostredi):
        from app.config import aktivni_model, nastav_aktivni_model, vychozi_model
        from app.main import vytvor_aplikaci
        from app.sluzby.volba_modelu import obnov_ulozenou_volbu

        with TestClient(vytvor_aplikaci()) as klient:
            klient.put("/api/system/model", json={"model": "qwen2.5:7b", "kdo": "test"})

        nastav_aktivni_model(None)
        assert aktivni_model() == vychozi_model()

        assert obnov_ulozenou_volbu() == "qwen2.5:7b"
        assert aktivni_model() == "qwen2.5:7b"

    def test_navrat_na_vychozi_smaze_ulozenou_volbu(self, klient):
        from app.db import precti_volbu
        from app.sluzby.volba_modelu import KLIC_VOLBY

        klient.put("/api/system/model", json={"model": "qwen2.5:7b", "kdo": "test"})
        assert precti_volbu(KLIC_VOLBY) == "qwen2.5:7b"

        klient.put("/api/system/model", json={"model": "", "kdo": "test"})
        assert precti_volbu(KLIC_VOLBY) is None
