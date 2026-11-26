# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

from app.config import Nastaveni, nastaveni

logger = logging.getLogger(__name__)

INTERVAL_PRUBEZNEHO_ULOZENI_S = 120.0


def _zvol_zarizeni(pozadovane: str) -> str:
    if pozadovane != "auto":
        return pozadovane
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _otisk_textu(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


class SpravceEmbeddingu:
    def __init__(self, konfigurace: Nastaveni | None = None) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._model = None
        self._nacita = False
        self._zamek = threading.Lock()
        self._cache: dict[str, np.ndarray] = {}
        self._cache_nactena = False
        self._cache_zmenena = False

    @property
    def cesta_cache(self) -> Path:
        bezpecny_nazev = self._nastaveni.model_embeddingu.replace("/", "_")
        return self._nastaveni.adresar_cache / f"embeddingy_{bezpecny_nazev}.npz"

    def _nacti_model(self):
        if self._model is not None:
            return self._model
        with self._zamek:
            if self._model is not None:
                return self._model

            os.environ.setdefault("HF_HOME", str(self._nastaveni.adresar_modelu))
            if self._nastaveni.offline_rezim:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

            self._nacita = True
            try:
                from sentence_transformers import SentenceTransformer

                zarizeni = _zvol_zarizeni(self._nastaveni.zarizeni_embeddingu)
                logger.info("Načítám embedding model %s (zařízení %s)",
                            self._nastaveni.model_embeddingu, zarizeni)
                self._model = SentenceTransformer(
                    self._nastaveni.model_embeddingu,
                    device=zarizeni,
                )
            finally:
                self._nacita = False
            return self._model

    def nacti_model(self) -> None:
        self._nacti_model()

    @property
    def stav(self) -> str:
        if self._model is not None:
            return "pripraven"
        return "nacita" if self._nacita else "nenacten"

    @property
    def dimenze(self) -> int:

        return self._nastaveni.dimenze_vektoru

    def _zajisti_cache(self) -> None:

        if self._cache_nactena:
            return
        self._cache_nactena = True
        cesta = self.cesta_cache
        if not cesta.exists():
            return
        try:
            with np.load(cesta, allow_pickle=False) as data:
                klice = data["klice"]
                vektory = data["vektory"]
            self._cache = {str(k): vektory[i] for i, k in enumerate(klice)}
            logger.info("Načteno %d vektorů z cache", len(self._cache))
        except Exception as chyba:
            logger.warning("Cache vektorů se nepodařilo načíst (%s), bude přepočtena.", chyba)
            self._cache = {}

    def uloz_cache(self) -> None:

        if not self._cache_zmenena or not self._cache:
            return
        cesta = self.cesta_cache
        cesta.parent.mkdir(parents=True, exist_ok=True)
        klice = np.array(list(self._cache.keys()))
        vektory = np.vstack([self._cache[k] for k in self._cache])
        np.savez_compressed(cesta, klice=klice, vektory=vektory)
        self._cache_zmenena = False
        logger.info("Cache vektorů uložena (%d záznamů)", len(klice))

    def vycisti_cache(self) -> None:

        self._cache = {}
        self._cache_zmenena = False
        if self.cesta_cache.exists():
            self.cesta_cache.unlink()

    def pocet_chybejicich(self, texty: Sequence[str]) -> int:
        self._zajisti_cache()
        return len({o for o in map(_otisk_textu, texty) if o not in self._cache})

    def zakoduj(
        self,
        texty: Sequence[str],
        pouzit_cache: bool = True,
        zobrazit_prubeh: bool = False,
        postup: Callable[[int, int], None] | None = None,
    ) -> np.ndarray:

        if len(texty) == 0:
            return np.zeros((0, self.dimenze), dtype=np.float32)

        if not pouzit_cache:
            return self._spocti(list(texty), zobrazit_prubeh)

        self._zajisti_cache()

        otisky = [_otisk_textu(t) for t in texty]
        chybejici: dict[str, str] = {}
        for otisk, text in zip(otisky, texty):
            if otisk not in self._cache and otisk not in chybejici:
                chybejici[otisk] = text

        if chybejici:
            self._spocti_po_castech(chybejici, zobrazit_prubeh, postup)

        return np.vstack([self._cache[o] for o in otisky]).astype(np.float32)

    def _spocti_po_castech(
        self,
        chybejici: dict[str, str],
        zobrazit_prubeh: bool,
        postup: Callable[[int, int], None] | None,
    ) -> None:
        polozky = list(chybejici.items())
        celkem = len(polozky)
        velikost_casti = max(self._nastaveni.velikost_davky * 8, 256)
        posledni_ulozeni = time.monotonic()
        if postup:
            postup(0, celkem)
        for zacatek in range(0, celkem, velikost_casti):
            cast = polozky[zacatek:zacatek + velikost_casti]
            vektory = self._spocti([text for _, text in cast], zobrazit_prubeh)
            for (otisk, _), vektor in zip(cast, vektory):
                self._cache[otisk] = vektor
            self._cache_zmenena = True
            if postup:
                postup(min(zacatek + velikost_casti, celkem), celkem)
            if time.monotonic() - posledni_ulozeni >= INTERVAL_PRUBEZNEHO_ULOZENI_S:
                self.uloz_cache()
                posledni_ulozeni = time.monotonic()

    def _spocti(self, texty: list[str], zobrazit_prubeh: bool) -> np.ndarray:
        neprazdne_indexy = [i for i, t in enumerate(texty) if t and t.strip()]
        vysledek = np.zeros((len(texty), self.dimenze), dtype=np.float32)

        if not neprazdne_indexy:
            return vysledek

        model = self._nacti_model()
        vstup = [texty[i] for i in neprazdne_indexy]
        vektory = model.encode(
            vstup,
            batch_size=self._nastaveni.velikost_davky,
            normalize_embeddings=self._nastaveni.normalizovat_vektory,
            show_progress_bar=zobrazit_prubeh,
            convert_to_numpy=True,
        )
        vysledek[neprazdne_indexy] = np.asarray(vektory, dtype=np.float32)
        return vysledek

    def zakoduj_jeden(self, text: str, pouzit_cache: bool = True) -> np.ndarray:
        return self.zakoduj([text], pouzit_cache=pouzit_cache)[0]


def kosinova_podobnost(vektor_a: np.ndarray, vektor_b: np.ndarray) -> float:
    norma_a = float(np.linalg.norm(vektor_a))
    norma_b = float(np.linalg.norm(vektor_b))
    if norma_a == 0.0 or norma_b == 0.0:
        return 0.0
    return float(np.dot(vektor_a, vektor_b) / (norma_a * norma_b))


def matice_podobnosti(vektory: np.ndarray) -> np.ndarray:
    if vektory.shape[0] == 0:
        return np.zeros((0, 0), dtype=np.float32)
    normy = np.linalg.norm(vektory, axis=1, keepdims=True)
    normy[normy == 0.0] = 1.0
    normalizovane = vektory / normy
    return (normalizovane @ normalizovane.T).astype(np.float32)

_sdileny_spravce: SpravceEmbeddingu | None = None


def spravce_embeddingu() -> SpravceEmbeddingu:
    global _sdileny_spravce
    if _sdileny_spravce is None:
        _sdileny_spravce = SpravceEmbeddingu()
    return _sdileny_spravce
