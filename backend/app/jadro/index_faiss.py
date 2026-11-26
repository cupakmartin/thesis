# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

import numpy as np

from app.config import Nastaveni, nastaveni

logger = logging.getLogger(__name__)

VELIKOST_CASTI_STAVBY = 4096
VELIKOST_CASTI_HLEDANI = 4096


def otisk_vektoru(vektory: np.ndarray, konfigurace: Nastaveni | None = None) -> str:
    nast = konfigurace or nastaveni()
    otisk = hashlib.sha1(np.ascontiguousarray(vektory, dtype=np.float32).tobytes())
    otisk.update(
        f"{vektory.shape}|{nast.hnsw_pocet_sousedu_grafu}|{nast.hnsw_ef_construction}".encode()
    )
    return otisk.hexdigest()[:20]


class VektorovyIndex:
    def __init__(self, dimenze: int | None = None, konfigurace: Nastaveni | None = None) -> None:
        self._nastaveni = konfigurace or nastaveni()
        self._dimenze = dimenze or self._nastaveni.dimenze_vektoru
        self._index = None
        self._pocet = 0

    def postav(
        self,
        vektory: np.ndarray,
        postup: Callable[[int, int], None] | None = None,
    ) -> None:
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

        celkem = len(data)
        for zacatek in range(0, celkem, VELIKOST_CASTI_STAVBY):
            index.add(data[zacatek:zacatek + VELIKOST_CASTI_STAVBY])
            if postup:
                postup(min(zacatek + VELIKOST_CASTI_STAVBY, celkem), celkem)
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
        postup: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._index is None:
            raise RuntimeError("Index dosud nebyl postaven; zavolejte nejprve postav().")

        k = pocet_sousedu or self._nastaveni.pocet_sousedu
        k_dotaz = min(k + 1 if vynechat_sebe else k, self._pocet)
        if k_dotaz <= 0:
            prazdne = np.zeros((len(dotazy), 0), dtype=np.float32)
            return prazdne, prazdne.astype(np.int64)

        data = np.ascontiguousarray(np.atleast_2d(dotazy), dtype=np.float32)
        celkem = len(data)
        podobnosti = np.zeros((celkem, k_dotaz), dtype=np.float32)
        indexy = np.full((celkem, k_dotaz), -1, dtype=np.int64)
        for zacatek in range(0, celkem, VELIKOST_CASTI_HLEDANI):
            konec = min(zacatek + VELIKOST_CASTI_HLEDANI, celkem)
            podobnosti[zacatek:konec], indexy[zacatek:konec] = self._index.search(
                data[zacatek:konec], k_dotaz
            )
            if postup:
                postup(konec, celkem)

        if not vynechat_sebe:
            return podobnosti, indexy

        return _bez_sebe(podobnosti, indexy, k)

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
            nacteny = faiss.read_index(str(cesta))
            graf = getattr(nacteny, "hnsw", None)
            if graf is None:
                raise RuntimeError("Uložený index není typu HNSW.")
            graf.efSearch = self._nastaveni.hnsw_ef_search
            self._index = nacteny
            self._pocet = int(nacteny.ntotal)
            logger.info("Index načten z %s (%d vektorů)", cesta, self._pocet)
            return True
        except Exception as chyba:
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


def _bez_sebe(
    podobnosti: np.ndarray, indexy: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    pocet_radku, sirka = indexy.shape
    if sirka < k:
        indexy = np.pad(indexy, ((0, 0), (0, k - sirka)), constant_values=-1)
        podobnosti = np.pad(podobnosti, ((0, 0), (0, k - sirka)))
    vynechane = (indexy == np.arange(pocet_radku)[:, None]) | (indexy < 0)
    poradi = np.argsort(vynechane, axis=1, kind="stable")[:, :k]
    vybrane_indexy = np.take_along_axis(indexy, poradi, axis=1)
    vybrane_podobnosti = np.take_along_axis(podobnosti, poradi, axis=1)
    neplatne = np.take_along_axis(vynechane, poradi, axis=1)
    vybrane_indexy[neplatne] = -1
    vybrane_podobnosti[neplatne] = 0.0
    return vybrane_podobnosti.astype(np.float32), vybrane_indexy.astype(np.int64)
