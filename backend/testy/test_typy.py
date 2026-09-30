# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.glosar import PolozkaGlosare
from app.jadro.typy import SlovnikTypu


@pytest.fixture(scope="module")
def slovnik() -> SlovnikTypu:
    polozky = [
        PolozkaGlosare(id="G1", termin_en="check valve", termin_cs="ventil zpětný",
                       kategorie="armatura"),
        PolozkaGlosare(id="G2", termin_en="gate valve", termin_cs="šoupátko",
                       kategorie="armatura"),
        PolozkaGlosare(id="G3", termin_en="ball valve", termin_cs="ventil kulový",
                       kategorie="armatura"),
        PolozkaGlosare(id="G4", termin_en="ball bearing", termin_cs="ložisko kuličkové",
                       kategorie="ložisko"),
        PolozkaGlosare(id="G5", termin_en="roller bearing", termin_cs="ložisko válečkové",
                       kategorie="ložisko"),
        PolozkaGlosare(id="G6", termin_en="downtime", termin_cs="prostoj",
                       kategorie="provoz"),
    ]
    novy = SlovnikTypu()
    novy.priprav(polozky)
    return novy


class TestUrceniDruhu:
    def test_ruzne_druhy_armatur(self, slovnik):
        prvni = slovnik.urci("Check valve DN125 PN16")
        druhy = slovnik.urci("Ball valve DN125 PN16")
        assert prvni is not None and druhy is not None
        assert prvni.identifikator != druhy.identifikator

    def test_shodny_druh_napric_jazyky(self, slovnik):
        anglicky = slovnik.urci("Check valve DN125 PN16 stainless steel")
        cesky = slovnik.urci("Ventil zpětný DN125 PN16 nerez")
        assert anglicky is not None and cesky is not None
        assert anglicky.identifikator == cesky.identifikator

    def test_nezavislost_na_slovosledu(self, slovnik):
        prvni = slovnik.urci("Ventil kulový DN50 PN16")
        druhy = slovnik.urci("Kulový ventil DN50 PN16")
        assert prvni is not None and druhy is not None
        assert prvni.identifikator == druhy.identifikator

    def test_zkraceny_zapis(self, slovnik):
        plny = slovnik.urci("Ventil kulový DN50")
        zkraceny = slovnik.urci("Vent. kul. DN50")
        assert plny is not None and zkraceny is not None
        assert plny.identifikator == zkraceny.identifikator

    def test_prednost_specifictejsiho_nazvu(self, slovnik):
        urceny = slovnik.urci("Ložisko kuličkové 6204 2RS")
        assert urceny is not None
        assert urceny.identifikator == "T_BALL_BEARING"

    def test_ruzne_druhy_lozisek(self, slovnik):
        kulickove = slovnik.urci("Ložisko kuličkové 6204")
        valeckove = slovnik.urci("Ložisko válečkové NU205")
        assert kulickove is not None and valeckove is not None
        assert kulickove.identifikator != valeckove.identifikator

    def test_funkcni_varianta(self, slovnik):
        prvni = slovnik.urci("Elektromagnetický ventil DN25 2/2 NC")
        druhy = slovnik.urci("Elektromagnetický ventil DN25 2/2 NO")
        assert prvni is not None and druhy is not None
        assert prvni.identifikator != druhy.identifikator

    def test_termin_mimo_kategorii_komponent(self, slovnik):
        assert slovnik.urci("Prostoj zařízení") is None

    def test_neznamy_popis(self, slovnik):
        assert slovnik.urci("Neznámá součástka XYZ") is None

    def test_prazdny_popis(self, slovnik):
        assert slovnik.urci("") is None
