# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from app.jadro.glosar import Glosar, NalezenyTermin, PolozkaGlosare, ZPUSOB_PRIMY
from app.jadro.llm import StubPoskytovatel
from app.jadro.rag import (
    ZPUSOB_GLOSAR,
    PozadavekPrekladu,
    PrekladacRAG,
    _sestav_blok_glosare,
    je_kratky_vstup,
)
from app.jadro.validace import obsahuje_termin, zvaliduj_preklad

MATICE = PolozkaGlosare(
    id="G1",
    terminy={"en": "nut", "cs": "matice", "de": "Mutter", "ja": "ナット", "zh": "螺母"},
    nespravne_podle_jazyka={"cs": "ořech", "de": "Nuss"},
)


def _prekladac(stub: StubPoskytovatel | None = None) -> PrekladacRAG:
    glosar = Glosar()
    glosar._polozky = [MATICE]
    glosar._sestav_mapu_tvaru()
    return PrekladacRAG(zdroj_glosare=glosar, poskytovatel=stub or StubPoskytovatel())


class TestKratkyVstupBezMezer:
    @pytest.mark.parametrize("text", ["螺母", "安全眼镜", "ナット", "工具："])
    def test_kratky(self, text):
        assert je_kratky_vstup(text)

    @pytest.mark.parametrize("text", ["拧紧螺母。", "请拧紧安装螺栓上的螺母", "ナットを締めてください"])
    def test_vetny(self, text):
        assert not je_kratky_vstup(text)


class TestPrompt:
    def test_ceske_pravidlo_jen_pro_cestinu(self):
        prekladac = _prekladac()
        do_cestiny = prekladac.sestav_instrukci([], "en", "cs")
        do_nemciny = prekladac.sestav_instrukci([], "en", "de")

        assert "vyměňte oběžné kolo" in do_cestiny
        assert "vyměňte" not in do_nemciny
        assert "do němčiny" in do_nemciny
        assert "formálně a zdvořile" in do_nemciny

    def test_nespravna_varianta_podle_ciloveho_jazyka(self):
        terminy = [NalezenyTermin(MATICE, 1.0, ZPUSOB_PRIMY)]
        assert "Nuss" in _sestav_blok_glosare(terminy, "en", "de")
        assert "ořech" not in _sestav_blok_glosare(terminy, "en", "de")

    def test_nepodporovany_jazyk(self):
        with pytest.raises(ValueError, match="není podporován"):
            _prekladac().prelozi(PozadavekPrekladu(text="nut", cilovy_jazyk="pl"))


class TestGlosarMeziJazyky:
    def test_nemcina_do_japonstiny_z_glosare(self):
        stub = StubPoskytovatel()
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="Mutter", zdrojovy_jazyk="de", cilovy_jazyk="ja"))
        assert vysledek.preklad == "ナット"
        assert vysledek.zpusob == ZPUSOB_GLOSAR
        assert stub.zaznamenane_vstupy == []

    def test_chybejici_cilovy_jazyk_jde_na_model(self):
        stub = StubPoskytovatel({"nut": "écrou"})
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(
            text="nut", zdrojovy_jazyk="en", cilovy_jazyk="fr"))
        assert vysledek.preklad == "écrou"
        assert vysledek.zpusob != ZPUSOB_GLOSAR


class TestKontrola:
    def test_cinsky_termin_v_textu_bez_mezer(self):
        assert obsahuje_termin("请拧紧螺母。", "螺母")
        assert not obsahuje_termin("请拧紧螺栓。", "螺母")

    def test_nemecka_kontrola_dodrzeni(self):
        validace = zvaliduj_preklad(
            "Tighten the nut.", "Ziehen Sie die Nuss fest.",
            [NalezenyTermin(MATICE, 1.0, ZPUSOB_PRIMY)], "en", "de",
        )
        assert validace.pocet_dodrzenych == 0
        assert validace.pocet_nespravnych_variant == 1
