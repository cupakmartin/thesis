# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.csv_import import (
    ChybaCsv,
    nacti_csv,
    navrhni_sloupce,
    rozpoznej_jazyk,
)


class TestNacteni:
    def test_strednik_a_utf8_s_bom(self):
        data = "﻿ITEMNUM;DESCRIPTION\n1;Ložisko 6204\n".encode("utf-8")
        obsah = nacti_csv(data)
        assert obsah.sloupce == ["ITEMNUM", "DESCRIPTION"]
        assert obsah.radky == [["1", "Ložisko 6204"]]
        assert obsah.oddelovac == ";"
        assert obsah.kodovani == "utf-8"

    def test_carka_a_windows_1250_z_excelu(self):
        data = "Kód,Název,Výrobce\n10,Čerpadlo odstředivé,KSB\n".encode("cp1250")
        obsah = nacti_csv(data)
        assert obsah.sloupce == ["Kód", "Název", "Výrobce"]
        assert obsah.radky[0][1] == "Čerpadlo odstředivé"
        assert obsah.oddelovac == ","
        assert obsah.kodovani == "cp1250"

    def test_tabulator(self):
        obsah = nacti_csv(b"a\tb\n1\t2\n")
        assert obsah.oddelovac == "\t"
        assert obsah.radky == [["1", "2"]]

    def test_carka_uvnitr_uvozovek(self):
        obsah = nacti_csv(b'id,popis\n1,"Ventil, kulovy DN50"\n')
        assert obsah.radky == [["1", "Ventil, kulovy DN50"]]

    def test_rucne_zvolene_kodovani_a_oddelovac(self):
        data = "a|b\n1|č\n".encode("cp1250")
        obsah = nacti_csv(data, kodovani="cp1250", oddelovac="|")
        assert obsah.radky == [["1", "č"]]

    def test_prazdne_a_duplicitni_nazvy_sloupcu(self):
        obsah = nacti_csv(b"popis;;popis\nA;B;C\n")
        assert obsah.sloupce == ["popis", "Sloupec 2", "popis (2)"]

    def test_nerovne_radky_a_prazdne_radky(self):
        obsah = nacti_csv(b"a;b;c\n1;2\n\n4;5;6;7\n")
        assert obsah.radky == [["1", "2", ""], ["4", "5", "6"]]

    def test_radky_s_prebyvajici_hodnotou_se_spocitaji(self):
        obsah = nacti_csv(b"nazev,cena\nCerpadlo 5,5 kW,100\nVentil,20\n")
        assert obsah.radku_s_prebytkem == 1

    def test_prazdny_soubor(self):
        with pytest.raises(ChybaCsv):
            nacti_csv(b"")

    def test_jen_hlavicka(self):
        with pytest.raises(ChybaCsv, match="záznam"):
            nacti_csv(b"a;b\n")


class TestNavrh:
    def test_maximo_export(self):
        obsah = nacti_csv(
            b"ITEMNUM;DESCRIPTION;COMMODITYGROUP;ISOCLASS;LANGCODE\n"
            b"1;Lozisko;BEARINGS;PU;CS\n2;Bearing;BEARINGS;PU;EN\n"
        )
        role = {s.puvodni: s.navrh_role for s in navrhni_sloupce(obsah)}
        assert role == {
            "ITEMNUM": "id", "DESCRIPTION": "popis", "COMMODITYGROUP": "skupina",
            "ISOCLASS": "trida", "LANGCODE": "jazyk",
        }

    def test_ceske_nazvy(self):
        obsah = nacti_csv("Kód;Název položky;Kategorie;Jazyk\n1;Ventil;A;cs\n".encode())
        role = [s.navrh_role for s in navrhni_sloupce(obsah)]
        assert role == ["id", "popis", "skupina", "jazyk"]

    def test_sloupce_podle_jazyka(self):
        obsah = nacti_csv(b"ID;DESCRIPTION_EN;DESCRIPTION_CS;Popis (de)\n1;a;b;c\n")
        jazyky = {s.puvodni: s.navrh_jazyk for s in navrhni_sloupce(obsah)}
        assert jazyky == {"ID": "", "DESCRIPTION_EN": "en", "DESCRIPTION_CS": "cs", "Popis (de)": "de"}

    def test_priklady_hodnoty_a_jedinecnost(self):
        obsah = nacti_csv(b"id;lang\n1;CS\n2;EN\n3;CS\n")
        sloupce = navrhni_sloupce(obsah)
        assert sloupce[0].unikatni is True
        assert sloupce[1].unikatni is False
        assert sloupce[1].hodnoty == ["CS", "EN"]
        assert sloupce[0].priklady == ["1", "2", "3"]


class TestJazyk:
    @pytest.mark.parametrize("hodnota,kod", [
        ("CS", "cs"), ("cz", "cs"), ("cze", "cs"), ("Czech", "cs"), ("čeština", "cs"),
        ("EN", "en"), ("eng", "en"), ("English", "en"), ("DE", "de"), ("Deutsch", "de"),
        ("it", "it"), ("ES", "es"), ("fr", "fr"), ("ZH", "zh"), ("中文", "zh"),
        ("ja", "ja"), ("JP", "ja"), ("日本語", "ja"),
    ])
    def test_rozpoznani(self, hodnota, kod):
        assert rozpoznej_jazyk(hodnota) == kod

    def test_nezname(self):
        assert rozpoznej_jazyk("XX") == ""
