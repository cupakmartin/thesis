# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.llm import OllamaPoskytovatel
from app.sluzby.kontrola import (
    STAV_CHYBA,
    STAV_OK,
    STAV_VAROVANI,
    Kontrola,
    SluzbaKontroly,
    VysledekKontroly,
)


class TestSouhrnStavu:
    def test_vse_v_poradku(self):
        vysledek = VysledekKontroly(kontroly=[
            Kontrola("a", STAV_OK, ""), Kontrola("b", STAV_OK, ""),
        ])
        assert vysledek.celkovy_stav == STAV_OK

    def test_jedno_varovani_snizi_celkovy_stav(self):
        vysledek = VysledekKontroly(kontroly=[
            Kontrola("a", STAV_OK, ""), Kontrola("b", STAV_VAROVANI, ""),
        ])
        assert vysledek.celkovy_stav == STAV_VAROVANI

    def test_chyba_prevazi_nad_varovanim(self):
        vysledek = VysledekKontroly(kontroly=[
            Kontrola("a", STAV_VAROVANI, ""), Kontrola("b", STAV_CHYBA, ""),
        ])
        assert vysledek.celkovy_stav == STAV_CHYBA

    def test_pocet_v_poradku(self):
        vysledek = VysledekKontroly(kontroly=[
            Kontrola("a", STAV_OK, ""), Kontrola("b", STAV_CHYBA, ""),
            Kontrola("c", STAV_OK, ""),
        ])
        assert vysledek.jako_slovnik()["pocet_v_poradku"] == 2
        assert vysledek.jako_slovnik()["pocet_kontrol"] == 3


class TestKontrolyBezModelu:
    def test_atributova_faze(self):
        vysledek = SluzbaKontroly()._atributova_faze()  # noqa: SLF001
        assert vysledek.stav == STAV_OK
        assert "6204" in vysledek.podrobnost

    def test_druh_komponenty(self):
        vysledek = SluzbaKontroly()._druh_komponenty()  # noqa: SLF001
        assert vysledek.stav == STAV_OK

    def test_kontrola_ma_vzdy_nazev_a_stav(self):
        sluzba = SluzbaKontroly()
        for kontrola in (sluzba._atributova_faze(), sluzba._druh_komponenty()):  # noqa: SLF001
            assert kontrola.nazev
            assert kontrola.stav in {STAV_OK, STAV_VAROVANI, STAV_CHYBA}
            assert kontrola.doba_s >= 0


class TestDostupnostModelu:
    def test_hlasi_chybu_kdyz_ollama_nebezi(self, monkeypatch):
        monkeypatch.setattr(OllamaPoskytovatel, "je_dostupny", lambda self: False)
        vysledek = SluzbaKontroly()._dostupnost_modelu()  # noqa: SLF001
        assert vysledek.stav == STAV_CHYBA
        assert "Ollama" in vysledek.zprava

    def test_hlasi_chybu_kdyz_chybi_vychozi_model(self, monkeypatch):
        monkeypatch.setattr(OllamaPoskytovatel, "je_dostupny", lambda self: True)
        monkeypatch.setattr(
            OllamaPoskytovatel, "seznam_modelu", lambda self: ["jiny-model:1b"],
        )
        vysledek = SluzbaKontroly()._dostupnost_modelu()  # noqa: SLF001
        assert vysledek.stav == STAV_CHYBA
        assert "ollama pull" in vysledek.podrobnost


@pytest.mark.skipif(
    not OllamaPoskytovatel().je_dostupny(),
    reason="Služba Ollama neběží; kontroly závislé na jazykovém modelu se přeskakují.",
)
class TestSJazykovymModelem:
    def test_zkusebni_preklad_dodrzi_glosar(self):
        vysledek = SluzbaKontroly()._preklad_s_glosarem()  # noqa: SLF001
        assert vysledek.stav in {STAV_OK, STAV_VAROVANI}
        assert vysledek.podrobnost

    def test_uplna_kontrola_vraci_vsechny_polozky(self):
        souhrn = SluzbaKontroly().proved().jako_slovnik()
        nazvy = {k["nazev"] for k in souhrn["kontroly"]}
        assert "Embedding model" in nazvy
        assert "Zkušební překlad" in nazvy
        assert souhrn["celkovy_stav"] in {STAV_OK, STAV_VAROVANI, STAV_CHYBA}
