# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Sequence

from app.config import Nastaveni
from app.jadro.glosar import ZPUSOB_PRIMY, Glosar, NalezenyTermin, PolozkaGlosare
from app.jadro.llm import OdpovedLLM, StubPoskytovatel
from app.jadro.rag import ZPUSOB_TEXT, PlanPrekladu, PozadavekPrekladu, PrekladacRAG
from app.sluzby.prekladani import SluzbaPrekladu

VETA = "Replace the seal on the centrifugal pump."


class PostupnyStub(StubPoskytovatel):
    def __init__(self, odpovedi: list[str]) -> None:
        super().__init__()
        self._postupne = list(odpovedi)

    def generuj(
        self,
        systemova_instrukce: str,
        uzivatelsky_vstup: str,
        temperature: float | None = None,
        model: str | None = None,
        max_tokenu: int | None = None,
        stop: Sequence[str] | None = None,
    ) -> OdpovedLLM:
        super().generuj(systemova_instrukce, uzivatelsky_vstup, temperature, model,
                        max_tokenu, stop)
        return OdpovedLLM(text=self._postupne.pop(0), model="stub", doba_s=0.0)


class GlosarSPevnymVyhledanim(Glosar):
    def najdi_relevantni(
        self, text: str, pocet: int | None = None, prah: float | None = None
    ) -> list[NalezenyTermin]:
        return [NalezenyTermin(self.polozky[0], 0.95, ZPUSOB_PRIMY)]


def _prekladac(stub: StubPoskytovatel, konfigurace: Nastaveni | None = None) -> PrekladacRAG:
    glosar = GlosarSPevnymVyhledanim()
    glosar.pridej(PolozkaGlosare(id="G1", termin_en="centrifugal pump",
                                 termin_cs="čerpadlo odstředivé"))
    glosar.pridej(PolozkaGlosare(id="G2", termin_en="nut", termin_cs="matice",
                                 nespravne="ořech"))
    return PrekladacRAG(konfigurace=konfigurace, zdroj_glosare=glosar, poskytovatel=stub)


class TestOprava:
    def test_druhy_pokus_opravi_tvar_terminu(self):
        stub = PostupnyStub([
            "Vyměňte těsnění na odstředovém čerpadle.",
            "Vyměňte těsnění na odstředivém čerpadle.",
        ])
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text=VETA))

        assert vysledek.preklad == "Vyměňte těsnění na odstředivém čerpadle."
        assert vysledek.prvni_pokus == "Vyměňte těsnění na odstředovém čerpadle."
        assert vysledek.oprava is not None and vysledek.oprava.prijata
        instrukce_opravy = stub.zaznamenane_vstupy[1][0]
        assert "KONTROLA PŘEDCHOZÍHO POKUSU" in instrukce_opravy
        assert "odstředovém" in instrukce_opravy
        assert "centrifugal pump = odstředivé čerpadlo" in instrukce_opravy
        assert "slovo „odstředovém“ není správným tvarem slova „odstředivé“" in instrukce_opravy

    def test_horsi_druhy_pokus_se_neprevezme(self):
        stub = PostupnyStub([
            "Vyměňte těsnění na odstředovém čerpadle.",
            "Vyměňte těsnění čerpací stanice.",
        ])
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text=VETA))

        assert vysledek.preklad == "Vyměňte těsnění na odstředovém čerpadle."
        assert vysledek.prvni_pokus == ""
        assert vysledek.oprava is not None and not vysledek.oprava.prijata

    def test_spravny_preklad_se_neopakuje(self):
        stub = PostupnyStub(["Vyměňte těsnění na odstředivém čerpadle."])
        vysledek = _prekladac(stub).prelozi(PozadavekPrekladu(text=VETA))

        assert vysledek.oprava is None
        assert len(stub.zaznamenane_vstupy) == 1

    def test_opravu_lze_vypnout(self):
        stub = PostupnyStub(["Vyměňte těsnění na odstředovém čerpadle."])
        prekladac = _prekladac(stub, Nastaveni(oprava_podle_validace=False))
        vysledek = prekladac.prelozi(PozadavekPrekladu(text=VETA))

        assert vysledek.oprava is None
        assert len(stub.zaznamenane_vstupy) == 1

    def test_bez_glosare_se_neopravuje(self):
        prekladac = _prekladac(PostupnyStub(["x"]))
        plan = PlanPrekladu(
            zpusob=ZPUSOB_TEXT,
            nalezene_terminy=[NalezenyTermin(prekladac.glosar.polozky[0], 0.95, ZPUSOB_PRIMY)],
        )
        pozadavek = PozadavekPrekladu(text=VETA, pouzit_glosar=False)
        assert prekladac.oprav(pozadavek, plan, "Vyměňte těsnění čerpadla.") is None


class TestKontrolaPrekladuBezGlosare:
    def test_preklad_bez_glosare_se_meri_stejnymi_terminy(self):
        sluzba = SluzbaPrekladu(prekladac=_prekladac(StubPoskytovatel({"Nut": "Ořech"})))
        vysledek, validace = sluzba.prelozi(
            PozadavekPrekladu(text="Nut", pouzit_glosar=False), ulozit=False
        )

        assert vysledek.preklad == "Ořech"
        assert vysledek.nalezene_terminy == []
        assert validace.pocet_ocekavanych == 1
        assert validace.pocet_dodrzenych == 0
        assert validace.pocet_nespravnych_variant == 1
