# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.glosar import Glosar, PolozkaGlosare
from app.jadro.llm import ZNACKA_KONCE, ZNACKA_ZACATKU, StubPoskytovatel
from app.jadro.rag import (
    ZPUSOB_GLOSAR,
    ZPUSOB_KRATKY,
    ZPUSOB_TEXT,
    PozadavekPrekladu,
    PrekladacRAG,
    _ocisti_odpoved,
    je_kratky_vstup,
)


def _glosar() -> Glosar:
    glosar = Glosar()
    glosar._polozky = [  # noqa: SLF001 - testovací příprava
        PolozkaGlosare(id="G1", termin_en="nut", termin_cs="matice",
                       nespravne="ořech"),
        PolozkaGlosare(id="G2", termin_en="centrifugal pump",
                       termin_cs="čerpadlo odstředivé"),
        PolozkaGlosare(id="G3", termin_en="impeller", termin_cs="oběžné kolo"),
        PolozkaGlosare(id="G4", termin_en="thread", termin_cs="závit"),
    ]
    glosar._sestav_mapu_tvaru()  # noqa: SLF001
    return glosar


def _prekladac(stub: StubPoskytovatel | None = None) -> PrekladacRAG:
    return PrekladacRAG(zdroj_glosare=_glosar(),
                        poskytovatel=stub or StubPoskytovatel())


class TestRozpoznaniKratkehoVstupu:
    @pytest.mark.parametrize("text", [
        "Nut", "Tree", "Safety goggles", "Torque wrench", "Ložisko 6204",
        "Check oil level", "Tools required:", "  Ladder  ",
    ])
    def test_kratky_vstup(self, text):
        assert je_kratky_vstup(text)

    @pytest.mark.parametrize("text", [
        "Replace the impeller and seal on the centrifugal pump.",
        "Remove the cover.",
        "Is the valve closed?",
        "Disconnect the power supply before removing the motor",
        "Nut\nBolt",
    ])
    def test_vetny_vstup(self, text):
        assert not je_kratky_vstup(text)


class TestPrimaShodaVGlosari:
    def test_termin_glosare_se_preklada_bez_modelu(self):
        stub = StubPoskytovatel()
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text="Nut"))

        assert vysledek.preklad == "Matice"
        assert vysledek.zpusob == ZPUSOB_GLOSAR
        assert stub.zaznamenane_vstupy == []

    def test_opacny_smer(self):
        vysledek = _prekladac().prelozi(PozadavekPrekladu(
            text="matice", zdrojovy_jazyk="cs", cilovy_jazyk="en"))
        assert vysledek.preklad == "nut"
        assert vysledek.zpusob == ZPUSOB_GLOSAR

    def test_cesky_vysledek_ma_prirozeny_slovosled(self):
        vysledek = _prekladac().prelozi(PozadavekPrekladu(text="Centrifugal pump"))
        assert vysledek.preklad == "Odstředivé čerpadlo"

    def test_bez_glosare_se_ptame_modelu(self):
        stub = StubPoskytovatel({"Nut": "Matice"})
        vysledek = _prekladac(stub).prelozi(
            PozadavekPrekladu(text="Nut", pouzit_glosar=False))

        assert vysledek.zpusob == ZPUSOB_KRATKY
        assert len(stub.zaznamenane_vstupy) == 1

    def test_shoda_jen_s_terminem_ve_zdrojovem_jazyce(self):
        stub = StubPoskytovatel({"matice": "matrix"})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text="matice"))
        assert vysledek.zpusob == ZPUSOB_KRATKY


class TestKratkyPrompt:
    def test_neobsahuje_priklady_z_vetneho_promptu(self):
        stub = StubPoskytovatel({"Tree": "Strom"})
        _prekladac(stub).prelozi(PozadavekPrekladu(text="Tree"))
        instrukce, _ = stub.zaznamenane_vstupy[0]

        assert "oběžné kolo" not in instrukce
        assert "vyměňte" not in instrukce.lower()
        assert "DATA" in instrukce

    def test_generovani_je_omezeno(self):
        stub = StubPoskytovatel({"Tree": "Strom"})
        _prekladac(stub).prelozi(PozadavekPrekladu(text="Tree"))
        volani = stub.zaznamenane_parametry[0]

        assert volani["max_tokenu"] is not None and volani["max_tokenu"] <= 64
        assert ZNACKA_ZACATKU in volani["stop"]
        assert "\n" not in volani["stop"]

    def test_zavazny_je_jen_doslovne_nalezeny_termin(self):
        stub = StubPoskytovatel({"Nuts": "Matice"})
        _prekladac(stub).prelozi(PozadavekPrekladu(text="Nuts"))
        instrukce, _ = stub.zaznamenane_vstupy[0]

        assert "nut = matice" in instrukce
        assert "závit" not in instrukce

    def test_vysledkem_je_jen_prvni_radek(self):
        stub = StubPoskytovatel({"Tree": "Strom\n\nPoznámka: strom je rostlina."})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text="Tree"))
        assert vysledek.preklad == "Strom"

    def test_dvojtecka_popisku_zustane(self):
        stub = StubPoskytovatel({"Tools": "Potřebné nástroje"})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text="Tools required:"))
        assert vysledek.preklad == "Potřebné nástroje:"

    def test_velikost_pismen_podle_vstupu(self):
        stub = StubPoskytovatel({"Gloves": "rukavice", "WARNING": "Varování"})
        prekladac = _prekladac(stub)
        assert prekladac.prelozi(PozadavekPrekladu(text="Gloves")).preklad == "Rukavice"
        assert prekladac.prelozi(PozadavekPrekladu(text="WARNING")).preklad == "VAROVÁNÍ"


