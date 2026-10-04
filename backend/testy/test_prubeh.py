# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest


class TestVetnyTvar:
    def test_obraceny_slovosled_se_prevraci(self):
        from app.data.glosar_zdroj import vetny_tvar

        assert vetny_tvar("čerpadlo odstředivé") == "odstředivé čerpadlo"
        assert vetny_tvar("ventil kulový") == "kulový ventil"
        assert vetny_tvar("ložisko kuličkové") == "kuličkové ložisko"

    def test_prirozeny_slovosled_zustava(self):
        from app.data.glosar_zdroj import vetny_tvar

        assert vetny_tvar("oběžné kolo") == "oběžné kolo"
        assert vetny_tvar("zpětný ventil") == "zpětný ventil"
        assert vetny_tvar("tlumič vibrací") == "tlumič vibrací"

    def test_neznamy_termin_projde_beze_zmeny(self):
        from app.data.glosar_zdroj import vetny_tvar

        assert vetny_tvar("cokoli jiného") == "cokoli jiného"

    def test_vsechny_klice_existuji_v_glosari(self):
        from app.data.glosar_zdroj import PRIROZENY_SLOVOSLED, vsechny_terminy

        v_glosari = {t.termin_cs for t in vsechny_terminy()}
        chybejici = set(PRIROZENY_SLOVOSLED) - v_glosari
        assert not chybejici, f"v glosáři nejsou: {sorted(chybejici)}"

    def test_prevod_nemeni_mnozinu_slov(self):
        from app.data.glosar_zdroj import PRIROZENY_SLOVOSLED

        for katalogovy, vetny in PRIROZENY_SLOVOSLED.items():
            assert sorted(katalogovy.split()) == sorted(vetny.split()), katalogovy


class TestPromptPouzivaVetnyTvar:
    def test_cesky_blok_obsahuje_vetny_tvar(self):
        from app.jadro.glosar import NalezenyTermin, PolozkaGlosare
        from app.jadro.rag import _sestav_blok_glosare

        polozka = PolozkaGlosare(
            id="T1", termin_en="centrifugal pump", termin_cs="čerpadlo odstředivé"
        )
        blok = _sestav_blok_glosare(
            [NalezenyTermin(polozka=polozka, skore=1.0, zpusob="primy")],
            "en", "cs",
        )
        assert "odstředivé čerpadlo" in blok
        assert "čerpadlo odstředivé" not in blok

    def test_anglicky_smer_zustava_nedotcen(self):
        from app.jadro.glosar import NalezenyTermin, PolozkaGlosare
        from app.jadro.rag import _sestav_blok_glosare

        polozka = PolozkaGlosare(
            id="T1", termin_en="centrifugal pump", termin_cs="čerpadlo odstředivé"
        )
        blok = _sestav_blok_glosare(
            [NalezenyTermin(polozka=polozka, skore=1.0, zpusob="primy")],
            "cs", "en",
        )
        assert "centrifugal pump" in blok


@pytest.fixture(scope="module")
def prostredi(tmp_path_factory):
    import os

    docasny = tmp_path_factory.mktemp("prubeh")
    os.environ["MRO_SOUBOR_DATABAZE"] = str(docasny / "test.db")

    from app.config import nastaveni

    nastaveni.cache_clear()
    from app.db import inicializuj_schema

    inicializuj_schema()
    yield docasny
    nastaveni.cache_clear()


