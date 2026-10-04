# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.jadro.dokument import MAX_ZNAKU_DOKUMENTU
from app.jadro.rag import MAX_ZNAKU_JEDNOHO_PREKLADU

class OdpovedSeStrankovanim(BaseModel):
    polozky: list[dict[str, Any]]
    celkem: int
    limit: int
    odsazeni: int


class Potvrzeni(BaseModel):
    uspech: bool = True
    zprava: str = ""
    podrobnosti: dict[str, Any] = Field(default_factory=dict)

class PozadavekImportu(BaseModel):
    cesta: str | None = Field(
        default=None,
        description="Cesta k souboru; není-li uvedena, použije se výchozí katalog.",
    )
    kdo: str = "neznámý"

class PozadavekDeduplikace(BaseModel):
    metoda: str = Field(
        default="hybridni",
        description="semanticka | lexikalni | hybridni | pravidlova",
    )
    prah_rozhodnuti: float = Field(default=0.72, ge=0.0, le=1.0)
    prah_kandidatu: float = Field(default=0.55, ge=0.0, le=1.0)
    pocet_sousedu: int = Field(default=16, ge=1, le=100)
    uplatnit_atributy: bool = True
    omezit_na_tridu_iso: bool = False
    prisne_shlukovani: bool = True
    kdo: str = "neznámý"
    nahradit: bool = True


class PozadavekKontrolyPolozky(BaseModel):
    popis: str = Field(min_length=1)
    komoditni_skupina: str = ""
    itemnum: str = ""
    pocet_kandidatu: int = Field(default=10, ge=1, le=50)

class PozadavekVyjmuti(BaseModel):
    itemnum: str = Field(min_length=1, description="Položka, která do skupiny nepatří.")
    poznamka: str = ""
    kdo: str = "neznámý"

class PozadavekRozhodnuti(BaseModel):
    vysledek: str = Field(description="schvaleno | zamitnuto | odlozeno")
    zastupce: str | None = Field(
        default=None, description="Záznam, který má být zachován."
    )
    upraveny_popis: str | None = None
    poznamka: str | None = None
    kdo: str = "neznámý"

class PozadavekPrekladuAPI(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_ZNAKU_JEDNOHO_PREKLADU,
        description="Delší text se překládá jako dokument (/preklad/dokument).",
    )
    zdrojovy_jazyk: str = "en"
    cilovy_jazyk: str = "cs"
    pouzit_glosar: bool = True
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    itemnum: str | None = None
    kdo: str = "neznámý"

class PozadavekDokumentuAPI(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ZNAKU_DOKUMENTU)
    zdrojovy_jazyk: str = "en"
    cilovy_jazyk: str = "cs"
    pouzit_glosar: bool = True
    model: str | None = None
    kdo: str = "neznámý"

class PolozkaGlosareAPI(BaseModel):
    terminy: dict[str, str] = Field(
        description="Termín podle kódu jazyka; vyplněny alespoň dva jazyky.",
    )
    kategorie: str = Field(min_length=1)
    definice: str = ""
    nespravne: dict[str, str] = Field(default_factory=dict)
    zdroj: str = "firemní glosář"
    overene: list[str] = Field(default_factory=list)
    model: str | None = None
    kdo: str = "neznámý"

class UdalostMIF(BaseModel):
    typ_udalosti: str = Field(
        default="MXITEM_UPDATED",
        description="MXITEM_CREATED | MXITEM_UPDATED",
    )
    obsah: dict[str, Any] = Field(
        description="Obsah objektové struktury MXITEM, minimálně ITEMNUM a DESCRIPTION.",
    )
    kdo: str = "MIF"

class StavSystemu(BaseModel):
    katalog_nacten: bool
    pocet_polozek: int
    index_pripraven: bool
    glosar_nacten: bool
    pocet_terminu: int
    ollama_dostupna: bool
    dostupne_modely: list[str]
    aktivni_model: str
    vychozi_model: str
    model_prepnut_uzivatelem: bool
    model_embeddingu: str
    offline_rezim: bool


class PozadavekZmenyModelu(BaseModel):
    model: str | None = Field(
        default=None,
        description="Název modelu v Ollamě, například 'qwen2.5:7b'. "
                    "Prázdná hodnota vrací výchozí model z konfigurace.",
    )
    kdo: str = Field(default="neznámý", description="Identita uživatele.")
