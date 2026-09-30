# -*- coding: utf-8 -*-
from __future__ import annotations

from app.jadro.duplicity import (
    Dvojice,
    UnionFind,
    ZaznamPolozky,
    _rozloz_na_uplne_skupiny,
)


def _dvojice(a: int, b: int, skore: float = 0.9) -> Dvojice:
    return Dvojice(
        index_a=a, index_b=b, podobnost_semanticka=skore,
        podobnost_lexikalni=skore, skore_atributu=0.7,
        skore=skore, prijata=True, rozpor_atributu=False,
    )


class TestUnionFind:
    def test_samostatne_prvky(self):
        struktura = UnionFind(3)
        assert len(struktura.skupiny()) == 3

    def test_spojeni_dvou_prvku(self):
        struktura = UnionFind(3)
        assert struktura.spoj(0, 1) is True
        assert len(struktura.skupiny()) == 2

    def test_opakovane_spojeni_nic_nezmeni(self):
        struktura = UnionFind(3)
        struktura.spoj(0, 1)
        assert struktura.spoj(0, 1) is False

    def test_tranzitivita(self):
        struktura = UnionFind(3)
        struktura.spoj(0, 1)
        struktura.spoj(1, 2)
        skupiny = list(struktura.skupiny().values())
        assert len(skupiny) == 1
        assert sorted(skupiny[0]) == [0, 1, 2]

    def test_nezavisle_skupiny(self):
        struktura = UnionFind(4)
        struktura.spoj(0, 1)
        struktura.spoj(2, 3)
        assert len(struktura.skupiny()) == 2


class TestRozlozNaUplneSkupiny:
    def test_dvojice_zustava_cela(self):
        vazby = {(0, 1): _dvojice(0, 1)}
        assert _rozloz_na_uplne_skupiny([0, 1], vazby) == [[0, 1]]

    def test_uplny_trojuhelnik_zustava_cely(self):
        vazby = {
            (0, 1): _dvojice(0, 1), (0, 2): _dvojice(0, 2), (1, 2): _dvojice(1, 2),
        }
        assert _rozloz_na_uplne_skupiny([0, 1, 2], vazby) == [[0, 1, 2]]

    def test_retez_se_rozpadne(self):
        vazby = {(0, 1): _dvojice(0, 1, 0.95), (1, 2): _dvojice(1, 2, 0.80)}
        skupiny = _rozloz_na_uplne_skupiny([0, 1, 2], vazby)
        assert [0, 1] in skupiny
        for skupina in skupiny:
            assert not (0 in skupina and 2 in skupina)

    def test_prednost_ma_silnejsi_vazba(self):
        vazby = {(0, 1): _dvojice(0, 1, 0.70), (1, 2): _dvojice(1, 2, 0.98)}
        skupiny = _rozloz_na_uplne_skupiny([0, 1, 2], vazby)
        assert [1, 2] in skupiny

    def test_osamocene_prvky_se_nevraci(self):
        vazby = {(0, 1): _dvojice(0, 1)}
        skupiny = _rozloz_na_uplne_skupiny([0, 1, 2], vazby)
        assert all(len(s) >= 2 for s in skupiny)


class TestZaznamPolozky:
    def test_text_obsahuje_popis(self):
        zaznam = ZaznamPolozky(itemnum="1", popis="Ložisko 6204",
                               komoditni_skupina="BEARINGS")
        assert "Ložisko 6204" in zaznam.text_pro_porovnani()

    def test_vyrobce_se_nezahrnuje(self):
        zaznam = ZaznamPolozky(itemnum="1", popis="Ložisko 6204", vyrobce="SKF")
        assert "SKF" not in zaznam.text_pro_porovnani()

    def test_prazdna_komoditni_skupina(self):
        zaznam = ZaznamPolozky(itemnum="1", popis="Ložisko 6204")
        assert zaznam.text_pro_porovnani() == "Ložisko 6204"
