# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.normalizace import (
    ZKRATKY,
    normalizuj_jednotky,
    normalizuj_pro_embedding,
    normalizuj_pro_lexikalni,
    odstran_diakritiku,
    rozvin_zkratky,
    sestav_reprezentaci,
    vycisti_text,
)


class TestOdstranDiakritiku:
    def test_ceska_diakritika(self):
        assert odstran_diakritiku("Ložisko kuličkové") == "Lozisko kulickove"

    def test_text_bez_diakritiky_zustava(self):
        assert odstran_diakritiku("Ball bearing") == "Ball bearing"

    def test_prazdny_retezec(self):
        assert odstran_diakritiku("") == ""


class TestNormalizujJednotky:
    def test_pripoji_mezeru_pred_jednotku(self):
        assert normalizuj_jednotky("Ložisko 20MM") == "Ložisko 20 mm"

    def test_prevede_palce_na_milimetry(self):
        assert normalizuj_jednotky('Ventil 1/2"') == "Ventil 12.7 mm"

    def test_prevede_desetinny_palec(self):
        assert normalizuj_jednotky("Trubka 0.5 inch") == "Trubka 12.7 mm"

    def test_sjednoti_zavit(self):
        assert normalizuj_jednotky("Šroub M20 x 1,5") == "Šroub m20x1.5"

    def test_rozepsana_jednotka(self):
        assert "20 mm" in normalizuj_jednotky("délka 20 milimetrů")

    def test_nedeli_nulou(self):
        assert normalizuj_jednotky('Rozměr 1/0"') == 'Rozměr 1/0"'


class TestRozvinZkratky:
    def test_zkratka_s_teckou(self):
        assert rozvin_zkratky("Čerp. vysokotl.") == "čerpadlo vysokotlaký"

    def test_samostatna_anglicka_zkratka(self):
        assert rozvin_zkratky("BRG BALL 6204").startswith("bearing")

    def test_neznama_zkratka_zustava(self):
        assert "xyz." in rozvin_zkratky("Součást xyz.")

    def test_slovnik_neobsahuje_synonyma(self):
        assert "kohout" not in ZKRATKY
        assert ZKRATKY.get("vent") == "ventil"


class TestVycistiText:
    def test_odstrani_specialni_znaky(self):
        assert vycisti_text("Ventil (kulový) DN50!") == "Ventil kulový DN50"

    def test_zachova_rozmerove_znaky(self):
        assert vycisti_text("20x47x14") == "20x47x14"

    def test_sloucí_vice_mezer(self):
        assert vycisti_text("Ventil    kulový") == "Ventil kulový"


class TestNormalizujProEmbedding:
    def test_zachova_diakritiku(self):
        assert "ložisko" in normalizuj_pro_embedding("Ložisko kuličkové")

    def test_prevede_na_mala_pismena(self):
        assert normalizuj_pro_embedding("VENTIL") == "ventil"

    def test_none_vraci_prazdny_retezec(self):
        assert normalizuj_pro_embedding(None) == ""

    def test_kombinace_uprav(self):
        assert normalizuj_pro_embedding("ČERP. VYSOKOTL. 20MM") == \
            "čerpadlo vysokotlaký 20 mm"


class TestNormalizujProLexikalni:
    def test_odstrani_diakritiku(self):
        assert normalizuj_pro_lexikalni("Ložisko kuličkové 6204") == \
            "lozisko kulickove 6204"

    def test_prazdny_vstup(self):
        assert normalizuj_pro_lexikalni("") == ""


class TestSestavReprezentaci:
    def test_spoji_pole(self):
        zaznam = {"nazev": "Ložisko", "vyrobce": "SKF"}
        assert sestav_reprezentaci(zaznam, ["nazev", "vyrobce"]) == "Ložisko | SKF"

    def test_preskoci_prazdne_hodnoty(self):
        zaznam = {"nazev": "Ložisko", "vyrobce": "", "model": None}
        assert sestav_reprezentaci(zaznam, ["nazev", "vyrobce", "model"]) == "Ložisko"

    def test_preskoci_textove_nan(self):
        zaznam = {"nazev": "Ložisko", "popis": "nan"}
        assert sestav_reprezentaci(zaznam, ["nazev", "popis"]) == "Ložisko"


@pytest.mark.parametrize("vstup,ocekavano", [
    ("Ložisko kuličkové 6204", "lozisko kulickove 6204"),
    ("BEARING BALL 6204", "bearing ball 6204"),
])
def test_lexikalni_normalizace_sjednocuje_jazyky(vstup, ocekavano):
    assert normalizuj_pro_lexikalni(vstup) == ocekavano
