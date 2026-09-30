# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.config import Nastaveni, nastaveni

logger = logging.getLogger(__name__)


class VektorovyIndex:
    def __init__(self, dimenze: int | None = None, konfigurace: Nastaveni | None = None) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._dimenze = dimenze or self._nastaveni.dimenze_vektoru
        self._index = None
        self._pocet = 0

    def postav(self, vektory: np.ndarray) -> None:
        import faiss

        if vektory.ndim != 2:
            raise ValueError(
                f"Očekávána matice o dvou rozměrech, obdrženo pole tvaru {vektory.shape}."
            )
        if vektory.shape[1] != self._dimenze:
            raise ValueError(
                f"Vektory mají {vektory.shape[1]} dimenzí, index očekává {self._dimenze}."
            )

        data = np.ascontiguousarray(vektory, dtype=np.float32)

        index = faiss.IndexHNSWFlat(
            self._dimenze,
            self._nastaveni.hnsw_pocet_sousedu_grafu,
            faiss.METRIC_INNER_PRODUCT,
        )

        index.hnsw.efConstruction = self._nastaveni.hnsw_ef_construction
        index.hnsw.efSearch = self._nastaveni.hnsw_ef_search

        index.add(data)
        self._index = index
        self._pocet = int(index.ntotal)
        logger.info(
            "Index HNSW postaven nad %d vektory (M=%d, efConstruction=%d).",
            self._pocet,
            self._nastaveni.hnsw_pocet_sousedu_grafu,
            self._nastaveni.hnsw_ef_construction,
        )

    def hledej(
        self,
        dotazy: np.ndarray,
        pocet_sousedu: int | None = None,
        vynechat_sebe: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._index is None:
            raise RuntimeError("Index dosud nebyl postaven; zavolejte nejprve postav().")

        k = pocet_sousedu or self._nastaveni.pocet_sousedu
        k_dotaz = min(k + 1 if vynechat_sebe else k, self._pocet)
        if k_dotaz <= 0:
            prazdne = np.zeros((len(dotazy), 0), dtype=np.float32)
            return prazdne, prazdne.astype(np.int64)

        data = np.ascontiguousarray(np.atleast_2d(dotazy), dtype=np.float32)
        podobnosti, indexy = self._index.search(data, k_dotaz)

        if not vynechat_sebe:
            return podobnosti.astype(np.float32), indexy.astype(np.int64)

        vysledne_podobnosti = np.zeros((len(data), k), dtype=np.float32)
        vysledne_indexy = np.full((len(data), k), -1, dtype=np.int64)
        for radek in range(len(data)):
            zapsano = 0
            for sloupec in range(k_dotaz):
                soused = int(indexy[radek, sloupec])
                if soused == radek or soused < 0:
                    continue
                if zapsano >= k:
                    break
                vysledne_podobnosti[radek, zapsano] = podobnosti[radek, sloupec]
                vysledne_indexy[radek, zapsano] = soused
                zapsano += 1
        return vysledne_podobnosti, vysledne_indexy

    def uloz(self, cesta: Path) -> None:
        import faiss

        if self._index is None:
            raise RuntimeError("Index dosud nebyl postaven.")
        cesta.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(cesta))
        logger.info("Index uložen do %s", cesta)

    def nacti(self, cesta: Path) -> bool:
        import faiss

        if not cesta.exists():
            return False
        try:
            self._index = faiss.read_index(str(cesta))
            self._pocet = int(self._index.ntotal)
            self._index.hnsw.efSearch = self._nastaveni.hnsw_ef_search
            logger.info("Index načten z %s (%d vektorů)", cesta, self._pocet)
            return True
        except Exception as chyba:  # pragma: no cover - poškozený soubor
            logger.warning("Index se nepodařilo načíst (%s), bude přestavěn.", chyba)
            self._index = None
            return False

    @property
    def velikost(self) -> int:
        return self._pocet

    @property
    def je_postaven(self) -> bool:
        return self._index is not None

    @property
    def dimenze(self) -> int:
        return self._dimenze
