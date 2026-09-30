# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routery import VSECHNY_SMEROVACE
from app.api.routery_analyza import VSECHNY_SMEROVACE_ANALYZY
from app.api.routery_prubeh import VSECHNY_SMEROVACE_PRUBEHU
from app.config import nastaveni
from app.db import inicializuj_schema
from app.sluzby.katalog import sluzba_katalogu
from app.sluzby.volba_modelu import obnov_ulozenou_volbu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def zivotni_cyklus(aplikace: FastAPI):
    konfigurace = nastaveni()
    logger.info("Spouštím aplikaci (offline režim: %s)", konfigurace.offline_rezim)

    if konfigurace.offline_rezim:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_HOME", str(konfigurace.adresar_modelu))

    inicializuj_schema()

    logger.info("Aktivní jazykový model: %s", obnov_ulozenou_volbu())

    katalog = sluzba_katalogu()
    if katalog.pocet() == 0 and konfigurace.soubor_katalogu.exists():
        try:
            pocet = katalog.nacti_z_csv(kdo="systém")
            logger.info("Při startu načteno %d položek katalogu.", pocet)
        except Exception as chyba:
            logger.warning("Katalog se při startu nepodařilo načíst: %s", chyba)

    yield

    logger.info("Aplikace ukončena.")


def vytvor_aplikaci() -> FastAPI:
    konfigurace = nastaveni()

    aplikace = FastAPI(
        title="Bachelor Thesis",
        description=(
            "Automatizovaná správa kmenových dat údržby s využitím generativní "
            "umělé inteligence a vektorové sémantiky. Bakalářská práce, "
            "Mendelova univerzita v Brně."
        ),
        version="1.0.0",
        lifespan=zivotni_cyklus,
        docs_url="/api/dokumentace",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    aplikace.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for smerovac in (
        *VSECHNY_SMEROVACE,
        *VSECHNY_SMEROVACE_ANALYZY,
        *VSECHNY_SMEROVACE_PRUBEHU,
    ):
        aplikace.include_router(smerovac, prefix="/api")

    @aplikace.get("/api/zdravi", tags=["Systém"])
    def zdravi() -> dict[str, str]:
        return {"stav": "v pořádku"}

    _pripoj_rozhrani(aplikace, konfigurace.adresar_frontendu)
    return aplikace


def _pripoj_rozhrani(aplikace: FastAPI, adresar: Path) -> None:
    if not adresar.exists():
        logger.warning(
            "Adresář rozhraní %s neexistuje. API je dostupné, "
            "rozhraní je nutné nejprve sestavit.", adresar,
        )

        @aplikace.get("/")
        def rozhrani_chybi() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "chyba": "Uživatelské rozhraní není sestaveno.",
                    "napoveda": "Spusťte ve složce frontend: npm install && npm run build",
                    "api_dokumentace": "/api/dokumentace",
                },
            )

        return

    soubory = adresar / "assets"
    if soubory.exists():
        aplikace.mount("/assets", StaticFiles(directory=soubory), name="assets")

    koren_rozhrani = adresar.resolve()

    @aplikace.get("/{cesta:path}", include_in_schema=False)
    def rozhrani(cesta: str) -> FileResponse:
        if cesta:
            try:
                pozadovany = (koren_rozhrani / cesta).resolve()
            except (OSError, ValueError):
                return FileResponse(koren_rozhrani / "index.html")

            uvnitr_adresare = (
                pozadovany == koren_rozhrani
                or koren_rozhrani in pozadovany.parents
            )
            if uvnitr_adresare and pozadovany.is_file():
                return FileResponse(pozadovany)

        return FileResponse(koren_rozhrani / "index.html")


aplikace = vytvor_aplikaci()
