# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.db import pripoj
from app.jadro.csv_import import ChybaCsv
from app.sluzby.import_katalogu import (
    MAX_VELIKOST_CSV,
    POSTUP_IMPORTU,
    ChybaImportu,
    NastaveniImportu,
    SloupecKatalogu,
    generuj,
    importuj_nahled,
    metadata,
    smaz_katalog,
    uloz_nahled,
)

router_katalog = APIRouter(prefix="/katalog", tags=["Katalog"])

ODDELOVACE = {"strednik": ";", "carka": ",", "tabulator": "\t", "svislice": "|"}


class SloupecImportuAPI(BaseModel):
    index: int = Field(ge=0)
    nazev: str = Field(min_length=1)
    role: str = ""
    jazyk: str = ""


class PozadavekImportuKatalogu(BaseModel):
    token: str = Field(min_length=1)
    sloupce: list[SloupecImportuAPI]
    ma_id: bool
    vicejazycny: Literal["ne", "sloupec", "sloupce"] = "ne"
    mapa_jazyku: dict[str, str] = Field(default_factory=dict)
    jazyk_katalogu: str = ""
    kdo: str = "neznámý"


class PozadavekGenerovaniKatalogu(BaseModel):
    pocet: int = Field(default=5000, ge=100, le=50000)
    kdo: str = "neznámý"


@router_katalog.get("")
def stav_katalogu() -> dict[str, Any]:
    meta = metadata()
    with pripoj(pouze_cteni=True) as spojeni:
        pocet_behu = int(spojeni.execute("SELECT COUNT(*) FROM behy").fetchone()[0])
    return {"existuje": meta is not None, "pocet_behu": pocet_behu, **(meta or {})}


@router_katalog.post(
    "/nahled",
    openapi_extra={"requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
    }},
)
async def nahled_csv(
    request: Request,
    nazev: str = "katalog.csv",
    kodovani: str = "",
    oddelovac: str = "",
) -> dict[str, Any]:
    delka = int(request.headers.get("content-length") or 0)
    if delka > MAX_VELIKOST_CSV:
        raise HTTPException(status_code=413, detail="Soubor je větší než 50 MB.")
    if oddelovac and oddelovac not in ODDELOVACE:
        raise HTTPException(status_code=400, detail=f"Neznámý oddělovač: {oddelovac}.")
    data = await request.body()
    try:
        return await run_in_threadpool(
            uloz_nahled, data, nazev, kodovani or None, ODDELOVACE.get(oddelovac)
        )
    except (ChybaCsv, ChybaImportu) as chyba:
        raise HTTPException(status_code=422, detail=str(chyba)) from chyba


@router_katalog.post("/import")
def importuj_katalog(pozadavek: PozadavekImportuKatalogu) -> dict[str, Any]:
    nastaveni = NastaveniImportu(
        sloupce=[SloupecKatalogu(**s.model_dump()) for s in pozadavek.sloupce],
        ma_id=pozadavek.ma_id,
        vicejazycny=pozadavek.vicejazycny,
        mapa_jazyku=pozadavek.mapa_jazyku,
        jazyk_katalogu=pozadavek.jazyk_katalogu,
    )
    try:
        return importuj_nahled(pozadavek.token, nastaveni, kdo=pozadavek.kdo)
    except (ChybaCsv, ChybaImportu) as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba


@router_katalog.get("/import/prubeh")
def prubeh_importu() -> dict[str, Any]:
    return POSTUP_IMPORTU.snimek()


@router_katalog.post("/generovat")
def vygeneruj_katalog(pozadavek: PozadavekGenerovaniKatalogu) -> dict[str, Any]:
    return generuj(pocet=pozadavek.pocet, kdo=pozadavek.kdo)


@router_katalog.delete("")
def smaz(kdo: str = "neznámý") -> dict[str, int]:
    return smaz_katalog(kdo=kdo)


VSECHNY_SMEROVACE_KATALOGU = (router_katalog,)
