# -*- coding: utf-8 -*-
from __future__ import annotations

from app.jadro.atributy import porovnej_atributy, vytez_atributy


class TestExtrakce:
    def test_jmenovita_svetlost_a_tlak(self):
        atributy = vytez_atributy("Ventil kulový DN50 PN16 nerez")
        assert atributy.dn == frozenset({"50"})
        assert atributy.pn == frozenset({"16"})

    def test_typove_oznaceni_loziska(self):
        assert vytez_atributy("Ložisko kuličkové 6204 2RS").kody == frozenset({"6204"})

    def test_zavit(self):
        assert "m10x40" in vytez_atributy("Šroub M10x40 DIN 933").zavity

    def test_norma(self):
        assert "din933" in vytez_atributy("Šroub M10x40 DIN 933").normy

    def test_velicina_s_desetinnou_carkou(self):
        veliciny = dict(
            (j, h) for j, h in vytez_atributy("Elektromotor 5,5 kW 1450 ot/min").veliciny
        )
        assert veliciny["kw"] == 5.5
        assert veliciny["rpm"] == 1450.0

    def test_sjednoceni_otacek(self):
        prvni = vytez_atributy("Motor 1450 ot/min")
        druhy = vytez_atributy("Motor 1450 rpm")
        assert prvni.veliciny == druhy.veliciny

    def test_rozmer_nezavisly_na_mezerach(self):
        assert vytez_atributy("Ložisko 20x47x14").rozmery == \
            vytez_atributy("Ložisko 20 x 47 x 14").rozmery

    def test_interpunkce_neprerusi_jednotku(self):
        prvni = vytez_atributy("Šroubení trubka 22, mm")
        druhy = vytez_atributy("Šroubení trubka 22 mm")
        assert prvni.veliciny == druhy.veliciny

    def test_kratke_typove_oznaceni(self):
        assert "nh1" in vytez_atributy("Pojistka nožová 25 A NH1 aM").kody

    def test_osamocena_cisla(self):
        assert vytez_atributy("Ozubené kolo modul 2.0 počet zubů 24").cisla

    def test_prazdny_popis(self):
        assert vytez_atributy("").je_prazdna()


class TestKanonickeProvedeni:
    def test_material_napric_jazyky(self):
        cesky = vytez_atributy("Ventil kulový DN50 nerez")
        anglicky = vytez_atributy("Ball valve DN50 stainless steel")
        assert cesky.provedeni == anglicky.provedeni

    def test_tvarove_provedeni_napric_jazyky(self):
        assert vytez_atributy("Šroubení přímé").provedeni == \
            vytez_atributy("Fitting straight").provedeni

    def test_obecna_ocel_neni_rozlisovaci(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Check valve DN125 PN16 stain. steel"),
            vytez_atributy("Check valve DN125 PN16 stainless steel"),
        )
        assert not vysledek.rozpor


class TestPorovnani:
    def test_shodne_lozisko_napric_jazyky(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Ložisko kuličkové 6204 2RS"),
            vytez_atributy("Ball bearing 6204 2RS"),
        )
        assert not vysledek.rozpor
        assert vysledek.pocet_shod >= 2

    def test_odlisne_lozisko_je_rozpor(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Ložisko kuličkové 6204 2RS"),
            vytez_atributy("Ložisko kuličkové 6205 2RS"),
        )
        assert vysledek.rozpor
        assert vysledek.skore == 0.0
        assert any("6204" in v for v in vysledek.vysvetleni)

    def test_odlisny_vykon_je_rozpor(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Elektromotor 5,5 kW 1450 ot/min"),
            vytez_atributy("Elektromotor 7,5 kW 1450 ot/min"),
        )
        assert vysledek.rozpor

    def test_odlisne_kryti_loziska_je_rozpor(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Ložisko kuličkové 6006 otevřené"),
            vytez_atributy("Ball bearing 6006 2RS"),
        )
        assert vysledek.rozpor

    def test_chybejici_udaj_neni_rozpor(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Šroub šestihranný M12x40 DIN 933 nerez A4"),
            vytez_atributy("Šroub šestihranný M12x40 DIN 933"),
        )
        assert not vysledek.rozpor

    def test_castecny_prekryv_je_rozpor(self):
        vysledek = porovnej_atributy(
            vytez_atributy("Rozvaděč DN50 DN80"),
            vytez_atributy("Rozvaděč DN50 DN100"),
        )
        assert vysledek.rozpor

    def test_bez_atributu_neutralni_skore(self):
        vysledek = porovnej_atributy(vytez_atributy("Mazivo"), vytez_atributy("Grease"))
        assert not vysledek.rozpor
        assert vysledek.skore == 0.5
