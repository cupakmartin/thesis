# -*- coding: utf-8 -*-
from __future__ import annotations

import threading

import pytest


class FalesnyKlient:
    def __init__(self, v_pameti=(), selhat=False, cekat=None):
        self.v_pameti = set(v_pameti)
        self.selhat = selhat
        self.cekat = cekat
        self.volani: list[dict] = []

    def generate(self, **kw):
        self.volani.append(kw)
        if self.cekat is not None:
            self.cekat.wait(5)
        if self.selhat:
            raise ConnectionError("Ollama neběží")
        self.v_pameti.add(kw["model"])
        return {}

    def ps(self):
        return {"models": [{"model": m} for m in sorted(self.v_pameti)]}


@pytest.fixture
def klient(monkeypatch):
    from app.sluzby import nacitani

    falesny = FalesnyKlient()
    monkeypatch.setattr(nacitani, "_klient", lambda: falesny)
    nacitani._nacitane.clear()
    nacitani._chyby.clear()
    return falesny


class TestPredehrati:
    def test_nacteni_pouzije_stejne_kontextove_okno_jako_preklad(self, klient):
        from app.config import nastaveni
        from app.sluzby.nacitani import predehrej_llm

        predehrej_llm("translategemma:12b", v_pozadi=False)

        volani = klient.volani[0]
        assert volani["model"] == "translategemma:12b"
        assert volani["options"]["num_ctx"] == nastaveni().kontext_modelu
        assert volani["keep_alive"] == nastaveni().udrzet_model_v_pameti

    def test_stav_behem_a_po_nacteni(self, klient, monkeypatch):
        from app.sluzby import nacitani

        monkeypatch.setattr(nacitani, "aktivni_model", lambda: "translategemma:12b")
        uvolnit = threading.Event()
        klient.cekat = uvolnit

        assert nacitani.stav_nacitani()["llm"]["stav"] == "nenacten"
        nacitani.predehrej_llm()
        assert nacitani.stav_nacitani()["llm"]["stav"] == "nacita"

        uvolnit.set()
        for _ in range(100):
            if nacitani.stav_nacitani()["llm"]["stav"] != "nacita":
                break
            threading.Event().wait(0.02)
        assert nacitani.stav_nacitani()["llm"]["stav"] == "pripraven"

    def test_dvoji_spusteni_nacita_jednou(self, klient):
        from app.sluzby import nacitani

        uvolnit = threading.Event()
        klient.cekat = uvolnit
        nacitani.predehrej_llm("gemma2:9b")
        nacitani.predehrej_llm("gemma2:9b")
        uvolnit.set()
        for _ in range(100):
            if not nacitani._nacitane:
                break
            threading.Event().wait(0.02)
        assert len(klient.volani) == 1

    def test_selhani_neuvizne_ve_stavu_nacitani(self, klient, monkeypatch):
        from app.sluzby import nacitani

        monkeypatch.setattr(nacitani, "aktivni_model", lambda: "gemma2:9b")
        klient.selhat = True
        nacitani.predehrej_llm(v_pozadi=False)

        stav = nacitani.stav_nacitani()["llm"]
        assert stav["stav"] == "nenacten"
        assert "Ollama" in stav["chyba"]

    def test_nedostupna_ollama(self, monkeypatch):
        from app.sluzby import nacitani

        class Nedostupny:
            def ps(self):
                raise ConnectionError("odmítnuto")

        monkeypatch.setattr(nacitani, "_klient", lambda: Nedostupny())
        assert nacitani.stav_nacitani()["llm"]["stav"] == "nedostupny"


class TestPrepnutiModelu:
    def test_prepnuti_nacte_novy_model(self, klient, monkeypatch, tmp_path):
        from app.config import nastav_aktivni_model, nastaveni
        from app.jadro.llm import OllamaPoskytovatel

        monkeypatch.setenv("MRO_SOUBOR_DATABAZE", str(tmp_path / "test.db"))
        monkeypatch.setenv("MRO_PREDEHRAT_MODELY", "true")
        nastaveni.cache_clear()
        try:
            from app.db import inicializuj_schema
            from app.sluzby import nacitani
            from app.sluzby.volba_modelu import zmen_model

            inicializuj_schema()
            monkeypatch.setattr(OllamaPoskytovatel, "je_dostupny", lambda self: True)
            monkeypatch.setattr(OllamaPoskytovatel, "seznam_modelu",
                                lambda self: ["gemma2:9b", "translategemma:12b"])
            zmen_model("gemma2:9b", kdo="test")
            for _ in range(100):
                if not nacitani._nacitane:
                    break
                threading.Event().wait(0.02)

            assert [v["model"] for v in klient.volani] == ["gemma2:9b"]
        finally:
            monkeypatch.undo()
            nastaveni.cache_clear()
            nastav_aktivni_model(None)


class TestEmbeddingy:
    def test_stav_spravce(self):
        from app.jadro.embeddingy import SpravceEmbeddingu

        spravce = SpravceEmbeddingu()
        assert spravce.stav == "nenacten"
        spravce._model = object()
        assert spravce.stav == "pripraven"
