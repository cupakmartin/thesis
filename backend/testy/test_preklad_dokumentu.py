# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from testy.pomocne_pdf import sestav_pdf

ODPOVEDI = {
    "Tools required": "Potřebné nástroje",
    "Replace the impeller": "Vyměňte oběžné kolo.",
    "Drain the oil": "Vypusťte olej.",
}


def _predstirany_model(self, systemova_instrukce, uzivatelsky_vstup, **kw):
    from app.jadro.llm import OdpovedLLM

    for klic, hodnota in ODPOVEDI.items():
        if klic in uzivatelsky_vstup:
            return OdpovedLLM(text=hodnota, model="zkousime:1b", doba_s=0.01)
    return OdpovedLLM(text=uzivatelsky_vstup, model="zkousime:1b", doba_s=0.01)


@pytest.fixture(scope="module")
def prostredi(tmp_path_factory):
    import os

    docasny = tmp_path_factory.mktemp("dokument")
    os.environ["MRO_SOUBOR_DATABAZE"] = str(docasny / "test.db")

    from app.config import nastaveni

    nastaveni.cache_clear()
    from app.db import inicializuj_schema, smaz_vse

    inicializuj_schema()
    smaz_vse()
    yield docasny
    nastaveni.cache_clear()


@pytest.fixture(autouse=True)
def _model(monkeypatch, prostredi):
    from app.jadro.llm import OllamaPoskytovatel

    monkeypatch.setattr(OllamaPoskytovatel, "generuj", _predstirany_model)


@pytest.fixture
def klient(prostredi) -> Iterator[TestClient]:
    from app.main import vytvor_aplikaci

    with TestClient(vytvor_aplikaci()) as testovaci_klient:
        yield testovaci_klient


DOKUMENT = "Tools required:\n1. Nut\n\nReplace the impeller."


class TestSluzba:
    def test_prubeh_udalosti_a_vysledny_text(self, prostredi):
        from app.sluzby.prekladani import SluzbaPrekladu

        udalosti = list(SluzbaPrekladu().prelozi_dokument(DOKUMENT))
        typy = [u["typ"] for u in udalosti]

        assert typy == ["plan", "usek", "usek", "usek", "hotovo"]
        assert udalosti[0]["pocet_useku"] == 3
        assert udalosti[-1]["preklad"] == (
            "Potřebné nástroje:\n1. Matice\n\nVyměňte oběžné kolo."
        )

    def test_termin_glosare_v_seznamu_jde_z_glosare(self, prostredi):
        from app.sluzby.prekladani import SluzbaPrekladu

        useky = [u for u in SluzbaPrekladu().prelozi_dokument(DOKUMENT)
                 if u["typ"] == "usek"]
        polozka = next(u for u in useky if u["zdroj"] == "Nut")
        assert polozka["zpusob"] == "glosář"
        assert polozka["preklad"] == "Matice"
        assert polozka["odrazka"] == "1. "

    def test_dokument_se_ulozi_jako_jeden_preklad(self, prostredi):
        from app.db import pripoj
        from app.sluzby.prekladani import SluzbaPrekladu

        with pripoj(pouze_cteni=True) as spojeni:
            pred = spojeni.execute("SELECT COUNT(*) FROM preklady").fetchone()[0]
        list(SluzbaPrekladu().prelozi_dokument(DOKUMENT, kdo="tester"))
        with pripoj(pouze_cteni=True) as spojeni:
            radky = spojeni.execute(
                "SELECT zdrojovy_text, vytvoril FROM preklady ORDER BY id DESC"
            ).fetchall()

        assert len(radky) == pred + 1
        assert radky[0]["zdrojovy_text"] == DOKUMENT
        assert radky[0]["vytvoril"] == "tester"

    def test_text_bez_slov_je_odmitnut(self, prostredi):
        from app.sluzby.prekladani import SluzbaPrekladu

        with pytest.raises(ValueError):
            list(SluzbaPrekladu().prelozi_dokument("DN50 PN16\n\n6204"))


class TestRozhrani:
    def test_dokument_se_streamuje_po_usecich(self, klient):
        with klient.stream("POST", "/api/preklad/dokument", json={
            "text": DOKUMENT, "zdrojovy_jazyk": "en", "cilovy_jazyk": "cs",
        }) as odpoved:
            assert odpoved.status_code == 200
            udalosti = [json.loads(r) for r in odpoved.iter_lines() if r]

        assert [u["typ"] for u in udalosti][0] == "plan"
        assert udalosti[-1]["typ"] == "hotovo"
        assert "Matice" in udalosti[-1]["preklad"]

    def test_stejny_jazyk_je_chyba_pred_zahajenim(self, klient):
        odpoved = klient.post("/api/preklad/dokument", json={
            "text": DOKUMENT, "zdrojovy_jazyk": "cs", "cilovy_jazyk": "cs",
        })
        assert odpoved.status_code == 400

    def test_pdf_se_prevede_na_text(self, klient):
        pdf = sestav_pdf([["Tools required:", "1. Torque wrench",
                           "Drain the oil from the gear-",
                           "box before the inspection."]])
        odpoved = klient.post("/api/preklad/pdf", content=pdf,
                              headers={"Content-Type": "application/pdf"})

        assert odpoved.status_code == 200
        data = odpoved.json()
        assert data["pocet_stran"] == 1
        assert data["text"].split("\n") == [
            "Tools required:", "1. Torque wrench",
            "Drain the oil from the gearbox before the inspection.",
        ]

    def test_jiny_soubor_nez_pdf(self, klient):
        odpoved = klient.post("/api/preklad/pdf", content=b"neni pdf",
                              headers={"Content-Type": "application/pdf"})
        assert odpoved.status_code == 422

    def test_sken_bez_textu(self, klient):
        odpoved = klient.post("/api/preklad/pdf", content=sestav_pdf([[]]),
                              headers={"Content-Type": "application/pdf"})
        assert odpoved.status_code == 422
        assert "OCR" in odpoved.json()["detail"]

    def test_jednotlivy_preklad_ma_horni_mez_delky(self, klient):
        odpoved = klient.post("/api/preklad", json={"text": "word " * 1000})
        assert odpoved.status_code == 422
