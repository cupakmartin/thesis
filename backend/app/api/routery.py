# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.schemas import (
    OdpovedSeStrankovanim,
    PolozkaGlosareAPI,
    Potvrzeni,
    PozadavekDeduplikace,
    PozadavekDokumentuAPI,
    PozadavekImportu,
    PozadavekKontrolyPolozky,
    PozadavekPrekladuAPI,
    PozadavekRozhodnuti,
    PozadavekVyjmuti,
    PozadavekZmenyModelu,
    StavSystemu,
    UdalostMIF,
)
from app.config import aktivni_model, nastaveni, vychozi_model
from app.db import pripoj
from app.jadro.duplicity import (
    NastaveniDeduplikace,
    ZaznamPolozky,
    zkontroluj_novou_polozku,
)
from app.jadro.dokument import MAX_VELIKOST_PDF, ChybaDokumentu, vytez_text_z_pdf
from app.jadro.glosar import glosar
from app.jadro.jazyky import JAZYKY
from app.jadro.llm import OllamaPoskytovatel
from app.jadro.rag import PozadavekPrekladu
from app.jadro.taxonomie import zarad_pravidlove
from app.sluzby.deduplikace import sluzba_deduplikace
from app.sluzby.katalog import FiltrKatalogu, sluzba_katalogu
from app.sluzby.glosar_sprava import (
    ChybaGlosare,
    TerminNenalezen,
    serializuj as serializuj_termin,
    sluzba_glosare,
)
from app.sluzby.kontrola import sluzba_kontroly
from app.sluzby.mif import polozka_do_xml, sluzba_mif, xml_do_polozek
from app.sluzby.nacitani import predehrej_embeddingy, predehrej_llm, stav_nacitani
from app.sluzby.prekladani import sluzba_prekladu
from app.sluzby.slucovani import ChybaSlucovani, sluzba_slucovani
from app.sluzby.volba_modelu import ChybaVolbyModelu, zjisti_stav, zmen_model

logger = logging.getLogger(__name__)

router_system = APIRouter(prefix="/system", tags=["Systém"])

@router_system.get("/stav", response_model=StavSystemu)
def stav_systemu() -> StavSystemu:
    konfigurace = nastaveni()
    katalog = sluzba_katalogu()
    pocet_polozek = katalog.pocet()

    poskytovatel = OllamaPoskytovatel(konfigurace)
    dostupna = poskytovatel.je_dostupny()
    modely = poskytovatel.seznam_modelu() if dostupna else []

    try:
        zdroj_glosare = glosar()
        pocet_terminu = zdroj_glosare.velikost
    except Exception:
        pocet_terminu = 0

    return StavSystemu(
        katalog_nacten=pocet_polozek > 0,
        pocet_polozek=pocet_polozek,
        index_pripraven=katalog.je_index_pripraven,
        glosar_nacten=pocet_terminu > 0,
        pocet_terminu=pocet_terminu,
        ollama_dostupna=dostupna,
        dostupne_modely=modely,
        aktivni_model=aktivni_model(),
        vychozi_model=vychozi_model(),
        model_prepnut_uzivatelem=aktivni_model() != vychozi_model(),
        model_embeddingu=konfigurace.model_embeddingu,
        offline_rezim=konfigurace.offline_rezim,
    )


@router_system.get("/model")
def stav_modelu() -> dict[str, Any]:
    return zjisti_stav().jako_slovnik()


@router_system.put("/model")
def zmen_jazykovy_model(pozadavek: PozadavekZmenyModelu) -> dict[str, Any]:
    try:
        return zmen_model(pozadavek.model, kdo=pozadavek.kdo).jako_slovnik()
    except ChybaVolbyModelu as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba


@router_system.get("/jazyky")
def podporovane_jazyky() -> list[dict[str, str]]:
    return [{"kod": j.kod, "nazev": j.nazev} for j in JAZYKY.values()]


