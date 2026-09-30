# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from app.db import nyni, pripoj
from app.jadro.glosar import Glosar, glosar
from app.jadro.rag import PozadavekPrekladu, PrekladacRAG, VysledekPrekladu
from app.jadro.validace import VysledekValidace, zvaliduj_preklad

logger = logging.getLogger(__name__)


class SluzbaPrekladu:
    def __init__(
        self,
        prekladac: PrekladacRAG | None = None,
        zdroj_glosare: Glosar | None = None,
    ) -> None:
        self._prekladac = prekladac
        self._glosar = zdroj_glosare

    @property
    def prekladac(self) -> PrekladacRAG:
        if self._prekladac is None:
            self._prekladac = PrekladacRAG(zdroj_glosare=self._glosar or glosar())
        return self._prekladac

    def prelozi(
        self,
        pozadavek: PozadavekPrekladu,
        kdo: str = "systém",
        itemnum: str | None = None,
        ulozit: bool = True,
    ) -> tuple[VysledekPrekladu, VysledekValidace]:
        vysledek = self.prekladac.prelozi(pozadavek)
        validace = zvaliduj_preklad(
            zdrojovy_text=vysledek.zdrojovy_text,
            preklad=vysledek.preklad,
            nalezene_terminy=vysledek.nalezene_terminy,
            zdrojovy_jazyk=vysledek.zdrojovy_jazyk,
            cilovy_jazyk=vysledek.cilovy_jazyk,
        )

        if ulozit:
            self._uloz(vysledek, validace, kdo, itemnum)

        return vysledek, validace

    @staticmethod
    def _uloz(
        vysledek: VysledekPrekladu,
        validace: VysledekValidace,
        kdo: str,
        itemnum: str | None,
    ) -> int:
        terminy = [
            {
                "id": n.polozka.id,
                "termin_en": n.polozka.termin_en,
                "termin_cs": n.polozka.termin_cs,
                "zpusob": n.zpusob,
                "skore": round(n.skore, 4),
            }
            for n in vysledek.nalezene_terminy
        ]
        podrobnosti_validace = {
            "mira_dodrzeni": validace.mira_dodrzeni_glosare,
            "pocet_ocekavanych": validace.pocet_ocekavanych,
            "pocet_dodrzenych": validace.pocet_dodrzenych,
            "nespravne_varianty": validace.pocet_nespravnych_variant,
            "chybejici_identifikatory": validace.chybejici_identifikatory,
            "varovani": validace.varovani,
            "kontroly": [asdict(k) for k in validace.kontroly],
        }

        with pripoj() as spojeni:
            kurzor = spojeni.execute(
                """
                INSERT INTO preklady (
                    vytvoreno, zdrojovy_text, preklad, zdrojovy_jazyk, cilovy_jazyk,
                    pouzity_glosar, model, doba_s, terminy_json, mira_dodrzeni,
                    validace_json, itemnum, vytvoril
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nyni(), vysledek.zdrojovy_text, vysledek.preklad,
                    vysledek.zdrojovy_jazyk, vysledek.cilovy_jazyk,
                    1 if vysledek.pouzity_glosar else 0, vysledek.model,
                    vysledek.doba_s, json.dumps(terminy, ensure_ascii=False),
                    validace.mira_dodrzeni_glosare,
                    json.dumps(podrobnosti_validace, ensure_ascii=False),
                    itemnum, kdo,
                ),
            )
            return int(kurzor.lastrowid or 0)

    def historie(
        self,
        limit: int = 50,
        odsazeni: int = 0,
        itemnum: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        klauzule = " WHERE itemnum = ?" if itemnum else ""
        parametry: list[Any] = [itemnum] if itemnum else []

        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute(
                f"SELECT COUNT(*) FROM preklady{klauzule}", parametry
            ).fetchone()[0])
            radky = spojeni.execute(
                f"SELECT * FROM preklady{klauzule} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*parametry, limit, odsazeni],
            ).fetchall()

        return [dict(r) for r in radky], celkem

    def statistiky(self) -> dict[str, Any]:
        with pripoj(pouze_cteni=True) as spojeni:
            celkem = int(spojeni.execute("SELECT COUNT(*) FROM preklady").fetchone()[0])
            radek = spojeni.execute(
                "SELECT pouzity_glosar, COUNT(*), AVG(mira_dodrzeni) "
                "FROM preklady GROUP BY pouzity_glosar"
            ).fetchall()

        podle_glosare = {
            ("s glosářem" if int(r[0]) else "bez glosáře"): {
                "pocet": int(r[1]),
                "prumerne_dodrzeni": round(float(r[2] or 0.0), 4),
            }
            for r in radek
        }
        return {"pocet_prekladu": celkem, "podle_glosare": podle_glosare}


_sdilena_sluzba: SluzbaPrekladu | None = None


def sluzba_prekladu() -> SluzbaPrekladu:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaPrekladu()
    return _sdilena_sluzba
