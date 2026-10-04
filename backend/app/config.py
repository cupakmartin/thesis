from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

KOREN_PROJEKTU: Path = Path(__file__).resolve().parents[2]


class Nastaveni(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MRO_",
        env_file=KOREN_PROJEKTU / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    koren: Path = KOREN_PROJEKTU
    adresar_dat: Path = KOREN_PROJEKTU / "data"
    adresar_vstupu: Path = KOREN_PROJEKTU / "data" / "vstup"
    adresar_cache: Path = KOREN_PROJEKTU / "data" / "cache"
    adresar_vystupu: Path = KOREN_PROJEKTU / "data" / "vystup"
    adresar_modelu: Path = KOREN_PROJEKTU / "modely"
    adresar_frontendu: Path = KOREN_PROJEKTU / "frontend" / "dist"

    soubor_katalogu: Path = KOREN_PROJEKTU / "data" / "vstup" / "katalog.csv"
    soubor_glosare: Path = KOREN_PROJEKTU / "data" / "vstup" / "glosar.csv"
    soubor_databaze: Path = KOREN_PROJEKTU / "data" / "aplikace.db"

    model_embeddingu: str = "sentence-transformers/LaBSE"
    dimenze_vektoru: int = 768

    zarizeni_embeddingu: str = "cpu"
    velikost_davky: int = 128

    normalizovat_vektory: bool = True

    hnsw_pocet_sousedu_grafu: int = Field(default=32, description="Parametr M grafu HNSW")
    hnsw_ef_construction: int = Field(default=200, description="Šířka prohledávání při stavbě")
    hnsw_ef_search: int = Field(default=64, description="Šířka prohledávání při dotazu")

    prah_podobnosti: float = Field(default=0.72, ge=0.0, le=1.0)

    prah_kandidatu: float = Field(default=0.55, ge=0.0, le=1.0)

    pocet_sousedu: int = Field(default=16, ge=1, le=100)

    omezit_na_tridu_iso: bool = False

    prisne_shlukovani: bool = True

    ollama_url: str = "http://localhost:11434"
    model_llm: str = "translategemma:12b"

    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokenu_odpovedi: int = 2048
    kontext_modelu: int = Field(default=4096, ge=2048)
    predehrat_modely: bool = True
    udrzet_model_v_pameti: str = "30m"

    modely_pro_benchmark: list[str] = [
        "translategemma:12b",
        "mistral:7b",
        "qwen2.5:7b",
        "llama3.1:8b",
        "gemma2:9b",
    ]

    pocet_termu_z_glosare: int = Field(default=12, ge=1, le=100)

    prah_relevance_glosare: float = Field(default=0.45, ge=0.0, le=1.0)

    host: str = "127.0.0.1"
    port: int = 8000

    offline_rezim: bool = True

    def zajisti_adresare(self) -> None:
        for adresar in (
            self.adresar_dat,
            self.adresar_vstupu,
            self.adresar_cache,
            self.adresar_vystupu,
            self.adresar_modelu,
        ):
            adresar.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def nastaveni() -> Nastaveni:
    konfigurace = Nastaveni()
    konfigurace.zajisti_adresare()
    return konfigurace

_bezici_model: str | None = None


def aktivni_model() -> str:
    return _bezici_model or nastaveni().model_llm


def nastav_aktivni_model(nazev: str | None) -> str:
    global _bezici_model
    _bezici_model = (nazev or "").strip() or None
    return aktivni_model()


def vychozi_model() -> str:
    return nastaveni().model_llm
