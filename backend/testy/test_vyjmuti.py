# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest


@pytest.fixture
def prostredi(tmp_path_factory):
    import os

    docasny = tmp_path_factory.mktemp("vyjmuti")
    os.environ["MRO_SOUBOR_DATABAZE"] = str(docasny / "test.db")

    from app.config import nastaveni

    nastaveni.cache_clear()
    from app.db import inicializuj_schema, nyni, pripoj, smaz_vse

    inicializuj_schema()
    smaz_vse()

    with pripoj() as spojeni:
        spojeni.execute(
            "INSERT INTO behy (zalozeno, stav, metoda, nastaveni_json, "
            "pocet_polozek, pocet_klastru, pocet_duplicit, doba_s, spustil) "
            "VALUES (?, 'dokonceno', 'hybridni', '{}', 3, 1, 2, 0.1, 'test')",
            (nyni(),),
        )
        for itemnum, popis in (
            ("100001", "Pneumatický válec 80/25 mm uchycení příruba"),
            ("100002", "válec 80/25 mm uchycení příruba Pneumatický"),
            ("100003", "Pneumatický válec 80/25 mm uchycení závit"),
        ):
            spojeni.execute(
                "INSERT INTO polozky (itemnum, description, stav_konsolidace) "
                "VALUES (?, ?, 'aktivni')",
                (itemnum, popis),
            )
        spojeni.execute(
            "INSERT INTO klastry (id, beh_id, poradi, velikost, "
            "prumerna_podobnost, minimalni_podobnost, navrzeny_zastupce) "
            "VALUES (1, 1, 1, 3, 0.85, 0.80, '100001')"
        )
        for itemnum in ("100001", "100002", "100003"):
            spojeni.execute(
                "INSERT INTO klastr_cleny (klastr_id, itemnum) VALUES (1, ?)",
                (itemnum,),
            )
        for a, b, skore in (
            ("100001", "100002", 0.92),
            ("100001", "100003", 0.80),
            ("100002", "100003", 0.83),
        ):
            spojeni.execute(
                "INSERT INTO dvojice (klastr_id, itemnum_a, itemnum_b, "
                "podobnost_semanticka, podobnost_lexikalni, skore_atributu, "
                "skore) VALUES (1, ?, ?, ?, ?, 1.0, ?)",
                (a, b, skore, skore, skore),
            )

    yield docasny
    nastaveni.cache_clear()


def _cleny(klastr_id: int) -> list[str]:
    from app.db import pripoj

    with pripoj(pouze_cteni=True) as spojeni:
        return [
            r["itemnum"] for r in spojeni.execute(
                "SELECT itemnum FROM klastr_cleny WHERE klastr_id = ? "
                "ORDER BY itemnum", (klastr_id,)
            ).fetchall()
        ]


