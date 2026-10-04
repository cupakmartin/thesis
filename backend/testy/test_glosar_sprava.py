# -*- coding: utf-8 -*-
from __future__ import annotations

import re

import pytest

from app.jadro.llm import OdpovedLLM

PREKLADY = {
    "angličtina": "nut", "čeština": "matice", "němčina": "Mutter",
    "italština": "dado", "španělština": "tuerca", "francouzština": "écrou",
    "čínština": "螺母", "japonština": "ナット",
}


class JazykovyStub:
    def __init__(self) -> None:
        self.volani: list[str] = []

    def generuj(self, systemova_instrukce, uzivatelsky_vstup, **kw) -> OdpovedLLM:
        cil = re.search(r"v jazyce: (\S+)\.", systemova_instrukce).group(1)
        self.volani.append(cil)
        return OdpovedLLM(text=PREKLADY[cil] + ".", model="stub", doba_s=0.0)


@pytest.fixture
def sluzba(tmp_path, monkeypatch):
    from app.config import nastaveni

    monkeypatch.setenv("MRO_SOUBOR_DATABAZE", str(tmp_path / "test.db"))
    monkeypatch.setenv("MRO_SOUBOR_GLOSARE", str(tmp_path / "glosar.csv"))
    nastaveni.cache_clear()
    from app.db import inicializuj_schema
    from app.jadro.glosar import Glosar
    from app.sluzby.glosar_sprava import SluzbaGlosare

    inicializuj_schema()
    glosar = Glosar()
    sluzba = SluzbaGlosare(zdroj=glosar, poskytovatel=JazykovyStub())
    yield sluzba
    nastaveni.cache_clear()


class TestPridani:
    def test_jeden_jazyk_nestaci(self, sluzba):
        from app.sluzby.glosar_sprava import ChybaGlosare

        with pytest.raises(ChybaGlosare, match="dvou jazycích"):
            sluzba.pridej({"en": "nut", "cs": ""}, kategorie="spojovací materiál")

    def test_kategorie_je_povinna(self, sluzba):
        from app.sluzby.glosar_sprava import ChybaGlosare

        with pytest.raises(ChybaGlosare, match="kategorii"):
            sluzba.pridej({"en": "nut", "cs": "matice"}, kategorie=" ")

    def test_ostatni_jazyky_doplni_model(self, sluzba):
        polozka = sluzba.pridej(
            {"en": "nut", "cs": "matice"}, kategorie="spojovací materiál",
            nespravne={"cs": "ořech"},
        )
        assert polozka.terminy["de"] == "Mutter"
        assert polozka.terminy["ja"] == "ナット"
        assert polozka.strojove == {"de", "it", "es", "fr", "zh", "ja"}
        assert polozka.nespravne_v("cs") == "ořech"
        assert sorted(sluzba.poskytovatel.volani) == sorted(
            ["němčina", "italština", "španělština", "francouzština", "čínština", "japonština"]
        )

    def test_ulozi_se_do_csv(self, sluzba, tmp_path):
        sluzba.pridej({"en": "nut", "de": "Mutter", "cs": "matice"}, kategorie="spoj")
        obsah = (tmp_path / "glosar.csv").read_text(encoding="utf-8")
        assert "Mutter" in obsah and "ナット" in obsah

    def test_id_se_neopakuje_po_smazani(self, sluzba):
        prvni = sluzba.pridej({"en": "nut", "cs": "matice"}, kategorie="spoj")
        druhy = sluzba.pridej({"en": "bolt", "cs": "šroub"}, kategorie="spoj")
        sluzba.glosar.smaz(prvni.id)
        treti = sluzba.pridej({"en": "washer", "cs": "podložka"}, kategorie="spoj")
        assert treti.id not in {druhy.id}
        assert len({p.id for p in sluzba.glosar.polozky}) == len(sluzba.glosar.polozky)

    def test_nova_kategorie_zustane_i_po_smazani_terminu(self, sluzba):
        polozka = sluzba.pridej({"en": "nut", "cs": "matice"}, kategorie="Nová kategorie")
        sluzba.glosar.smaz(polozka.id)
        assert "Nová kategorie" in sluzba.kategorie()


class TestUprava:
    def test_oprava_strojoveho_prekladu_jej_overi(self, sluzba):
        polozka = sluzba.pridej({"en": "nut", "cs": "matice"}, kategorie="spoj")
        terminy = dict(polozka.terminy, de="Schraubenmutter")
        upravena = sluzba.uprav(polozka.id, terminy, kategorie="spoj")

        assert upravena.terminy["de"] == "Schraubenmutter"
        assert "de" not in upravena.strojove
        assert "fr" in upravena.strojove

    def test_potvrzeni_bez_zmeny(self, sluzba):
        polozka = sluzba.pridej({"en": "nut", "cs": "matice"}, kategorie="spoj")
        upravena = sluzba.uprav(
            polozka.id, dict(polozka.terminy), kategorie="spoj", overene=["fr", "ja"]
        )
        assert upravena.strojove == {"de", "it", "es", "zh"}

    def test_neznamy_termin(self, sluzba):
        from app.sluzby.glosar_sprava import TerminNenalezen

        with pytest.raises(TerminNenalezen):
            sluzba.uprav("G9999", {"en": "a", "cs": "b"}, kategorie="x")


class TestHromadneDoplneni:
    def test_doplni_puvodni_dvojjazycne_terminy(self, sluzba):
        from app.jadro.glosar import PolozkaGlosare

        sluzba.glosar.pridej(PolozkaGlosare(id="G0135", termin_en="nut", termin_cs="matice"))
        udalosti = list(sluzba.dopln_vse())

        assert [u["typ"] for u in udalosti] == ["plan", "termin", "hotovo"]
        assert udalosti[1]["doplneno"] == ["de", "it", "es", "fr", "zh", "ja"]
        assert sluzba.k_doplneni() == []


class TestRozhrani:
    @pytest.fixture
    def klient(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from app.config import nastaveni

        monkeypatch.setenv("MRO_SOUBOR_DATABAZE", str(tmp_path / "api.db"))
        nastaveni.cache_clear()
        from app.main import vytvor_aplikaci

        with TestClient(vytvor_aplikaci()) as testovaci_klient:
            yield testovaci_klient
        nastaveni.cache_clear()

    def test_seznam_jazyku(self, klient):
        kody = [j["kod"] for j in klient.get("/api/system/jazyky").json()]
        assert kody == ["en", "cs", "de", "it", "es", "fr", "zh", "ja"]

    def test_jeden_jazyk_je_odmitnut(self, klient):
        odpoved = klient.post("/api/glosar", json={
            "terminy": {"en": "nut"}, "kategorie": "spoj",
        })
        assert odpoved.status_code == 400
        assert "dvou jazycích" in odpoved.json()["detail"]