class TestZaznamPrubehu:
    def test_zaznam_obsahuje_vsechny_kroky(self, prostredi, monkeypatch):
        from app.jadro.llm import OdpovedLLM, OllamaPoskytovatel

        monkeypatch.setattr(
            OllamaPoskytovatel, "generuj",
            lambda self, systemova_instrukce, uzivatelsky_vstup, **kw: OdpovedLLM(
                text="Vyměňte oběžné kolo.", model="zkousime:1b", doba_s=0.1,
                pocet_tokenu_vstup=100, pocet_tokenu_vystup=10,
            ),
        )
        from app.sluzby.prubeh import prubeh_prekladu

        zaznam = prubeh_prekladu("Replace the impeller.")
        nazvy = [k["nazev"] for k in zaznam["kroky"]]
        assert len(nazvy) == 7
        assert nazvy[0] == "Určení způsobu překladu"
        assert "Vektorová reprezentace vstupu" in nazvy
        assert "Volání jazykového modelu" in nazvy

    def test_termin_glosare_se_obejde_bez_modelu(self, prostredi, monkeypatch):
        from app.jadro.llm import OllamaPoskytovatel

        def _nesmi_byt_volano(*args, **kwargs):
            raise AssertionError("model byl volán, ačkoli odpověděl glosář")

        monkeypatch.setattr(OllamaPoskytovatel, "generuj", _nesmi_byt_volano)
        from app.sluzby.prubeh import prubeh_prekladu

        zaznam = prubeh_prekladu("Nut")
        nazvy = [k["nazev"] for k in zaznam["kroky"]]
        assert zaznam["vystup"] == "Matice"
        assert zaznam["zpusob"] == "glosář"
        assert "Volání jazykového modelu" not in nazvy
        assert "Sestavení promptu" not in nazvy

    def test_kratky_vstup_ukazuje_skutecne_parametry(self, prostredi, monkeypatch):
        from app.jadro.llm import OdpovedLLM, OllamaPoskytovatel

        monkeypatch.setattr(
            OllamaPoskytovatel, "generuj",
            lambda self, systemova_instrukce, uzivatelsky_vstup, **kw: OdpovedLLM(
                text="Strom\n\nPoznámka navíc.", model="zkousime:1b", doba_s=0.1,
            ),
        )
        from app.sluzby.prubeh import prubeh_prekladu

        zaznam = prubeh_prekladu("Tree")
        kroky = {k["nazev"]: k for k in zaznam["kroky"]}
        volani = kroky["Volání jazykového modelu"]["udaje"]

        assert zaznam["vystup"] == "Strom"
        assert volani["max_tokenu"] <= 64
        assert volani["odpoved_doslovne"].startswith("Strom")
        assert kroky["Kontrola výstupu"]["udaje"]["odpoved_upravena"] is True
        assert "Vektorová reprezentace vstupu" not in kroky

    def test_zobrazeny_vektor_je_ten_pouzity(self, prostredi, monkeypatch):
        from app.jadro.embeddingy import spravce_embeddingu
        from app.jadro.llm import OdpovedLLM, OllamaPoskytovatel
        from app.jadro.normalizace import normalizuj_pro_embedding

        monkeypatch.setattr(
            OllamaPoskytovatel, "generuj",
            lambda self, systemova_instrukce, uzivatelsky_vstup, **kw: OdpovedLLM(
                text="x", model="zkousime:1b", doba_s=0.1,
            ),
        )
        from app.sluzby.prubeh import _ukazka_vektoru, prubeh_prekladu

        text = "Replace the IMPELLER on pump P-101."
        zaznam = prubeh_prekladu(text)
        zobrazeny = next(k for k in zaznam["kroky"]
                         if k["nazev"] == "Vektorová reprezentace vstupu")
        pouzity = spravce_embeddingu().zakoduj_jeden(normalizuj_pro_embedding(text))
        assert zobrazeny["udaje"]["vektor"] == _ukazka_vektoru(pouzity)

    def test_vektor_ma_ocekavanou_dimenzi(self, prostredi):
        from app.sluzby.prubeh import prubeh_podobnosti

        vysledek = prubeh_podobnosti("Ložisko kuličkové 6204", "Ball bearing 6204")
        assert vysledek["prvni"]["vektor"]["dimenze"] == 768
        assert len(vysledek["prvni"]["vektor"]["prvnich_n"]) == 16

    def test_podobnost_je_vypoctena_nikoli_pevna(self, prostredi):
        from app.sluzby.prubeh import prubeh_podobnosti

        blizke = prubeh_podobnosti("Ložisko kuličkové 6204", "Ball bearing 6204")
        vzdalene = prubeh_podobnosti("Ložisko kuličkové 6204", "Pracovní rukavice")
        assert blizke["kosinova_podobnost"] > vzdalene["kosinova_podobnost"]

    def test_vektor_se_meni_se_vstupem(self, prostredi):
        from app.sluzby.prubeh import prubeh_podobnosti

        prvni = prubeh_podobnosti("Ložisko 6204", "x")["prvni"]["vektor"]
        druhy = prubeh_podobnosti("Ložisko 6205", "x")["prvni"]["vektor"]
        assert prvni["prvnich_n"] != druhy["prvnich_n"]
