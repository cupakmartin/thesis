# -*- coding: utf-8 -*-
from __future__ import annotations

from app.jadro.glosar import Glosar, PolozkaGlosare


def _polozka() -> PolozkaGlosare:
    return PolozkaGlosare(
        id="G1",
        terminy={"en": "nut", "cs": "matice", "de": "Mutter", "zh": "螺母", "ja": "ナット"},
        kategorie="spojovací materiál",
        nespravne_podle_jazyka={"cs": "ořech", "de": "Nuss"},
        strojove={"de", "zh", "ja"},
    )


def _glosar(*polozky: PolozkaGlosare) -> Glosar:
    glosar = Glosar()
    glosar._polozky = list(polozky)
    glosar._sestav_mapu_tvaru()
    return glosar


class TestPolozka:
    def test_puvodni_konstruktor_zustava_funkcni(self):
        p = PolozkaGlosare(id="G1", termin_en="nut", termin_cs="matice", nespravne="ořech")
        assert p.terminy == {"en": "nut", "cs": "matice"}
        assert p.nespravne_v("cs") == "ořech"
        assert p.termin_en == "nut"
        assert p.nespravne == "ořech"

    def test_termin_v_libovolnem_jazyce(self):
        p = _polozka()
        assert p.termin("de") == "Mutter"
        assert p.termin("fr") == ""
        assert p.jazyky == ["en", "cs", "de", "zh", "ja"]

    def test_zmena_terminu_pres_puvodni_nazev(self):
        p = _polozka()
        p.termin_cs = "matka"
        assert p.terminy["cs"] == "matka"

    def test_dokument_pro_vektor_obsahuje_vsechny_jazyky(self):
        dokument = _polozka().jako_dokument()
        for termin in ("nut", "matice", "Mutter", "螺母", "ナット"):
            assert termin in dokument


class TestCsv:
    def test_novy_format_tam_a_zpet(self, tmp_path):
        cesta = tmp_path / "glosar.csv"
        _glosar(_polozka()).uloz_do_csv(cesta)

        nacteny = Glosar()
        nacteny.nacti_z_csv(cesta)
        p = nacteny.polozky[0]
        assert p.terminy == _polozka().terminy
        assert p.nespravne_podle_jazyka == {"cs": "ořech", "de": "Nuss"}
        assert p.strojove == {"de", "zh", "ja"}
        assert p.kategorie == "spojovací materiál"

    def test_puvodni_format_se_nacte(self, tmp_path):
        cesta = tmp_path / "glosar.csv"
        cesta.write_text(
            "ID;TERMIN_EN;TERMIN_CS;KATEGORIE;DEFINICE;NESPRAVNE;ZDROJ\n"
            "G0135;nut;matice;spojovací materiál;Protikus šroubu.;ořech;firemní glosář\n",
            encoding="utf-8",
        )
        glosar = Glosar()
        glosar.nacti_z_csv(cesta)
        p = glosar.polozky[0]
        assert p.terminy == {"en": "nut", "cs": "matice"}
        assert p.nespravne_v("cs") == "ořech"
        assert p.strojove == set()


class TestVyhledani:
    def test_presna_shoda_v_nemcine(self):
        assert _glosar(_polozka()).najdi_presnou_shodu("Mutter", "de").id == "G1"

    def test_presna_shoda_v_japonstine(self):
        assert _glosar(_polozka()).najdi_presnou_shodu("ナット", "ja").id == "G1"

    def test_termin_uvnitr_cinske_vety_bez_mezer(self):
        nalezene = _glosar(_polozka()).najdi_doslovne("用扳手拧紧螺母。")
        assert [n.polozka.id for n in nalezene] == ["G1"]

    def test_nemecky_termin_ve_vete(self):
        nalezene = _glosar(_polozka()).najdi_doslovne("Ziehen Sie die Mutter fest.")
        assert [n.polozka.id for n in nalezene] == ["G1"]
