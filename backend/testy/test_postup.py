# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
import pytest

from app.jadro.index_faiss import _bez_sebe
from app.jadro.postup import (
    BEZ_SLEDOVANI,
    STAV_BEZI,
    STAV_CHYBA,
    STAV_DOKONCENO,
    STAV_NECINNY,
    SledovaniPostupu,
)


class Hodiny:
    def __init__(self) -> None:
        self.cas = 100.0

    def __call__(self) -> float:
        return self.cas


@pytest.fixture
def hodiny() -> Hodiny:
    return Hodiny()


class TestSledovaniPostupu:
    def test_necinne_sledovani(self):
        snimek = SledovaniPostupu().snimek()
        assert snimek["stav"] == STAV_NECINNY
        assert snimek["zbyva_s"] is None

    def test_pred_prvni_fazi_plati_soucet_odhadu(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 10.0), ("b", "B", 20.0)])
        assert postup.snimek()["zbyva_s"] == 30.0

    def test_odhad_z_namerene_rychlosti(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 10.0)])
        postup.faze("a", 1000)
        hodiny.cas += 20
        postup.posun(250)
        snimek = postup.snimek()
        assert snimek["odhad_z_mereni"]
        assert snimek["zbyva_s"] == pytest.approx(60.0)
        assert snimek["faze"] == "A"
        assert snimek["faze_poradi"] == 1

    def test_dalsi_faze_se_kalibruji_skutecnosti(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 10.0), ("b", "B", 10.0)])
        postup.faze("a", 100)
        hodiny.cas += 20
        postup.faze("b", 100)
        assert postup.snimek()["zbyva_s"] == pytest.approx(20.0)

    def test_kalibrace_je_omezena(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 1.0), ("b", "B", 10.0)])
        postup.faze("a")
        hodiny.cas += 1000
        postup.faze("b")
        assert postup.snimek()["zbyva_s"] == pytest.approx(50.0)

    def test_dokonceni_a_chyba(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 5.0)])
        hodiny.cas += 3
        postup.dokonci()
        snimek = postup.snimek()
        assert snimek["stav"] == STAV_DOKONCENO
        assert snimek["zbyva_s"] == 0.0
        assert snimek["uplynulo_s"] == 3.0

        postup.zacni("uloha", [("a", "A", 5.0)])
        postup.selhej("porucha")
        assert postup.snimek()["stav"] == STAV_CHYBA
        assert postup.snimek()["chyba"] == "porucha"

    def test_soubezne_spusteni_je_odmitnuto(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [])
        assert postup.bezi
        with pytest.raises(RuntimeError):
            postup.zacni("uloha", [])
        assert postup.snimek()["stav"] == STAV_BEZI

    def test_neznama_faze_se_prida(self, hodiny):
        postup = SledovaniPostupu(hodiny)
        postup.zacni("uloha", [("a", "A", 5.0)])
        postup.faze("x", 10)
        snimek = postup.snimek()
        assert snimek["pocet_fazi"] == 2
        assert snimek["faze_poradi"] == 2

    def test_bez_sledovani_nic_neeviduje(self):
        BEZ_SLEDOVANI.faze("a", 10)
        BEZ_SLEDOVANI.posun(5)
        assert BEZ_SLEDOVANI.snimek()["hotovo"] == 0


class TestVynechaniSebe:
    def _puvodni(self, podobnosti, indexy, k):
        vysledne_p = np.zeros((len(indexy), k), dtype=np.float32)
        vysledne_i = np.full((len(indexy), k), -1, dtype=np.int64)
        for radek in range(len(indexy)):
            zapsano = 0
            for sloupec in range(indexy.shape[1]):
                soused = int(indexy[radek, sloupec])
                if soused == radek or soused < 0:
                    continue
                if zapsano >= k:
                    break
                vysledne_p[radek, zapsano] = podobnosti[radek, sloupec]
                vysledne_i[radek, zapsano] = soused
                zapsano += 1
        return vysledne_p, vysledne_i

    @pytest.mark.parametrize("k", [1, 3, 5])
    def test_shoda_s_postupnym_vynechanim(self, k):
        generator = np.random.default_rng(7)
        indexy = generator.integers(-1, 12, size=(12, min(k + 1, 4))).astype(np.int64)
        indexy[3, 0] = 3
        indexy[5, -1] = 5
        podobnosti = generator.random(indexy.shape).astype(np.float32)
        nove_p, nove_i = _bez_sebe(podobnosti, indexy, k)
        stare_p, stare_i = self._puvodni(podobnosti, indexy, k)
        np.testing.assert_array_equal(nove_i, stare_i)
        np.testing.assert_allclose(nove_p, stare_p)