class TestVetnyRezim:
    def test_veta_pouziva_vetny_prompt_a_zastavovaci_znacky(self):
        stub = StubPoskytovatel()
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="Replace the impeller.", pouzit_glosar=False))
        volani = stub.zaznamenane_parametry[0]

        assert vysledek.zpusob == ZPUSOB_TEXT
        assert ZNACKA_ZACATKU in volani["stop"]
        assert "\n" not in volani["stop"]

    def test_jednoradkovy_vstup_ma_jednoradkovy_preklad(self):
        stub = StubPoskytovatel({"ACME": (
            "Obsluha vodních služeb ACME - Postup údržby MP-112\n\n"
            "1. Příprava k údržbě\n1.1. Zabezpečení bezpečnosti"
        )})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="ACME Water Services - Maintenance Procedure MP-112",
            pouzit_glosar=False))
        assert vysledek.preklad == "Obsluha vodních služeb ACME - Postup údržby MP-112"

    def test_viceradkovy_vstup_zachova_radky(self):
        stub = StubPoskytovatel({"Drain": "Vypusťte olej.\nVyměňte filtr."})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="Drain the oil.\nReplace the filter.", pouzit_glosar=False))
        assert vysledek.preklad == "Vypusťte olej.\nVyměňte filtr."

    def test_veta_zacina_velkym_pismenem(self):
        stub = StubPoskytovatel({"Tighten": "utahněte matici na 45 Nm."})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="Tighten the nut to 45 Nm.", pouzit_glosar=False))
        assert vysledek.preklad == "Utahněte matici na 45 Nm."

    def test_limit_tokenu_odpovida_delce_vstupu(self):
        stub = StubPoskytovatel()
        prekladac = _prekladac(stub)
        prekladac.prelozi(PozadavekPrekladu(
            text="Remove the cover.", pouzit_glosar=False))
        prekladac.prelozi(PozadavekPrekladu(
            text="Remove the cover. " * 40, pouzit_glosar=False))
        kratky, dlouhy = (v["max_tokenu"] for v in stub.zaznamenane_parametry)

        assert kratky < dlouhy
        assert kratky <= 256


class TestKontrolaDelky:
    def test_jedno_slovo_nevyvola_varovani_o_delce(self):
        from app.jadro.validace import zvaliduj_preklad

        validace = zvaliduj_preklad(
            zdrojovy_text="Gloves", preklad="Ochranné rukavice",
            nalezene_terminy=[], zdrojovy_jazyk="en", cilovy_jazyk="cs",
        )
        assert not any("delší" in v for v in validace.varovani)

    def test_u_vety_varovani_zustava(self):
        from app.jadro.validace import zvaliduj_preklad

        validace = zvaliduj_preklad(
            zdrojovy_text="Replace the impeller.",
            preklad="Vyměňte oběžné kolo. " * 8,
            nalezene_terminy=[], zdrojovy_jazyk="en", cilovy_jazyk="cs",
        )
        assert any("delší" in v for v in validace.varovani)


class TestOcisteniOdpovedi:
    def test_vymysleny_dalsi_vstup_je_odriznut(self):
        odpoved = (f"Matice\n\n\n{ZNACKA_ZACATKU}\nImpeller\n{ZNACKA_KONCE}"
                   f"\n\nOběžné kolo")
        assert _ocisti_odpoved(odpoved) == "Matice"

    def test_odpoved_obalena_znackami(self):
        assert _ocisti_odpoved(f"{ZNACKA_ZACATKU}\nMatice\n{ZNACKA_KONCE}") == "Matice"

    def test_useknuta_znacka_na_konci(self):
        assert _ocisti_odpoved("Matice\n<<<KONEC_TEXTU_KE_ZPRAC") == "Matice"
