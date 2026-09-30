# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from app.config import Nastaveni, nastaveni

logger = logging.getLogger(__name__)


def _otisk_textu(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


class SpravceEmbeddingu:
    def __init__(self, konfigurace: Nastaveni | None = None) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._model = None
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

            from sentence_transformers import SentenceTransformer

            logger.info("Načítám embedding model %s", self._nastaveni.model_embeddingu)
            self._model = SentenceTransformer(
                self._nastaveni.model_embeddingu,
                device=self._nastaveni.zarizeni_embeddingu,
            )
            return self._model

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

    def zakoduj(
        self,
        texty: Sequence[str],
        pouzit_cache: bool = True,
        zobrazit_prubeh: bool = False,
    ) -> np.ndarray:

        if len(texty) == 0:
            return np.zeros((0, self.dimenze), dtype=np.float32)

        if not pouzit_cache:
            return self._spocti(list(texty), zobrazit_prubeh)

        self._zajisti_cache()

        otisky = [_otisk_textu(t) for t in texty]
        chybejici_indexy = [i for i, o in enumerate(otisky) if o not in self._cache]

        if chybejici_indexy:
            nove_texty = [texty[i] for i in chybejici_indexy]
            nove_vektory = self._spocti(nove_texty, zobrazit_prubeh)
            for poradi, index in enumerate(chybejici_indexy):
                self._cache[otisky[index]] = nove_vektory[poradi]
            self._cache_zmenena = True

        return np.vstack([self._cache[o] for o in otisky]).astype(np.float32)

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
