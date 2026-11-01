# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from app.db import nyni, pripoj

logger = logging.getLogger(__name__)

VYSLEDEK_SCHVALENO = "schvaleno"
VYSLEDEK_ZAMITNUTO = "zamitnuto"
VYSLEDEK_ODLOZENO = "odlozeno"

PLATNE_VYSLEDKY = {VYSLEDEK_SCHVALENO, VYSLEDEK_ZAMITNUTO, VYSLEDEK_ODLOZENO}


class ChybaSlucovani(RuntimeError):
    """Chyba při zpracování rozhodnutí o sloučení."""


class SluzbaSlucovani:
    def rozhodni(
        self,
        klastr_id: int,
        vysledek: str,
        kdo: str,
        zastupce: str | None = None,
        upraveny_popis: str | None = None,
        poznamka: str | None = None,
    ) -> dict[str, Any]:
        if vysledek not in PLATNE_VYSLEDKY:
            raise ChybaSlucovani(
                f"Neplatný výsledek {vysledek!r}. "
                f"Povolené hodnoty: {', '.join(sorted(PLATNE_VYSLEDKY))}."
            )

        with pripoj() as spojeni:
            klastr = spojeni.execute(
                "SELECT * FROM klastry WHERE id = ?", (klastr_id,)
            ).fetchone()
            if klastr is None:
                raise ChybaSlucovani(f"Klastr {klastr_id} neexistuje.")

            cleny = [
                r["itemnum"] for r in spojeni.execute(
                    "SELECT itemnum FROM klastr_cleny WHERE klastr_id = ?", (klastr_id,)
                ).fetchall()
            ]
            if not cleny:
                raise ChybaSlucovani(f"Klastr {klastr_id} neobsahuje žádné položky.")

            drivejsi = spojeni.execute(
                "SELECT id FROM rozhodnuti WHERE klastr_id = ? AND vzato_zpet = 0",
                (klastr_id,),
            ).fetchone()
            if drivejsi is not None:
                raise ChybaSlucovani(
                    f"O klastru {klastr_id} již bylo rozhodnuto. "
                    f"Nejprve rozhodnutí zrušte."
                )

            zvoleny_zastupce = zastupce or klastr["navrzeny_zastupce"]
            if vysledek == VYSLEDEK_SCHVALENO:
                if not zvoleny_zastupce:
                    raise ChybaSlucovani("Pro schválení je nutné určit referenční záznam.")
                if zvoleny_zastupce not in cleny:
                    raise ChybaSlucovani(
                        f"Záznam {zvoleny_zastupce} není členem klastru {klastr_id}."
                    )

            kurzor = spojeni.execute(
                "INSERT INTO rozhodnuti (klastr_id, vysledek, zastupce, "
                "upraveny_popis, poznamka, rozhodl, rozhodnuto) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (klastr_id, vysledek, zvoleny_zastupce, upraveny_popis,
                 poznamka, kdo, nyni()),
            )
            rozhodnuti_id = int(kurzor.lastrowid or 0)

            if vysledek == VYSLEDEK_SCHVALENO:
                self._proved_slouceni(
                    spojeni, cleny, zvoleny_zastupce, upraveny_popis
                )

            spojeni.execute(
                "UPDATE klastry SET stav = ? WHERE id = ?", (vysledek, klastr_id)
            )


        logger.info("Klastr %d: %s (rozhodl %s).", klastr_id, vysledek, kdo)
        return {
            "rozhodnuti_id": rozhodnuti_id,
            "klastr_id": klastr_id,
            "vysledek": vysledek,
            "zastupce": zvoleny_zastupce,
            "pocet_dotcenych": len(cleny) - 1 if vysledek == VYSLEDEK_SCHVALENO else 0,
        }

    @staticmethod
    def _proved_slouceni(
        spojeni,
        cleny: list[str],
        zastupce: str,
        upraveny_popis: str | None,
    ) -> None:
        for itemnum in cleny:
            if itemnum == zastupce:
                spojeni.execute(
                    "UPDATE polozky SET stav_konsolidace = 'aktivni', "
                    "slouceno_do = NULL WHERE itemnum = ?",
                    (itemnum,),
                )
            else:
                spojeni.execute(
                    "UPDATE polozky SET stav_konsolidace = 'slouceno', "
                    "slouceno_do = ? WHERE itemnum = ?",
                    (zastupce, itemnum),
                )

        if upraveny_popis:
            spojeni.execute(
                "UPDATE polozky SET description = ? WHERE itemnum = ?",
                (upraveny_popis, zastupce),
            )

    def zrus_rozhodnuti(self, klastr_id: int, kdo: str) -> dict[str, Any]:
        with pripoj() as spojeni:
            rozhodnuti = spojeni.execute(
                "SELECT * FROM rozhodnuti WHERE klastr_id = ? AND vzato_zpet = 0 "
                "ORDER BY id DESC LIMIT 1",
                (klastr_id,),
            ).fetchone()
            if rozhodnuti is None:
                raise ChybaSlucovani(
                    f"O klastru {klastr_id} neexistuje žádné platné rozhodnutí."
                )

            cleny = [
                r["itemnum"] for r in spojeni.execute(
                    "SELECT itemnum FROM klastr_cleny WHERE klastr_id = ?", (klastr_id,)
                ).fetchall()
            ]

            for itemnum in cleny:
                spojeni.execute(
                    "UPDATE polozky SET stav_konsolidace = 'aktivni', "
                    "slouceno_do = NULL WHERE itemnum = ?",
                    (itemnum,),
                )

            spojeni.execute(
                "UPDATE rozhodnuti SET vzato_zpet = 1, vzal_zpet = ?, "
                "vzato_zpet_kdy = ? WHERE id = ?",
                (kdo, nyni(), rozhodnuti["id"]),
            )
            spojeni.execute(
                "UPDATE klastry SET stav = 'ke_kontrole' WHERE id = ?", (klastr_id,)
            )


        logger.info("Rozhodnutí o klastru %d zrušeno uživatelem %s.", klastr_id, kdo)
        return {"klastr_id": klastr_id, "stav": "ke_kontrole"}

    def vyjmi_clena(
        self, klastr_id: int, itemnum: str, kdo: str, poznamka: str = ""
    ) -> dict[str, Any]:
        with pripoj() as spojeni:
            klastr = spojeni.execute(
                "SELECT * FROM klastry WHERE id = ?", (klastr_id,)
            ).fetchone()
            if klastr is None:
                raise ChybaSlucovani(f"Skupina {klastr_id} neexistuje.")
            if klastr["stav"] != "ke_kontrole":
                raise ChybaSlucovani(
                    f"O skupině {klastr_id} již bylo rozhodnuto; "
                    "nejprve rozhodnutí zrušte."
                )

            cleny = [
                r["itemnum"] for r in spojeni.execute(
                    "SELECT itemnum FROM klastr_cleny WHERE klastr_id = ?",
                    (klastr_id,),
                ).fetchall()
            ]
            if itemnum not in cleny:
                raise ChybaSlucovani(
                    f"Položka {itemnum} ve skupině {klastr_id} není."
                )

            zbyle = [c for c in cleny if c != itemnum]

            spojeni.execute(
                "DELETE FROM klastr_cleny WHERE klastr_id = ? AND itemnum = ?",
                (klastr_id, itemnum),
            )
            spojeni.execute(
                "DELETE FROM dvojice WHERE klastr_id = ? "
                "AND (itemnum_a = ? OR itemnum_b = ?)",
                (klastr_id, itemnum, itemnum),
            )
            spojeni.execute(
                "INSERT INTO rozhodnuti (klastr_id, vysledek, poznamka, "
                "rozhodl, rozhodnuto) VALUES (?, ?, ?, ?, ?)",
                (klastr_id, "vyjmuto", poznamka or f"vyjmuta položka {itemnum}",
                 kdo, nyni()),
            )

            if len(zbyle) < 2:
                spojeni.execute("DELETE FROM klastry WHERE id = ?", (klastr_id,))
                logger.info(
                    "Skupina %d zrušena - po vyjmutí %s v ní zbyla jediná položka.",
                    klastr_id, itemnum,
                )
                return {"klastr_id": klastr_id, "zbylo_clenu": len(zbyle),
                        "skupina_zrusena": True}

            radky = spojeni.execute(
                "SELECT skore FROM dvojice WHERE klastr_id = ?", (klastr_id,)
            ).fetchall()
            skore = [float(r["skore"]) for r in radky] or [0.0]
            zastupce = klastr["navrzeny_zastupce"]
            spojeni.execute(
                "UPDATE klastry SET velikost = ?, prumerna_podobnost = ?, "
                "minimalni_podobnost = ?, navrzeny_zastupce = ? WHERE id = ?",
                (
                    len(zbyle),
                    sum(skore) / len(skore),
                    min(skore),
                    zastupce if zastupce in zbyle else zbyle[0],
                    klastr_id,
                ),
            )

        logger.info(
            "Ze skupiny %d vyjmuta položka %s (%s).", klastr_id, itemnum, kdo
        )
        return {"klastr_id": klastr_id, "zbylo_clenu": len(zbyle),
                "skupina_zrusena": False}

    def statistiky(self, beh_id: int | None = None) -> dict[str, Any]:
        podminka = " WHERE beh_id = ?" if beh_id else ""
        parametry = [beh_id] if beh_id else []

        with pripoj(pouze_cteni=True) as spojeni:
            radky = spojeni.execute(
                f"SELECT stav, COUNT(*) FROM klastry{podminka} GROUP BY stav", parametry
            ).fetchall()
            podle_stavu = {str(r[0]): int(r[1]) for r in radky}

            slouceno = int(spojeni.execute(
                "SELECT COUNT(*) FROM polozky WHERE stav_konsolidace = 'slouceno'"
            ).fetchone()[0])

        return {
            "podle_stavu": podle_stavu,
            "ke_kontrole": podle_stavu.get("ke_kontrole", 0),
            "schvaleno": podle_stavu.get(VYSLEDEK_SCHVALENO, 0),
            "zamitnuto": podle_stavu.get(VYSLEDEK_ZAMITNUTO, 0),
            "odlozeno": podle_stavu.get(VYSLEDEK_ODLOZENO, 0),
            "sloucenych_zaznamu": slouceno,
        }

    def export_slouceni(self, cesta: Path) -> int:
        with pripoj(pouze_cteni=True) as spojeni:
            radky = spojeni.execute(
                """
                SELECT p.itemnum        AS duplicitni_zaznam,
                       p.description    AS duplicitni_popis,
                       p.slouceno_do    AS referencni_zaznam,
                       z.description    AS referencni_popis,
                       r.rozhodl        AS schvalil,
                       r.rozhodnuto     AS schvaleno_kdy,
                       r.poznamka       AS poznamka,
                       k.id             AS klastr_id,
                       k.prumerna_podobnost AS prumerna_podobnost
                FROM polozky p
                JOIN polozky z ON z.itemnum = p.slouceno_do
                JOIN klastr_cleny kc ON kc.itemnum = p.itemnum
                JOIN klastry k ON k.id = kc.klastr_id
                JOIN rozhodnuti r ON r.klastr_id = k.id AND r.vzato_zpet = 0
                WHERE p.stav_konsolidace = 'slouceno'
                ORDER BY k.id
                """
            ).fetchall()

        cesta.parent.mkdir(parents=True, exist_ok=True)
        with cesta.open("w", encoding="utf-8", newline="") as soubor:
            zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            zapisovac.writerow([
                "DUPLICITNI_ZAZNAM", "DUPLICITNI_POPIS", "REFERENCNI_ZAZNAM",
                "REFERENCNI_POPIS", "SCHVALIL", "SCHVALENO_KDY", "POZNAMKA",
                "KLASTR_ID", "PRUMERNA_PODOBNOST",
            ])
            for r in radky:
                zapisovac.writerow([
                    r["duplicitni_zaznam"], r["duplicitni_popis"],
                    r["referencni_zaznam"], r["referencni_popis"],
                    r["schvalil"], r["schvaleno_kdy"], r["poznamka"] or "",
                    r["klastr_id"], round(float(r["prumerna_podobnost"]), 4),
                ])

        return len(radky)


_sdilena_sluzba: SluzbaSlucovani | None = None


def sluzba_slucovani() -> SluzbaSlucovani:
    global _sdilena_sluzba
    if _sdilena_sluzba is None:
        _sdilena_sluzba = SluzbaSlucovani()
    return _sdilena_sluzba
