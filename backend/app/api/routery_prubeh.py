# -*- coding: utf-8 -*
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.jadro.llm import ChybaLLM
from app.sluzby.prubeh import prubeh_podobnosti, prubeh_prekladu

logger = logging.getLogger(__name__)

router_prubeh = APIRouter(prefix="/prubeh", tags=["Průběh zpracování"])


class PozadavekPrubehu(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    zdrojovy_jazyk: str = "en"
    cilovy_jazyk: str = "cs"
    model: str | None = None


class PozadavekPodobnosti(BaseModel):
    prvni: str = Field(min_length=1, max_length=500)
    druhy: str = Field(min_length=1, max_length=500)


@router_prubeh.post("/preklad")
def zaznam_prekladu(pozadavek: PozadavekPrubehu) -> dict[str, Any]:
    if pozadavek.zdrojovy_jazyk == pozadavek.cilovy_jazyk:
        raise HTTPException(400, "Zdrojový a cílový jazyk se musí lišit.")
    try:
        return prubeh_prekladu(
            text=pozadavek.text,
            zdrojovy_jazyk=pozadavek.zdrojovy_jazyk,
            cilovy_jazyk=pozadavek.cilovy_jazyk,
            model=pozadavek.model,
        )
    except ChybaLLM as chyba:
        raise HTTPException(503, str(chyba)) from chyba


@router_prubeh.post("/podobnost")
def zaznam_podobnosti(pozadavek: PozadavekPodobnosti) -> dict[str, Any]:
    return prubeh_podobnosti(pozadavek.prvni, pozadavek.druhy)


VSECHNY_SMEROVACE_PRUBEHU = (router_prubeh,)