@router_system.get("/nacitani")
def stav_nacitani_modelu() -> dict[str, Any]:
    return stav_nacitani()


@router_system.post("/nacitani")
def nacti_modely() -> dict[str, Any]:
    stav = stav_nacitani()
    if stav["llm"]["stav"] == "nenacten":
        predehrej_llm()
    if stav["embedding"]["stav"] == "nenacten":
        predehrej_embeddingy()
    return stav_nacitani()


@router_system.post("/kontrola-modelu")
def kontrola_modelu(vcetne_prekladu: bool = True) -> dict[str, Any]:
    return sluzba_kontroly().proved(vcetne_prekladu=vcetne_prekladu).jako_slovnik()


@router_system.get("/prehled")
def prehled() -> dict[str, Any]:
    katalog = sluzba_katalogu()
    return {
        "katalog": katalog.statistiky(),
        "posledni_beh": sluzba_deduplikace().posledni_beh(),
        "slucovani": sluzba_slucovani().statistiky(),
        "preklady": sluzba_prekladu().statistiky(),
    }

router_polozky = APIRouter(prefix="/polozky", tags=["Katalog"])


@router_polozky.get("", response_model=OdpovedSeStrankovanim)
def seznam_polozek(
    hledany_text: str = "",
    komoditni_skupina: str = "",
    iso_trida: str = "",
    stav: str = "",
    stav_konsolidace: str = "",
    jazyk: str = "",
    razeni: str = "poradi",
    sestupne: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    odsazeni: int = Query(default=0, ge=0),
) -> OdpovedSeStrankovanim:
    filtr = FiltrKatalogu(
        hledany_text=hledany_text,
        komoditni_skupina=komoditni_skupina,
        iso_trida=iso_trida,
        stav=stav,
        stav_konsolidace=stav_konsolidace,
        jazyk=jazyk,
    )
    polozky, celkem = sluzba_katalogu().seznam(
        filtr, limit=limit, odsazeni=odsazeni, razeni=razeni, sestupne=sestupne
    )
    return OdpovedSeStrankovanim(
        polozky=polozky, celkem=celkem, limit=limit, odsazeni=odsazeni
    )


@router_polozky.get("/filtry")
def hodnoty_filtru() -> dict[str, list[str]]:
    return sluzba_katalogu().rozliseni_hodnot()


@router_polozky.get("/{itemnum:path}/xml", response_class=PlainTextResponse)
def polozka_jako_xml(itemnum: str) -> str:
    polozka = sluzba_katalogu().detail(itemnum)
    if polozka is None:
        raise HTTPException(status_code=404, detail=f"Položka {itemnum} nebyla nalezena.")
    return polozka_do_xml(polozka)


@router_polozky.get("/{itemnum:path}")
def detail_polozky(itemnum: str) -> dict[str, Any]:
    polozka = sluzba_katalogu().detail(itemnum)
    if polozka is None:
        raise HTTPException(status_code=404, detail=f"Položka {itemnum} nebyla nalezena.")

    zarazeni = zarad_pravidlove(
        polozka.get("description", ""), polozka.get("commodity_group", "")
    )
    polozka["zarazeni_iso"] = (
        {
            "kod": zarazeni.kod,
            "nazev_cs": zarazeni.nazev_cs,
            "nazev_en": zarazeni.nazev_en,
            "jistota": zarazeni.jistota,
            "zpusob": zarazeni.zpusob,
            "zduvodneni": zarazeni.zduvodneni,
        }
        if zarazeni
        else None
    )
    return polozka


@router_polozky.post("/import", response_model=Potvrzeni)
def importuj_katalog(pozadavek: PozadavekImportu) -> Potvrzeni:
    cesta = Path(pozadavek.cesta) if pozadavek.cesta else None
    try:
        pocet = sluzba_katalogu().nacti_z_csv(cesta, kdo=pozadavek.kdo)
    except (FileNotFoundError, ValueError) as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(
        zprava=f"Načteno {pocet} položek katalogu.",
        podrobnosti={"pocet": pocet},
    )


