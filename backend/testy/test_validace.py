# -*- coding: utf-8 -*-
from __future__ import annotations

from app.jadro.glosar import (
    KATEGORIE_DRUHU_PORUCHY,
    KATEGORIE_UDRZBOVE_CINNOSTI,
    ZPUSOB_PRIMY,
    NalezenyTermin,
    PolozkaGlosare,
)
from app.jadro.validace import chybne_tvary, obsahuje_termin, zvaliduj_preklad


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


class TestSouvislyVyskyt:
    def test_slova_terminu_musi_ve_zdroji_stat_vedle_sebe(self):
        vysledek = zvaliduj_preklad(
            "Check the gate valve for internal leakage",
            "Zkontrolujte šoupátko z hlediska vnitřní netěsnosti",
            [_termin("check valve", "zpětný ventil")],
        )
        assert vysledek.pocet_ocekavanych == 0

    def test_zdrojovy_termin_v_mnoznem_cisle(self):
        assert obsahuje_termin("Install two check valves", "check valve", zachovat_poradi=True)

    def test_zdrojovy_termin_v_opacnem_poradi_neplati(self):
        assert not obsahuje_termin("Perform a valve check", "check valve", zachovat_poradi=True)

    def test_cilovy_termin_ve_vetnem_slovosledu(self):
        assert obsahuje_termin("Vyměňte těsnění na odstředivém čerpadle", "čerpadlo odstředivé")

    def test_cilova_slova_daleko_od_sebe_neplati(self):
        assert not obsahuje_termin(
            "Čerpadlo chladicího okruhu je odstředivé", "čerpadlo odstředivé"
        )

    def test_zakazana_varianta_se_kontroluje_jen_u_terminu_ze_zdroje(self):
        vysledek = zvaliduj_preklad(
            "Check the valve",
            "Zkontrolujte ventil",
            [_termin("check valve", "zpětný ventil", nespravne="zkontroluj ventil")],
        )
        assert vysledek.pocet_nespravnych_variant == 0
        assert vysledek.je_v_poradku


class TestIdentifikatoryVTextu:
    def test_cislo_normy_v_jinem_kontextu(self):
        vysledek = zvaliduj_preklad(
            "The training will include the requirements of 1910.147.",
            "Školení bude zahrnovat požadavky normy 1910.147.",
            [],
        )
        assert vysledek.pocet_identifikatoru == 1
        assert vysledek.identifikatory_zachovany

    def test_jiny_zapis_tehoz_identifikatoru(self):
        vysledek = zvaliduj_preklad(
            "Use DN50 flange with M20x1,5 thread",
            "Použijte přírubu DN 50 se závitem M20 × 1,5",
            [],
        )
        assert vysledek.identifikatory_zachovany

    def test_delsi_cislo_neni_shoda(self):
        vysledek = zvaliduj_preklad("Replace bearing 6204", "Vyměňte ložisko 62045", [])
        assert vysledek.chybejici_identifikatory == ["6204"]

    def test_text_bez_identifikatoru(self):
        vysledek = zvaliduj_preklad("Nut", "Matice", [])
        assert vysledek.pocet_identifikatoru == 0


class TestChybneTvary:
    def test_zkomoleny_tvar_slova_terminu(self):
        assert chybne_tvary(
            "Vyměňte těsnění na odstředovém čerpadle.", "čerpadlo odstředivé"
        ) == [("odstředovém", "odstředivé")]

    def test_spravne_sklonovany_termin_neni_chybou(self):
        assert chybne_tvary(
            "Vyměňte těsnění na odstředivém čerpadle.", "čerpadlo odstředivé"
        ) == []

    def test_kontrola_uvadi_chybny_tvar(self):
        vysledek = zvaliduj_preklad(
            "Replace the seal on the centrifugal pump.",
            "Vyměňte těsnění na odstředovém čerpadle.",
            [_termin("centrifugal pump", "čerpadlo odstředivé")],
        )
        assert vysledek.kontroly[0].chybne_tvary == (("odstředovém", "odstředivé"),)


class TestCiselnikyAOdvozeneTvary:
    def _druh_poruchy(self) -> NalezenyTermin:
        return NalezenyTermin(
            polozka=PolozkaGlosare(id="G9", termin_en="Other", termin_cs="Jiné",
                                   kategorie=KATEGORIE_DRUHU_PORUCHY),
            skore=0.95,
            zpusob=ZPUSOB_PRIMY,
        )

    def test_druh_poruchy_se_nehleda_v_beznem_slove(self):
        vysledek = zvaliduj_preklad(
            "Ensure that all other employees are out of the area.",
            "Ujistěte se, že všichni ostatní zaměstnanci opustili oblast.",
            [self._druh_poruchy()],
        )
        assert vysledek.pocet_ocekavanych == 0

    def test_druh_poruchy_jako_hodnota_ciselniku(self):
        vysledek = zvaliduj_preklad(
            "Failure mode: Other", "Druh poruchy: Jiné", [self._druh_poruchy()]
        )
        assert vysledek.pocet_ocekavanych == 1
        assert vysledek.pocet_dodrzenych == 1

    def test_privlastek_prelozeny_pridavnym_jmenem(self):
        vysledek = zvaliduj_preklad(
            "Employees who do service and maintenance work must follow the procedure.",
            "Zaměstnanci, kteří provádějí servisní a údržbářské práce, musí dodržovat postup.",
            [_termin("maintenance", "údržba")],
        )
        assert vysledek.pocet_dodrzenych == 1
        assert vysledek.kontroly[0].odvozeny_tvar == "údržbářské"

    def test_odvozene_slovo_mimo_privlastek_neplati(self):
        vysledek = zvaliduj_preklad(
            "Plan the maintenance.", "Naplánujte údržbářské.", [_termin("maintenance", "údržba")]
        )
        assert vysledek.pocet_dodrzenych == 0


class TestSlozeninyACinnosti:
    def test_nemecka_slozenina_obsahuje_termin(self):
        assert obsahuje_termin("Ersetzen Sie das Pumpenlaufrad.", "Laufrad", jazyk="de")

    def test_slozenina_s_terminem_na_zacatku_neplati(self):
        assert not obsahuje_termin("Prüfen Sie den Lagerbestand.", "Lager", jazyk="de")

    def test_slozeniny_se_hledaji_jen_v_nemcine(self):
        assert not obsahuje_termin("Vyměňte čerpadlokolo.", "kolo", jazyk="cs")

    def test_udrzbova_cinnost_vyjadrena_slovesem(self):
        cinnost = NalezenyTermin(
            polozka=PolozkaGlosare(
                id="G5", terminy={"en": "Check", "fr": "Vérification"},
                kategorie=KATEGORIE_UDRZBOVE_CINNOSTI,
            ),
            skore=0.95,
            zpusob=ZPUSOB_PRIMY,
        )
        vysledek = zvaliduj_preklad(
            "Check the gate valve.", "Vérifiez le robinet-vanne.", [cinnost], "en", "fr"
        )
        assert vysledek.pocet_dodrzenych == 1
        assert vysledek.kontroly[0].odvozeny_tvar == "Vérifiez"
