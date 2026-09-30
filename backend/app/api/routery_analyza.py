# -*- coding: utf-8 -*

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import nastaveni
from app.sluzby.katalog import sluzba_katalogu

logger = logging.getLogger(__name__)

router_vizualizace = APIRouter(prefix="/vizualizace", tags=["Vizualizace"])

@router_vizualizace.get("/projekce")
def projekce(
    metoda: str = Query(default="pca", pattern="^(pca|tsne)$"),
    vzorek: int = Query(default=800, ge=50, le=3000),
) -> dict[str, Any]:
    katalog = sluzba_katalogu()
    zaznamy = katalog.zaznamy()
    if not zaznamy:
        raise HTTPException(status_code=400, detail="Katalog je prázdný.")

    vektory, _ = katalog.zajisti_index()

    generator = np.random.default_rng(20260817)
    pocet = min(vzorek, len(zaznamy))
    indexy = generator.choice(len(zaznamy), size=pocet, replace=False)
    indexy.sort()
    vybrane_vektory = vektory[indexy]

    if metoda == "tsne":
        from sklearn.manifold import TSNE
        from sklearn.decomposition import PCA

        predzpracovane = PCA(n_components=min(50, vybrane_vektory.shape[1]),
                             random_state=0).fit_transform(vybrane_vektory)
        souradnice = TSNE(
            n_components=2,
            perplexity=min(30, max(5, pocet // 20)),
            init="pca",
            random_state=0,
            max_iter=500,
        ).fit_transform(predzpracovane)
        vysvetlena_variance = None
    else:
        from sklearn.decomposition import PCA

        model = PCA(n_components=2, random_state=0)
        souradnice = model.fit_transform(vybrane_vektory)
        vysvetlena_variance = [float(h) for h in model.explained_variance_ratio_]

    rozsah = float(np.abs(souradnice).max()) or 1.0
    souradnice = souradnice / rozsah

    body = [
        {
            "itemnum": zaznamy[int(i)].itemnum,
            "popis": zaznamy[int(i)].popis,
            "skupina": zaznamy[int(i)].komoditni_skupina,
            "trida": zaznamy[int(i)].iso_trida,
            "x": round(float(souradnice[poradi, 0]), 4),
            "y": round(float(souradnice[poradi, 1]), 4),
        }
        for poradi, i in enumerate(indexy)
    ]

    return {
        "metoda": metoda,
        "pocet": len(body),
        "vysvetlena_variance": vysvetlena_variance,
        "body": body,
    }


@router_vizualizace.get("/rozlozeni-podobnosti")
def rozlozeni_podobnosti(
    pocet_sousedu: int = Query(default=5, ge=1, le=20),
    vzorek: int = Query(default=1500, ge=100, le=5000),
) -> dict[str, Any]:
    katalog = sluzba_katalogu()
    zaznamy = katalog.zaznamy()
    if not zaznamy:
        raise HTTPException(status_code=400, detail="Katalog je prázdný.")

    vektory, index = katalog.zajisti_index()
    generator = np.random.default_rng(20260817)
    pocet = min(vzorek, len(zaznamy))
    indexy = generator.choice(len(zaznamy), size=pocet, replace=False)

    podobnosti, _ = index.hledej(
        vektory[indexy], pocet_sousedu=pocet_sousedu, vynechat_sebe=True
    )
    hodnoty = podobnosti.flatten()
    hodnoty = hodnoty[hodnoty > 0]

    cetnosti, hranice = np.histogram(hodnoty, bins=28, range=(0.0, 1.0))
    return {
        "pocet_hodnot": int(hodnoty.size),
        "prumer": round(float(np.mean(hodnoty)), 4),
        "median": round(float(np.median(hodnoty)), 4),
        "sloupce": [
            {
                "od": round(float(hranice[i]), 3),
                "do": round(float(hranice[i + 1]), 3),
                "stred": round(float((hranice[i] + hranice[i + 1]) / 2), 3),
                "pocet": int(cetnosti[i]),
            }
            for i in range(len(cetnosti))
        ],
    }


VSECHNY_SMEROVACE_ANALYZY = (router_vizualizace,)