router_dedup = APIRouter(prefix="/deduplikace", tags=["Deduplikace"])

@router_dedup.post("/spustit", response_model=Potvrzeni)
def spust_deduplikaci(pozadavek: PozadavekDeduplikace) -> Potvrzeni:
    konfigurace = NastaveniDeduplikace(
        metoda=pozadavek.metoda,
        prah_rozhodnuti=pozadavek.prah_rozhodnuti,
        prah_kandidatu=pozadavek.prah_kandidatu,
        pocet_sousedu=pozadavek.pocet_sousedu,
        uplatnit_atributy=pozadavek.uplatnit_atributy,
        omezit_na_tridu_iso=pozadavek.omezit_na_tridu_iso,
        prisne_shlukovani=pozadavek.prisne_shlukovani,
    )
    try:
        beh_id = sluzba_deduplikace().spust(
            konfigurace, kdo=pozadavek.kdo, nahradit=pozadavek.nahradit
        )
    except RuntimeError as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(
        zprava=f"Deduplikace dokončena (běh {beh_id}).",
        podrobnosti={"beh_id": beh_id},
    )


@router_dedup.delete("/behy", response_model=Potvrzeni)
def smaz_behy() -> Potvrzeni:
    pocet = sluzba_deduplikace().smaz_vsechny_behy()
    return Potvrzeni(
        zprava=(
            f"Odstraněno {pocet} běhů deduplikace včetně všech skupin."
            if pocet else "Žádné běhy k odstranění."
        ),
        podrobnosti={"odstraneno_behu": pocet},
    )