class TestVyjmutiZeSkupiny:
    def test_zbyle_polozky_ve_skupine_zustanou(self, prostredi):
        from app.sluzby.slucovani import sluzba_slucovani

        vysledek = sluzba_slucovani().vyjmi_clena(1, "100003", kdo="test")

        assert vysledek["zbylo_clenu"] == 2
        assert vysledek["skupina_zrusena"] is False
        assert _cleny(1) == ["100001", "100002"]

    def test_velikost_a_podobnost_se_prepocitaji(self, prostredi):
        from app.db import pripoj
        from app.sluzby.slucovani import sluzba_slucovani

        sluzba_slucovani().vyjmi_clena(1, "100003", kdo="test")

        with pripoj(pouze_cteni=True) as spojeni:
            klastr = spojeni.execute(
                "SELECT * FROM klastry WHERE id = 1"
            ).fetchone()
        assert klastr["velikost"] == 2
        assert klastr["prumerna_podobnost"] == pytest.approx(0.92)
        assert klastr["minimalni_podobnost"] == pytest.approx(0.92)

    def test_dvojice_s_vyjmutou_polozkou_zmizi(self, prostredi):
        from app.db import pripoj
        from app.sluzby.slucovani import sluzba_slucovani

        sluzba_slucovani().vyjmi_clena(1, "100003", kdo="test")

        with pripoj(pouze_cteni=True) as spojeni:
            zbyle = spojeni.execute(
                "SELECT itemnum_a, itemnum_b FROM dvojice WHERE klastr_id = 1"
            ).fetchall()
        assert len(zbyle) == 1
        assert "100003" not in (zbyle[0]["itemnum_a"], zbyle[0]["itemnum_b"])

    def test_zastupce_se_prevede_zustane_li_ve_skupine(self, prostredi):
        from app.db import pripoj
        from app.sluzby.slucovani import sluzba_slucovani

        sluzba_slucovani().vyjmi_clena(1, "100001", kdo="test")

        with pripoj(pouze_cteni=True) as spojeni:
            zastupce = spojeni.execute(
                "SELECT navrzeny_zastupce FROM klastry WHERE id = 1"
            ).fetchone()["navrzeny_zastupce"]
        assert zastupce in _cleny(1)

    def test_skupina_o_jedinem_clenu_se_odstrani(self, prostredi):
        from app.db import pripoj
        from app.sluzby.slucovani import sluzba_slucovani

        sluzba = sluzba_slucovani()
        sluzba.vyjmi_clena(1, "100003", kdo="test")
        vysledek = sluzba.vyjmi_clena(1, "100002", kdo="test")

        assert vysledek["skupina_zrusena"] is True
        with pripoj(pouze_cteni=True) as spojeni:
            assert spojeni.execute(
                "SELECT COUNT(*) FROM klastry WHERE id = 1"
            ).fetchone()[0] == 0

    def test_neznama_polozka_je_odmitnuta(self, prostredi):
        from app.sluzby.slucovani import ChybaSlucovani, sluzba_slucovani

        with pytest.raises(ChybaSlucovani, match="999999"):
            sluzba_slucovani().vyjmi_clena(1, "999999", kdo="test")

    def test_po_rozhodnuti_nelze_vyjmout(self, prostredi):
        from app.sluzby.slucovani import ChybaSlucovani, sluzba_slucovani

        sluzba = sluzba_slucovani()
        sluzba.rozhodni(klastr_id=1, vysledek="zamitnuto", kdo="test")
        with pytest.raises(ChybaSlucovani, match="rozhodnut"):
            sluzba.vyjmi_clena(1, "100003", kdo="test")


class TestSpravaBehu:
    def test_smazani_vsech_behu(self, prostredi):
        from app.db import pripoj
        from app.sluzby.deduplikace import sluzba_deduplikace

        pocet = sluzba_deduplikace().smaz_vsechny_behy()

        assert pocet == 1
        with pripoj(pouze_cteni=True) as spojeni:
            assert spojeni.execute("SELECT COUNT(*) FROM behy").fetchone()[0] == 0
            assert spojeni.execute(
                "SELECT COUNT(*) FROM klastry"
            ).fetchone()[0] == 0
            assert spojeni.execute(
                "SELECT COUNT(*) FROM klastr_cleny"
            ).fetchone()[0] == 0

    def test_polozky_se_vrati_do_puvodniho_stavu(self, prostredi):
        from app.db import pripoj
        from app.sluzby.deduplikace import sluzba_deduplikace

        with pripoj() as spojeni:
            spojeni.execute(
                "UPDATE polozky SET stav_konsolidace = 'slouceno', "
                "slouceno_do = '100001' WHERE itemnum = '100002'"
            )

        sluzba_deduplikace().smaz_vsechny_behy()

        with pripoj(pouze_cteni=True) as spojeni:
            radek = spojeni.execute(
                "SELECT stav_konsolidace, slouceno_do FROM polozky "
                "WHERE itemnum = '100002'"
            ).fetchone()
        assert radek["stav_konsolidace"] == "aktivni"
        assert radek["slouceno_do"] is None

    def test_statistiky_se_vztahuji_k_behu(self, prostredi):
        from app.db import nyni, pripoj
        from app.sluzby.slucovani import sluzba_slucovani

        with pripoj() as spojeni:
            spojeni.execute(
                "INSERT INTO behy (id, zalozeno, stav, metoda, nastaveni_json, "
                "pocet_polozek, pocet_klastru, pocet_duplicit, doba_s, spustil) "
                "VALUES (2, ?, 'dokonceno', 'hybridni', '{}', 3, 1, 2, 0.1, 'test')",
                (nyni(),),
            )
            spojeni.execute(
                "INSERT INTO klastry (id, beh_id, poradi, velikost, "
                "prumerna_podobnost, minimalni_podobnost, stav) "
                "VALUES (2, 2, 1, 2, 0.9, 0.9, 'ke_kontrole')"
            )

        za_beh = sluzba_slucovani().statistiky(beh_id=2)
        celkem = sluzba_slucovani().statistiky()

        assert za_beh["ke_kontrole"] == 1
        assert celkem["ke_kontrole"] == 2
