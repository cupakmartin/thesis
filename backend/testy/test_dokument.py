# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from app.jadro.dokument import (
    ChybaDokumentu,
    normalizuj_text_stranek,
    rozdel_na_useky,
    sestav_preklad,
    vytez_text_z_pdf,
)
from testy.pomocne_pdf import sestav_pdf

POKYN = [
    "Maintenance Instruction MI-204",
    "Before starting any work on the pump, disconnect the power",
    "supply and lock the main switch in the off position.",
    "Tools required:",
    "1. Torque wrench",
    "2. Ring spanner 17 mm",
    "Replace the impeller and check the condition of the mechan-",
    "ical seal before reassembly.",
]


class TestTextZPdf:
    def test_zalomene_radky_odstavce_se_spoji(self):
        text = vytez_text_z_pdf(sestav_pdf([POKYN])).text
        radky = text.split("\n")

        assert ("Before starting any work on the pump, disconnect the power "
                "supply and lock the main switch in the off position.") in radky

    def test_rozdeleni_slova_na_konci_radku(self):
        text = vytez_text_z_pdf(sestav_pdf([POKYN])).text
        assert "mechanical seal before reassembly." in text
        assert "mechan-" not in text

    def test_nadpis_a_polozky_seznamu_zustanou_na_radcich(self):
        radky = vytez_text_z_pdf(sestav_pdf([POKYN])).text.split("\n")

        assert "Maintenance Instruction MI-204" in radky
        assert "Tools required:" in radky
        assert "1. Torque wrench" in radky
        assert "2. Ring spanner 17 mm" in radky

    def test_zahlavi_zustane_jednou_a_cisla_stran_zmizi(self):
        obsah = ["Drain the oil.", "Replace the filter.", "Refill the oil."]
        stranky = [
            ["ACME Plant Services - Training", veta, f"Page {i} of 3"]
            for i, veta in enumerate(obsah, 1)
        ]
        dokument = vytez_text_z_pdf(sestav_pdf(stranky))

        assert dokument.pocet_stran == 3
        assert "Page" not in dokument.text
        assert dokument.text.split("\n") == ["ACME Plant Services - Training", *obsah]

    def test_opakovany_radek_se_neztrati(self):
        stranky = [["WARNING: Disconnect power before servicing", f"Note {i}."]
                   for i in range(1, 5)]
        text = normalizuj_text_stranek(["\n".join(s) for s in stranky])
        assert text.count("WARNING: Disconnect power before servicing") == 1

    def test_zahlavi_se_nepripoji_k_textu(self):
        stranky = [
            ["1 Maintenance manual", "The pump must be inspected every"],
            ["Maintenance manual 2", "month by a qualified technician."],
            ["3 Maintenance manual", "Record the result in the log."],
        ]
        radky = normalizuj_text_stranek(["\n".join(s) for s in stranky]).split("\n")

        assert radky == [
            "1 Maintenance manual",
            "The pump must be inspected every month by a qualified technician.",
            "Record the result in the log.",
        ]

    def test_odstavec_pokracuje_na_dalsi_strane(self):
        stranky = [
            ["Hlavicka", "Never open the valve while the line is still",
             "Hlavicka"],
            ["Hlavicka", "under pressure.", "Hlavicka"],
            ["Hlavicka", "Done.", "Hlavicka"],
        ]
        text = normalizuj_text_stranek([
            "\n".join(s) for s in stranky
        ])
        assert "Never open the valve while the line is still under pressure." in text

    def test_obsah_s_vodicimi_teckami(self):
        stranka = [
            "Contents",
            "A sample lockout/tagout policy for your workplace ........ ......... 1",
            "Scope .................................................... 1",
            "Lockout and tagout devices ............................... 2",
            "Scope",
            "This policy applies to all employees.",
        ]
        radky = normalizuj_text_stranek(["\n".join(stranka)]).split("\n")
        assert radky == [
            "Contents",
            "A sample lockout/tagout policy for your workplace",
            "Scope",
            "Lockout and tagout devices",
            "Scope",
            "This policy applies to all employees.",
        ]

    def test_odrazka_z_pisma_symbol(self):
        stranka = [
            "Devices must meet the following criteria:",
            " Lockout devices must work under the conditions in",
            "which they are used.",
            " Each lock must have a unique key.",
        ]
        text = normalizuj_text_stranek(["\n".join(stranka)])
        assert text.split("\n") == [
            "Devices must meet the following criteria:",
            "• Lockout devices must work under the conditions in which they are used.",
            "• Each lock must have a unique key.",
        ]
        assert [u.odrazka for u in rozdel_na_useky(text)][1:] == ["• ", "• "]

    def test_soubor_bez_textu_je_odmitnut(self):
        with pytest.raises(ChybaDokumentu, match="textovou vrstvu"):
            vytez_text_z_pdf(sestav_pdf([[]]))

    def test_jiny_soubor_nez_pdf_je_odmitnut(self):
        with pytest.raises(ChybaDokumentu, match="PDF"):
            vytez_text_z_pdf(b"Toto neni PDF.")


class TestRozdeleniNaUseky:
    def test_kazdy_radek_je_usek_a_struktura_se_zachova(self):
        text = "Tools required:\n\n1. Torque wrench\n- Ring spanner\n\nDone."
        useky = rozdel_na_useky(text)
        preklady = {u.poradi: u.text for u in useky if u.prelozit}

        assert sestav_preklad(useky, preklady) == text

    def test_odrazka_se_nepreklada(self):
        useky = rozdel_na_useky("1. Torque wrench\n- Ring spanner\na) Gloves")
        assert [(u.odrazka, u.text) for u in useky] == [
            ("1. ", "Torque wrench"), ("- ", "Ring spanner"), ("a) ", "Gloves"),
        ]

    def test_cislo_ve_vete_neni_odrazka(self):
        useky = rozdel_na_useky("5 screws are required.\n4.8.2 Control layer")
        assert [u.odrazka for u in useky] == ["", ""]
        assert useky[0].text == "5 screws are required."

    def test_radek_bez_slov_se_nepreklada(self):
        useky = rozdel_na_useky("DN50 PN16\n6204-2RS\n—\nCheck the seal.")
        assert [u.prelozit for u in useky] == [False, False, False, True]

    def test_dlouhy_odstavec_se_deli_na_hranicich_vet(self):
        veta = "Check the seal of the pump and replace it if it leaks. "
        useky = rozdel_na_useky(veta * 40, max_znaku=300)

        assert len(useky) > 1
        assert all(len(u.text) <= 300 for u in useky)
        assert all(u.text.endswith(".") for u in useky)
        preklady = {u.poradi: u.text for u in useky}
        assert sestav_preklad(useky, preklady) == (veta * 40).strip()

    def test_preklad_nahradi_jen_prekladane_useky(self):
        useky = rozdel_na_useky("1. Torque wrench\nDN50 PN16")
        preklady = {useky[0].poradi: "Momentový klíč"}
        assert sestav_preklad(useky, preklady) == "1. Momentový klíč\nDN50 PN16"