@router_dedup.get("/behy")
def seznam_behu(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return sluzba_deduplikace().seznam_behu(limit)


@router_dedup.get("/behy/{beh_id}/klastry", response_model=OdpovedSeStrankovanim)
def klastry_behu(
    beh_id: int,
    stav: str = "",
    limit: int = Query(default=25, ge=1, le=200),
    odsazeni: int = Query(default=0, ge=0),
) -> OdpovedSeStrankovanim:
    klastry, celkem = sluzba_deduplikace().klastry(beh_id, stav, limit, odsazeni)
    return OdpovedSeStrankovanim(
        polozky=klastry, celkem=celkem, limit=limit, odsazeni=odsazeni
    )


@router_dedup.get("/klastry/{klastr_id}")
def detail_klastru(klastr_id: int) -> dict[str, Any]:
    klastr = sluzba_deduplikace().detail_klastru(klastr_id)
    if klastr is None:
        raise HTTPException(status_code=404, detail=f"Klastr {klastr_id} nebyl nalezen.")
    return klastr


@router_dedup.post("/kontrola-polozky")
def kontrola_nove_polozky(pozadavek: PozadavekKontrolyPolozky) -> dict[str, Any]:
    katalog = sluzba_katalogu()
    zaznamy = katalog.zaznamy()
    if not zaznamy:
        raise HTTPException(status_code=400, detail="Katalog je prázdný.")

    vektory, index = katalog.zajisti_index()
    nova = ZaznamPolozky(
        itemnum=pozadavek.itemnum or "NOVA",
        popis=pozadavek.popis,
        komoditni_skupina=pozadavek.komoditni_skupina,
    )
    dvojice = zkontroluj_novou_polozku(
        nova=nova,
        zaznamy=zaznamy,
        vektory_katalogu=vektory,
        index=index,
        pocet_kandidatu=pozadavek.pocet_kandidatu,
    )

    kandidati = []
    for d in dvojice:
        kandidat = zaznamy[d.index_a]
        if pozadavek.itemnum and kandidat.itemnum == pozadavek.itemnum:
            continue
        kandidati.append({
            "itemnum": kandidat.itemnum,
            "popis": kandidat.popis,
            "komoditni_skupina": kandidat.komoditni_skupina,
            "vyrobce": kandidat.vyrobce,
            "podobnost_semanticka": round(d.podobnost_semanticka, 4),
            "podobnost_lexikalni": round(d.podobnost_lexikalni, 4),
            "skore_atributu": round(d.skore_atributu, 4),
            "skore": round(d.skore, 4),
            "je_duplicita": d.prijata,
            "rozpor_atributu": d.rozpor_atributu,
            "vysvetleni": list(d.vysvetleni),
        })

    zarazeni = zarad_pravidlove(pozadavek.popis, pozadavek.komoditni_skupina)
    return {
        "pocet_kandidatu": len(kandidati),
        "nalezena_duplicita": any(k["je_duplicita"] for k in kandidati),
        "kandidati": kandidati,
        "zarazeni_iso": (
            {"kod": zarazeni.kod, "nazev_cs": zarazeni.nazev_cs,
             "jistota": zarazeni.jistota, "zduvodneni": zarazeni.zduvodneni}
            if zarazeni else None
        ),
    }

router_slucovani = APIRouter(prefix="/slucovani", tags=["Slučování"])

@router_slucovani.post("/klastry/{klastr_id}/vyjmout", response_model=Potvrzeni)
def vyjmi_ze_skupiny(klastr_id: int, pozadavek: PozadavekVyjmuti) -> Potvrzeni:
    try:
        vysledek = sluzba_slucovani().vyjmi_clena(
            klastr_id=klastr_id,
            itemnum=pozadavek.itemnum,
            kdo=pozadavek.kdo,
            poznamka=pozadavek.poznamka,
        )
    except ChybaSlucovani as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(
        zprava=(
            f"Položka {pozadavek.itemnum} vyjmuta; skupina zrušena, "
            "protože v ní zbyla jediná položka."
            if vysledek["skupina_zrusena"]
            else f"Položka {pozadavek.itemnum} ze skupiny vyjmuta."
        ),
        podrobnosti=vysledek,
    )


@router_slucovani.post("/klastry/{klastr_id}/rozhodnout", response_model=Potvrzeni)
def rozhodni_o_klastru(klastr_id: int, pozadavek: PozadavekRozhodnuti) -> Potvrzeni:
    try:
        vysledek = sluzba_slucovani().rozhodni(
            klastr_id=klastr_id,
            vysledek=pozadavek.vysledek,
            kdo=pozadavek.kdo,
            zastupce=pozadavek.zastupce,
            upraveny_popis=pozadavek.upraveny_popis,
            poznamka=pozadavek.poznamka,
        )
    except ChybaSlucovani as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(zprava="Rozhodnutí bylo zaznamenáno.", podrobnosti=vysledek)


@router_slucovani.post("/klastry/{klastr_id}/zrusit", response_model=Potvrzeni)
def zrus_rozhodnuti(klastr_id: int, kdo: str = "neznámý") -> Potvrzeni:
    try:
        vysledek = sluzba_slucovani().zrus_rozhodnuti(klastr_id, kdo)
    except ChybaSlucovani as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(zprava="Rozhodnutí bylo zrušeno.", podrobnosti=vysledek)


@router_slucovani.get("/statistiky")
def statistiky_slucovani(beh_id: int | None = None) -> dict[str, Any]:
    return sluzba_slucovani().statistiky(beh_id)


@router_slucovani.post("/export", response_model=Potvrzeni)
def export_slouceni(kdo: str = "neznámý") -> Potvrzeni:
    cesta = nastaveni().adresar_vystupu / "slouceni.csv"
    pocet = sluzba_slucovani().export_slouceni(cesta)
    return Potvrzeni(
        zprava=f"Vyexportováno {pocet} sloučení.",
        podrobnosti={"pocet": pocet, "cesta": str(cesta)},
    )

router_preklad = APIRouter(prefix="/preklad", tags=["Překlad"])

@router_preklad.post("")
def prelozi_text(pozadavek: PozadavekPrekladuAPI) -> dict[str, Any]:
    try:
        vysledek, validace = sluzba_prekladu().prelozi(
            PozadavekPrekladu(
                text=pozadavek.text,
                zdrojovy_jazyk=pozadavek.zdrojovy_jazyk,
                cilovy_jazyk=pozadavek.cilovy_jazyk,
                pouzit_glosar=pozadavek.pouzit_glosar,
                model=pozadavek.model,
                temperature=pozadavek.temperature,
            ),
            kdo=pozadavek.kdo,
            itemnum=pozadavek.itemnum,
        )
    except ValueError as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba
    except Exception as chyba:
        raise HTTPException(status_code=503, detail=str(chyba)) from chyba

    return {
        "zdrojovy_text": vysledek.zdrojovy_text,
        "preklad": vysledek.preklad,
        "zdrojovy_jazyk": vysledek.zdrojovy_jazyk,
        "cilovy_jazyk": vysledek.cilovy_jazyk,
        "pouzity_glosar": vysledek.pouzity_glosar,
        "zpusob": vysledek.zpusob,
        "model": vysledek.model,
        "doba_s": round(vysledek.doba_s, 3),
        "doba_vyhledani_s": round(vysledek.doba_vyhledani_s, 3),
        "doba_generovani_s": round(vysledek.doba_generovani_s, 3),
        "systemova_instrukce": vysledek.systemova_instrukce,
        "nalezene_terminy": [
            {
                "id": n.polozka.id,
                "termin_zdroj": n.polozka.termin(vysledek.zdrojovy_jazyk),
                "termin_cil": n.polozka.termin(vysledek.cilovy_jazyk),
                "cil_neoveren": vysledek.cilovy_jazyk in n.polozka.strojove,
                "definice": n.polozka.definice,
                "nespravne": n.polozka.nespravne_v(vysledek.cilovy_jazyk),
                "kategorie": n.polozka.kategorie,
                "zdroj": n.polozka.zdroj,
                "zpusob": n.zpusob,
                "skore": round(n.skore, 4),
            }
            for n in vysledek.nalezene_terminy
        ],
        "validace": {
            "mira_dodrzeni_glosare": validace.mira_dodrzeni_glosare,
            "pocet_ocekavanych": validace.pocet_ocekavanych,
            "pocet_dodrzenych": validace.pocet_dodrzenych,
            "pocet_nespravnych_variant": validace.pocet_nespravnych_variant,
            "identifikatory_zachovany": validace.identifikatory_zachovany,
            "chybejici_identifikatory": validace.chybejici_identifikatory,
            "varovani": validace.varovani,
            "je_v_poradku": validace.je_v_poradku,
            "souhrn": validace.souhrn(),
            "kontroly": [
                {
                    "termin_zdroj": k.termin_zdroj,
                    "termin_cil": k.termin_cil,
                    "ocekavan": k.ocekavan,
                    "dodrzen": k.dodrzen,
                    "nespravna_varianta": k.nespravna_varianta,
                    "nespravna_varianta_pouzita": k.nespravna_varianta_pouzita,
                }
                for k in validace.kontroly
            ],
        },
    }


def _radek_ndjson(udalost: dict[str, Any]) -> str:
    return json.dumps(udalost, ensure_ascii=False) + "\n"


@router_preklad.post("/dokument")
def prelozi_dokument(pozadavek: PozadavekDokumentuAPI) -> StreamingResponse:
    udalosti = sluzba_prekladu().prelozi_dokument(
        text=pozadavek.text,
        zdrojovy_jazyk=pozadavek.zdrojovy_jazyk,
        cilovy_jazyk=pozadavek.cilovy_jazyk,
        pouzit_glosar=pozadavek.pouzit_glosar,
        model=pozadavek.model,
        kdo=pozadavek.kdo,
    )
    try:
        prvni = next(udalosti)
    except ValueError as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    def proud() -> Iterator[str]:
        yield _radek_ndjson(prvni)
        try:
            for udalost in udalosti:
                yield _radek_ndjson(udalost)
        except Exception as chyba:
            logger.exception("Překlad dokumentu přerušen.")
            yield _radek_ndjson({"typ": "chyba", "zprava": str(chyba)})

    return StreamingResponse(proud(), media_type="application/x-ndjson")


@router_preklad.post(
    "/pdf",
    openapi_extra={"requestBody": {
        "required": True,
        "content": {"application/pdf": {"schema": {"type": "string",
                                                    "format": "binary"}}},
    }},
)
async def nacti_pdf(request: Request) -> dict[str, Any]:
    delka = int(request.headers.get("content-length") or 0)
    if delka > MAX_VELIKOST_PDF:
        raise HTTPException(status_code=413, detail="Soubor PDF je příliš velký.")
    data = await request.body()
    try:
        dokument = await run_in_threadpool(vytez_text_z_pdf, data)
    except ChybaDokumentu as chyba:
        raise HTTPException(status_code=422, detail=str(chyba)) from chyba
    return {
        "text": dokument.text,
        "pocet_stran": dokument.pocet_stran,
        "pocet_znaku": len(dokument.text),
    }


@router_preklad.get("/historie", response_model=OdpovedSeStrankovanim)
def historie_prekladu(
    itemnum: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    odsazeni: int = Query(default=0, ge=0),
) -> OdpovedSeStrankovanim:
    polozky, celkem = sluzba_prekladu().historie(limit, odsazeni, itemnum)
    return OdpovedSeStrankovanim(
        polozky=polozky, celkem=celkem, limit=limit, odsazeni=odsazeni
    )

router_glosar = APIRouter(prefix="/glosar", tags=["Glosář"])

@router_glosar.get("", response_model=OdpovedSeStrankovanim)
def seznam_glosare(
    hledany_text: str = "",
    kategorie: str = "",
    jen_strojove: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    odsazeni: int = Query(default=0, ge=0),
) -> OdpovedSeStrankovanim:
    polozky = glosar().polozky

    if hledany_text:
        hledane = hledany_text.casefold()
        polozky = [
            p for p in polozky
            if any(hledane in t.casefold() for t in p.terminy.values())
            or hledane in p.definice.casefold()
        ]
    if kategorie:
        polozky = [p for p in polozky if p.kategorie == kategorie]
    if jen_strojove:
        polozky = [p for p in polozky if p.strojove]

    vyrez = polozky[odsazeni: odsazeni + limit]
    return OdpovedSeStrankovanim(
        polozky=[serializuj_termin(p) for p in vyrez],
        celkem=len(polozky),
        limit=limit,
        odsazeni=odsazeni,
    )


@router_glosar.get("/kategorie")
def kategorie_glosare() -> list[str]:
    return sluzba_glosare().kategorie()


@router_glosar.get("/stav")
def stav_glosare() -> dict[str, int]:
    polozky = glosar().polozky
    return {
        "celkem": len(polozky),
        "k_doplneni": len(sluzba_glosare().k_doplneni()),
        "neovereno": sum(1 for p in polozky if p.strojove),
    }


@router_glosar.post("")
def pridej_termin(pozadavek: PolozkaGlosareAPI) -> dict[str, Any]:
    try:
        polozka = sluzba_glosare().pridej(
            terminy=pozadavek.terminy,
            kategorie=pozadavek.kategorie,
            definice=pozadavek.definice,
            nespravne=pozadavek.nespravne,
            zdroj=pozadavek.zdroj,
            kdo=pozadavek.kdo,
            model=pozadavek.model,
        )
    except ChybaGlosare as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba
    except Exception as chyba:
        raise HTTPException(
            status_code=503,
            detail=f"Ostatní jazyky se nepodařilo doplnit: {chyba}",
        ) from chyba
    return serializuj_termin(polozka)


@router_glosar.put("/{id_terminu}")
def uprav_termin(id_terminu: str, pozadavek: PolozkaGlosareAPI) -> dict[str, Any]:
    try:
        polozka = sluzba_glosare().uprav(
            id_terminu,
            terminy=pozadavek.terminy,
            kategorie=pozadavek.kategorie,
            definice=pozadavek.definice,
            nespravne=pozadavek.nespravne,
            overene=pozadavek.overene,
            kdo=pozadavek.kdo,
            model=pozadavek.model,
        )
    except TerminNenalezen as chyba:
        raise HTTPException(status_code=404, detail=str(chyba)) from chyba
    except ChybaGlosare as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba
    except Exception as chyba:
        raise HTTPException(
            status_code=503,
            detail=f"Ostatní jazyky se nepodařilo doplnit: {chyba}",
        ) from chyba
    return serializuj_termin(polozka)


@router_glosar.post("/doplnit-jazyky")
def dopln_jazyky_glosare(model: str | None = None) -> StreamingResponse:
    udalosti = sluzba_glosare().dopln_vse(model=model)

    def proud() -> Iterator[str]:
        try:
            for udalost in udalosti:
                yield _radek_ndjson(udalost)
        except Exception as chyba:
            logger.exception("Doplnění jazyků glosáře přerušeno.")
            yield _radek_ndjson({"typ": "chyba", "zprava": str(chyba)})

    return StreamingResponse(proud(), media_type="application/x-ndjson")


@router_glosar.delete("/{id_terminu}", response_model=Potvrzeni)
def smaz_termin(id_terminu: str, kdo: str = "neznámý") -> Potvrzeni:
    zdroj = glosar()
    if not zdroj.smaz(id_terminu):
        raise HTTPException(status_code=404, detail=f"Termín {id_terminu} nebyl nalezen.")
    zdroj.uloz_do_csv()
    return Potvrzeni(zprava=f"Termín {id_terminu} byl odstraněn.")

router_mif = APIRouter(prefix="/mif", tags=["Maximo MIF"])

@router_mif.get("/objektova-struktura")
def objektova_struktura() -> dict[str, Any]:
    """Vrátí popis podporované objektové struktury MXITEM."""
    return sluzba_mif().objektova_struktura()


@router_mif.post("/udalost")
def prijmi_udalost(udalost: UdalostMIF) -> dict[str, Any]:
    try:
        return sluzba_mif().prijmi_udalost(
            typ_udalosti=udalost.typ_udalosti,
            obsah=udalost.obsah,
            kdo=udalost.kdo,
        )
    except ValueError as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba


@router_mif.get("/udalosti", response_model=OdpovedSeStrankovanim)
def historie_udalosti(
    limit: int = Query(default=50, ge=1, le=200),
    odsazeni: int = Query(default=0, ge=0),
) -> OdpovedSeStrankovanim:
    polozky, celkem = sluzba_mif().historie_udalosti(limit, odsazeni)
    return OdpovedSeStrankovanim(
        polozky=polozky, celkem=celkem, limit=limit, odsazeni=odsazeni
    )


@router_mif.post("/import-xml", response_model=Potvrzeni)
def importuj_xml(obsah: str, kdo: str = "neznámý") -> Potvrzeni:
    try:
        polozky = xml_do_polozek(obsah)
    except ValueError as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba

    return Potvrzeni(
        zprava=f"Z XML načteno {len(polozky)} položek.",
        podrobnosti={"pocet": len(polozky), "polozky": polozky[:20]},
    )


VSECHNY_SMEROVACE = (
    router_system,
    router_polozky,
    router_dedup,
    router_slucovani,
    router_preklad,
    router_glosar,
    router_mif,
)
