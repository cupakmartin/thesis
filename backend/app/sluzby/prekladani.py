# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import asdict, replace
from typing import Any

from app.db import nyni, pripoj
from app.jadro.dokument import rozdel_na_useky, sestav_preklad
from app.jadro.glosar import Glosar, NalezenyTermin, glosar
from app.jadro.jazyky import jazyk
from app.jadro.rag import (
    ZPUSOB_GLOSAR,
    PozadavekPrekladu,
    PrekladacRAG,
    VysledekPrekladu,
)
from app.jadro.validace import KontrolaTerminu, VysledekValidace, zvaliduj_preklad

ZPUSOB_DOKUMENT = "dokument"

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
        terminy_kontroly = vysledek.nalezene_terminy
        if not pozadavek.pouzit_glosar:
            terminy_kontroly = self.prekladac.naplanuj(
                replace(pozadavek, pouzit_glosar=True)
            ).nalezene_terminy
        validace = zvaliduj_preklad(
            zdrojovy_text=vysledek.zdrojovy_text,
            preklad=vysledek.preklad,
            nalezene_terminy=terminy_kontroly,
            zdrojovy_jazyk=vysledek.zdrojovy_jazyk,
            cilovy_jazyk=vysledek.cilovy_jazyk,
        )

        if ulozit:
            self._uloz(vysledek, validace, kdo, itemnum)

        return vysledek, validace

    def prelozi_dokument(
        self,
        text: str,
        zdrojovy_jazyk: str = "en",
        cilovy_jazyk: str = "cs",
        pouzit_glosar: bool = True,
        model: str | None = None,
        kdo: str = "systém",
    ) -> Iterator[dict[str, Any]]:
        jazyk(zdrojovy_jazyk)
        jazyk(cilovy_jazyk)
        if zdrojovy_jazyk == cilovy_jazyk:
            raise ValueError("Zdrojový a cílový jazyk se musí lišit.")
        useky = rozdel_na_useky(text)
        k_prekladu = [u for u in useky if u.prelozit]
        if not k_prekladu:
            raise ValueError("Text neobsahuje nic k překladu.")

        yield {
            "typ": "plan",
            "pocet_useku": len(k_prekladu),
            "pocet_radku": max(u.radek for u in useky) + 1,
            "pocet_znaku": len(text),
        }

        cas_start = time.perf_counter()
        preklady: dict[int, str] = {}
        terminy: dict[str, NalezenyTermin] = {}
        souhrn = VysledekValidace()
        pouzity_model = ""
        opravenych = 0

        for poradi, usek in enumerate(k_prekladu, 1):
            vysledek, validace = self.prelozi(
                PozadavekPrekladu(
                    text=usek.text,
                    zdrojovy_jazyk=zdrojovy_jazyk,
                    cilovy_jazyk=cilovy_jazyk,
                    pouzit_glosar=pouzit_glosar,
                    model=model,
                ),
                kdo=kdo,
                ulozit=False,
            )
            preklady[usek.poradi] = vysledek.preklad
            for nalezeny in vysledek.nalezene_terminy:
                terminy.setdefault(nalezeny.polozka.id, nalezeny)
            if vysledek.zpusob != ZPUSOB_GLOSAR:
                pouzity_model = vysledek.model
            souhrn.kontroly.extend(validace.kontroly)
            souhrn.chybejici_identifikatory.extend(validace.chybejici_identifikatory)
            souhrn.pocet_identifikatoru += validace.pocet_identifikatoru
            if vysledek.prvni_pokus:
                opravenych += 1
            souhrn.varovani.extend(f"Úsek {poradi}: {v}" for v in validace.varovani)

            yield {
                "typ": "usek",
                "poradi": poradi,
                "radek": usek.radek,
                "odrazka": usek.odrazka,
                "zdroj": usek.text,
                "preklad": vysledek.preklad,
                "zpusob": vysledek.zpusob,
                "doba_s": round(vysledek.doba_s, 3),
                "pocet_ocekavanych": validace.pocet_ocekavanych,
                "pocet_dodrzenych": validace.pocet_dodrzenych,
                "problemy": [popis_problemu(k) for k in validace.problemy],
                "chybejici_identifikatory": validace.chybejici_identifikatory,
                "prvni_pokus": vysledek.prvni_pokus,
                "varovani": validace.varovani,
            }

        preklad = sestav_preklad(useky, preklady)
        doba = time.perf_counter() - cas_start
        celkovy = VysledekPrekladu(
            zdrojovy_text=text,
            preklad=preklad,
            zdrojovy_jazyk=zdrojovy_jazyk,
            cilovy_jazyk=cilovy_jazyk,
            pouzity_glosar=pouzit_glosar,
            nalezene_terminy=list(terminy.values()),
            model=pouzity_model or ZPUSOB_GLOSAR,
            doba_s=doba,
            zpusob=ZPUSOB_DOKUMENT,
        )
        self._uloz(celkovy, souhrn, kdo, None)

        yield {
            "typ": "hotovo",
            "preklad": preklad,
            "model": celkovy.model,
            "doba_s": round(doba, 2),
            "pocet_useku": len(k_prekladu),
            "mira_dodrzeni_glosare": souhrn.mira_dodrzeni_glosare,
            "pocet_ocekavanych": souhrn.pocet_ocekavanych,
            "pocet_dodrzenych": souhrn.pocet_dodrzenych,
            "pocet_nespravnych_variant": souhrn.pocet_nespravnych_variant,
            "pocet_identifikatoru": souhrn.pocet_identifikatoru,
            "identifikatory_zachovany": souhrn.identifikatory_zachovany,
            "chybejici_identifikatory": sorted(set(souhrn.chybejici_identifikatory)),
            "pocet_opravenych": opravenych,
            "varovani": souhrn.varovani,
        }

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
                "termin_zdroj": n.polozka.termin(vysledek.zdrojovy_jazyk),
                "termin_cil": n.polozka.termin(vysledek.cilovy_jazyk),
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
            radky = spojeni.execute(
                """
                SELECT pouzity_glosar,
                       COUNT(*),
                       SUM(json_extract(validace_json, '$.pocet_ocekavanych') > 0),
                       SUM(json_extract(validace_json, '$.pocet_ocekavanych')),
                       SUM(json_extract(validace_json, '$.pocet_dodrzenych')),
                       SUM(json_extract(validace_json, '$.nespravne_varianty'))
                FROM preklady GROUP BY pouzity_glosar
                """
            ).fetchall()
            posledni = spojeni.execute(
                """
                SELECT id, vytvoreno, zdrojovy_text, preklad, zdrojovy_jazyk,
                       cilovy_jazyk, pouzity_glosar, model, mira_dodrzeni,
                       json_extract(validace_json, '$.pocet_ocekavanych')
                FROM preklady ORDER BY id DESC LIMIT 5
                """
            ).fetchall()

        podle_glosare: dict[str, dict[str, Any]] = {}
        for r in radky:
            ocekavano = int(r[3] or 0)
            dodrzeno = int(r[4] or 0)
            podle_glosare["s glosářem" if int(r[0]) else "bez glosáře"] = {
                "pocet": int(r[1]),
                "pocet_s_terminy": int(r[2] or 0),
                "ocekavano": ocekavano,
                "dodrzeno": dodrzeno,
                "nespravnych_variant": int(r[5] or 0),
                "prumerne_dodrzeni": round(dodrzeno / ocekavano, 4) if ocekavano else 0.0,
            }
        return {
            "pocet_prekladu": celkem,
            "podle_glosare": podle_glosare,
            "posledni": [
                {
                    "id": r[0],
                    "vytvoreno": r[1],
                    "zdroj": r[2][:160],
                    "preklad": r[3][:160],
                    "zdrojovy_jazyk": r[4],
                    "cilovy_jazyk": r[5],
                    "pouzity_glosar": bool(r[6]),
                    "model": r[7],
                    "mira_dodrzeni": r[8] if int(r[9] or 0) > 0 else None,
                }
                for r in posledni
            ],
        }


def popis_problemu(kontrola: KontrolaTerminu) -> dict[str, Any]:
    return {
        "termin_zdroj": kontrola.termin_zdroj,
        "termin_cil": kontrola.termin_cil,
        "dodrzen": kontrola.dodrzen,
        "nespravna_varianta": (
            kontrola.nespravna_varianta if kontrola.nespravna_varianta_pouzita else ""
        ),
        "chybne_tvary": [list(dvojice) for dvojice in kontrola.chybne_tvary],
    }


_sdilena_sluzba: SluzbaPrekladu | None = None


def sluzba_prekladu() -> SluzbaPrekladu:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaPrekladu()
    return _sdilena_sluzba
