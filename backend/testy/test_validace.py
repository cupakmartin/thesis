# -*- coding: utf-8 -*-
from __future__ import annotations

from app.jadro.glosar import ZPUSOB_PRIMY, NalezenyTermin, PolozkaGlosare
from app.jadro.validace import obsahuje_termin, zvaliduj_preklad


def _termin(en: str, cs: str, nespravne: str = "") -> NalezenyTermin:
    return NalezenyTermin(
        polozka=PolozkaGlosare(id="G1", termin_en=en, termin_cs=cs, nespravne=nespravne),
        skore=0.95,
        zpusob=ZPUSOB_PRIMY,
    )


class TestObsahujeTermin:
    def test_presna_shoda(self):
        assert obsahuje_termin("Vyměňte těsnění", "těsnění")

    def test_ohnuty_tvar_sestipismenneho_slova(self):
        assert obsahuje_termin("Utáhněte matici na šroubu", "matice")

    def test_ohnuty_tvar_ctyrpismenneho_slova(self):
        assert obsahuje_termin("Vyměňte těsnicí sadu", "těsnicí sada")

    def test_viceslovny_termin_nezavisly_na_poradi(self):
        assert obsahuje_termin("Vyměňte kolo oběžné čerpadla", "oběžné kolo")

    def test_bez_diakritiky(self):
        assert obsahuje_termin("Vymente tesneni", "těsnění")

    def test_neobsazeny_termin(self):
        assert not obsahuje_termin("Vyměňte ložisko", "matice")

    def test_nezamenuje_podobna_slova(self):
        assert not obsahuje_termin("Zkontrolujte ventilátor", "ventil")

    def test_prazdny_termin(self):
        assert not obsahuje_termin("Vyměňte ložisko", "")


class TestZvalidujPreklad:
    def test_dodrzeny_termin(self):
        vysledek = zvaliduj_preklad(
            "Replace the impeller",
            "Vyměňte oběžné kolo",
            [_termin("impeller", "oběžné kolo")],
        )
        assert vysledek.mira_dodrzeni_glosare == 1.0
        assert vysledek.je_v_poradku

    def test_nedodrzeny_termin(self):
        vysledek = zvaliduj_preklad(
            "Replace the impeller",
            "Vyměňte rotor",
            [_termin("impeller", "oběžné kolo")],
        )
        assert vysledek.mira_dodrzeni_glosare == 0.0
        assert not vysledek.je_v_poradku

    def test_termin_mimo_zdrojovy_text_se_nepocita(self):
        vysledek = zvaliduj_preklad(
            "Replace the bearing",
            "Vyměňte ložisko",
            [_termin("impeller", "oběžné kolo")],
        )
        assert vysledek.pocet_ocekavanych == 0
        assert vysledek.mira_dodrzeni_glosare == 1.0

    def test_pouziti_nespravne_varianty(self):
        vysledek = zvaliduj_preklad(
            "Replace the seal kit",
            "Vyměňte sadu těsnění",
            [_termin("seal kit", "těsnicí sada", nespravne="sada těsnění")],
        )
        assert vysledek.pocet_nespravnych_variant == 1
        assert not vysledek.je_v_poradku

    def test_zachovani_identifikatoru(self):
        vysledek = zvaliduj_preklad(
            "Install check valve DN50 PN16", "Instalujte zpětný ventil DN50 PN16", [],
        )
        assert vysledek.identifikatory_zachovany

    def test_ztraceny_identifikator(self):
        vysledek = zvaliduj_preklad(
            "Install check valve DN50 PN16", "Instalujte zpětný ventil", [],
        )
        assert not vysledek.identifikatory_zachovany
        assert "DN50" in vysledek.chybejici_identifikatory

    def test_varovani_pri_prilis_kratkem_prekladu(self):
        vysledek = zvaliduj_preklad(
            "Replace the impeller and seal on the centrifugal pump immediately", "Vyměňte", [],
        )
        assert any("kratší" in v for v in vysledek.varovani)

    def test_bez_terminu_je_v_poradku(self):
        vysledek = zvaliduj_preklad("Replace part", "Vyměňte díl", [])
        assert vysledek.mira_dodrzeni_glosare == 1.0
        assert vysledek.je_v_poradku
