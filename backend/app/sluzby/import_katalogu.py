# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import nastaveni
from app.db import nyni, precti_volbu, pripoj, smaz_volbu, uloz_volbu
from app.jadro.csv_import import (
    ROLE,
    ROLE_ID,
    ROLE_JAZYK,
    ROLE_POPIS,
    ROLE_SKUPINA,
    ROLE_TRIDA,
    ChybaCsv,
    ObsahCsv,
    nacti_csv,
    navrhni_sloupce,
    rozpoznej_jazyk,
)
from app.jadro.jazyky import je_podporovany
from app.jadro.postup import BEZ_SLEDOVANI, SledovaniPostupu
from app.jadro.taxonomie import zarad_pravidlove

logger = logging.getLogger(__name__)

POSTUP_IMPORTU = SledovaniPostupu()
FAZE_CTENI = "cteni"
FAZE_ZPRACOVANI = "zpracovani"
FAZE_ZAPIS = "zapis"
KROK_HLASENI_IMPORTU = 2000
VELIKOST_DAVKY_ZAPISU = 5000
SEKUND_NA_BAJT_CTENI = 0.00000008
SEKUND_NA_BAJT_ZPRACOVANI = 0.0000004
SEKUND_NA_BAJT_ZAPISU = 0.0000003

KLIC_SMAZANO = "katalog_smazan"
MAX_VELIKOST_CSV = 50 * 1024 * 1024
REZIMY_JAZYKA = ("ne", "sloupec", "sloupce")
ZDROJ_IMPORT = "import"
ZDROJ_GENEROVANY = "generovany"
ZDROJ_PUVODNI = "puvodni"
PLATNOST_NAHLEDU_S = 24 * 3600

SLOUPCE_MAXIMO = {
    "itemnum": "ITEMNUM",
    "description": "DESCRIPTION",
    "long_description": "DESCRIPTION_LONGDESCRIPTION",
    "itemtype": "ITEMTYPE",
    "commodity_group": "COMMODITYGROUP",
    "order_unit": "ORDERUNIT",
    "issue_unit": "ISSUEUNIT",
    "status": "STATUS",
    "rotating": "ROTATING",
    "manufacturer": "MANUFACTURER",
    "model_num": "MODELNUM",
    "vendor": "VENDOR",
    "external_ref_id": "EXTERNALREFID",
    "iso_class": "ISOCLASS",
    "lang_code": "LANGCODE",
    "change_date": "CHANGEDATE",
    "change_by": "CHANGEBY",
}
ROLE_MAXIMO = {
    "ITEMNUM": ROLE_ID,
    "DESCRIPTION": ROLE_POPIS,
    "COMMODITYGROUP": ROLE_SKUPINA,
    "ISOCLASS": ROLE_TRIDA,
    "LANGCODE": ROLE_JAZYK,
}
DALSI_POLE_MAXIMO = {
    v: k for k, v in SLOUPCE_MAXIMO.items()
    if k not in {"itemnum", "description", "commodity_group", "iso_class", "lang_code"}
}


class ChybaImportu(ValueError):
    pass


@dataclass
class SloupecKatalogu:
    nazev: str
    role: str = ""
    jazyk: str = ""
    puvodni: str = ""
    index: int = -1


@dataclass
class NastaveniImportu:
    sloupce: list[SloupecKatalogu]
    ma_id: bool = True
    vicejazycny: str = "ne"
    mapa_jazyku: dict[str, str] = field(default_factory=dict)
    jazyk_katalogu: str = ""


def metadata() -> dict[str, Any] | None:
    with pripoj(pouze_cteni=True) as spojeni:
        radek = spojeni.execute("SELECT * FROM katalog WHERE id = 1").fetchone()
    if radek is None:
        return None
    return {
        "nazev_souboru": radek["nazev_souboru"],
        "zdroj": radek["zdroj"],
        "importovano": radek["importovano"],
        "kdo": radek["kdo"],
        "sloupce": json.loads(radek["sloupce_json"]),
        "nastaveni": json.loads(radek["nastaveni_json"]),
        "pocet_polozek": radek["pocet_polozek"],
        "preskoceno": radek["preskoceno"],
    }


def nastaveni_podle_navrhu(obsah: ObsahCsv) -> NastaveniImportu:
    navrhy = navrhni_sloupce(obsah)
    sloupce = [
        SloupecKatalogu(
            nazev=n.puvodni, role=n.navrh_role, jazyk=n.navrh_jazyk,
            puvodni=n.puvodni, index=n.index,
        )
        for n in navrhy
    ]
    jazykovy = next((n for n in navrhy if n.navrh_role == ROLE_JAZYK), None)
    mapa = {h: rozpoznej_jazyk(h) for h in (jazykovy.hodnoty or [])} if jazykovy else {}
    return NastaveniImportu(
        sloupce=sloupce,
        ma_id=any(s.role == ROLE_ID for s in sloupce),
        vicejazycny="sloupec" if jazykovy else "ne",
        mapa_jazyku=mapa,
    )


def _ukazka(hodnoty: list[str], pocet: int = 5) -> str:
    return ", ".join(f"„{h}“" for h in hodnoty[:pocet]) + (" …" if len(hodnoty) > pocet else "")


def over_nastaveni(obsah: ObsahCsv, nast: NastaveniImportu) -> None:
    indexy = sorted(s.index for s in nast.sloupce)
    if indexy != list(range(len(obsah.sloupce))):
        raise ChybaImportu("Nastavení musí obsahovat každý sloupec souboru právě jednou.")

    nazvy = [s.nazev.strip() for s in nast.sloupce]
    if any(not n for n in nazvy):
        raise ChybaImportu("Každý sloupec musí mít název.")
    duplicitni = sorted({n for n in nazvy if [x.casefold() for x in nazvy].count(n.casefold()) > 1})
    if duplicitni:
        raise ChybaImportu(f"Názvy sloupců se opakují: {_ukazka(duplicitni)}.")

    for s in nast.sloupce:
        if s.role and s.role not in ROLE:
            raise ChybaImportu(f"Neznámá role sloupce „{s.nazev}“: {s.role}.")
        if s.jazyk and not je_podporovany(s.jazyk):
            raise ChybaImportu(f"Sloupec „{s.nazev}“ má nepodporovaný jazyk {s.jazyk}.")
    if nast.vicejazycny not in REZIMY_JAZYKA:
        raise ChybaImportu(f"Neznámý způsob zápisu jazyka: {nast.vicejazycny}.")

    def s_roli(role: str) -> list[SloupecKatalogu]:
        return [s for s in nast.sloupce if s.role == role]

    if not s_roli(ROLE_POPIS):
        raise ChybaImportu("Označte alespoň jeden sloupec s popisem položky - ten se porovnává při deduplikaci.")
    for role, nazev in ((ROLE_SKUPINA, "skupina"), (ROLE_TRIDA, "třída ISO")):
        if len(s_roli(role)) > 1:
            raise ChybaImportu(f"Roli „{nazev}“ může mít nejvýše jeden sloupec.")

    idcka = s_roli(ROLE_ID)
    if nast.ma_id:
        if len(idcka) != 1:
            raise ChybaImportu("Označte právě jeden sloupec s ID položek.")
        hodnoty = [r[idcka[0].index] for r in obsah.radky]
        prazdne = sum(1 for h in hodnoty if not h)
        if prazdne:
            raise ChybaImportu(f"{prazdne} řádků nemá vyplněné ID ve sloupci „{idcka[0].nazev}“.")
        opakovane = sorted(h for h, pocet in Counter(hodnoty).items() if pocet > 1)
        if opakovane:
            raise ChybaImportu(
                f"ID ve sloupci „{idcka[0].nazev}“ nejsou jedinečná, opakuje se {len(opakovane)} "
                f"hodnot: {_ukazka(opakovane)}. Zvolte jiný sloupec, nebo nechte ID vygenerovat."
            )
    elif idcka:
        raise ChybaImportu("Soubor je označen jako soubor bez ID, sloupec nemůže mít roli ID.")

    jazykove = s_roli(ROLE_JAZYK)
    if nast.vicejazycny == "sloupec":
        if len(jazykove) != 1:
            raise ChybaImportu("Označte právě jeden sloupec, který uvádí jazyk záznamu.")
        hodnoty = sorted({r[jazykove[0].index] for r in obsah.radky if r[jazykove[0].index]})
        nezname = [
            h for h in hodnoty
            if h not in nast.mapa_jazyku and not rozpoznej_jazyk(h)
        ]
        if nezname:
            raise ChybaImportu(f"Přiřaďte jazyk hodnotám {_ukazka(nezname)} ve sloupci „{jazykove[0].nazev}“.")
        for kod in nast.mapa_jazyku.values():
            if kod and not je_podporovany(kod):
                raise ChybaImportu(f"Jazyk {kod} není podporován.")
    elif jazykove:
        raise ChybaImportu("Roli „jazyk“ lze použít jen u souboru s jazykem v samostatném sloupci.")

    if nast.vicejazycny == "sloupce":
        if len([s for s in nast.sloupce if s.jazyk]) < 2:
            raise ChybaImportu("Označte jazyk alespoň u dvou sloupců.")
        if any(not s.jazyk for s in s_roli(ROLE_POPIS)):
            raise ChybaImportu("U vícejazyčného souboru musí mít každý sloupec s popisem uvedený jazyk.")

    if nast.jazyk_katalogu and not je_podporovany(nast.jazyk_katalogu):
        raise ChybaImportu(f"Jazyk {nast.jazyk_katalogu} není podporován.")


def _nazev_generovaneho_id(nazvy: list[str]) -> str:
    for kandidat in ("ID", "ID položky", "Vygenerované ID"):
        if kandidat.casefold() not in {n.casefold() for n in nazvy}:
            return kandidat
    return f"ID {uuid.uuid4().hex[:4]}"


def _sestav(
    obsah: ObsahCsv, nast: NastaveniImportu, postup: SledovaniPostupu = BEZ_SLEDOVANI
) -> tuple[list[dict[str, Any]], list[SloupecKatalogu], int]:
    sloupce = sorted(nast.sloupce, key=lambda s: s.index)
    for s in sloupce:
        s.nazev = s.nazev.strip()
    if not nast.ma_id:
        sloupce.insert(0, SloupecKatalogu(
            nazev=_nazev_generovaneho_id([s.nazev for s in sloupce]), role=ROLE_ID,
        ))

    def prvni(role: str) -> SloupecKatalogu | None:
        return next((s for s in sloupce if s.role == role), None)

    popisove = [s for s in sloupce if s.role == ROLE_POPIS]
    sloupec_id, sloupec_jazyka = prvni(ROLE_ID), prvni(ROLE_JAZYK)
    sloupec_skupiny, sloupec_tridy = prvni(ROLE_SKUPINA), prvni(ROLE_TRIDA)
    dalsi_maximo = {
        s.index: DALSI_POLE_MAXIMO[s.puvodni.upper()]
        for s in sloupce if s.index >= 0 and s.puvodni.upper() in DALSI_POLE_MAXIMO
    }
    sirka = max(4, len(str(len(obsah.radky))))

    polozky: list[dict[str, Any]] = []
    preskoceno = 0
    postup.faze(FAZE_ZPRACOVANI, len(obsah.radky))
    for poradi, radek in enumerate(obsah.radky):
        if poradi % KROK_HLASENI_IMPORTU == 0:
            postup.posun(poradi)

        def hodnota(s: SloupecKatalogu | None) -> str:
            return radek[s.index] if s is not None and s.index >= 0 else ""

        popis = " ".join(h for h in (hodnota(s) for s in popisove) if h)
        if not popis:
            preskoceno += 1
            continue
        itemnum = hodnota(sloupec_id) if nast.ma_id else str(poradi + 1).zfill(sirka)

        if nast.vicejazycny == "sloupec":
            surovy = hodnota(sloupec_jazyka)
            jazyk = nast.mapa_jazyku.get(surovy, rozpoznej_jazyk(surovy))
        elif nast.vicejazycny == "sloupce":
            jazyk = popisove[0].jazyk
        else:
            jazyk = nast.jazyk_katalogu

        skupina = hodnota(sloupec_skupiny)
        trida = hodnota(sloupec_tridy)
        if not trida:
            zarazeni = zarad_pravidlove(popis, skupina)
            trida = zarazeni.kod if zarazeni else ""

        data = {
            s.nazev: (itemnum if s.index < 0 else radek[s.index]) for s in sloupce
        }
        polozka: dict[str, Any] = {
            "itemnum": itemnum,
            "description": popis,
            "commodity_group": skupina,
            "iso_class": trida,
            "lang_code": jazyk.upper(),
            "poradi": poradi,
            "data_json": json.dumps(data, ensure_ascii=False),
        }
        for index, pole in dalsi_maximo.items():
            polozka[pole] = radek[index]
        polozka["rotating"] = 1 if str(polozka.get("rotating", "")).strip().lower() in {"1", "true", "ano", "yes"} else 0
        polozky.append(polozka)
    return polozky, sloupce, preskoceno


def _smaz_v_transakci(spojeni: sqlite3.Connection) -> dict[str, int]:
    pocty = {
        "polozek": int(spojeni.execute("SELECT COUNT(*) FROM polozky").fetchone()[0]),
        "behu": int(spojeni.execute("SELECT COUNT(*) FROM behy").fetchone()[0]),
        "udalosti": int(spojeni.execute("SELECT COUNT(*) FROM mif_udalosti").fetchone()[0]),
    }
    spojeni.execute("DELETE FROM behy")
    spojeni.execute("DELETE FROM mif_udalosti")
    spojeni.execute("DELETE FROM polozky")
    spojeni.execute("DELETE FROM katalog")
    return pocty


def _invaliduj() -> None:
    from app.sluzby.katalog import sluzba_katalogu

    sluzba_katalogu().invaliduj_index()


def smaz_katalog(kdo: str = "neznámý") -> dict[str, int]:
    with pripoj() as spojeni:
        pocty = _smaz_v_transakci(spojeni)
    uloz_volbu(KLIC_SMAZANO, "1", kdo=kdo)
    _invaliduj()
    logger.info("Katalog smazán (%s): %s", kdo, pocty)
    return pocty


def importuj_obsah(
    obsah: ObsahCsv,
    nast: NastaveniImportu,
    nazev_souboru: str,
    zdroj: str = ZDROJ_IMPORT,
    kdo: str = "neznámý",
    postup: SledovaniPostupu = BEZ_SLEDOVANI,
) -> dict[str, Any]:
    over_nastaveni(obsah, nast)
    polozky, sloupce, preskoceno = _sestav(obsah, nast, postup)
    if not polozky:
        raise ChybaImportu("Žádný řádek nemá vyplněný popis, katalog by byl prázdný.")

    pole = ["itemnum", "description", "commodity_group", "iso_class", "lang_code",
            "poradi", "data_json", *DALSI_POLE_MAXIMO.values()]
    nastaveni_json = json.dumps({
        "ma_id": nast.ma_id,
        "vicejazycny": nast.vicejazycny,
        "mapa_jazyku": nast.mapa_jazyku,
        "jazyk_katalogu": nast.jazyk_katalogu,
        "kodovani": obsah.kodovani,
        "oddelovac": obsah.oddelovac,
    }, ensure_ascii=False)

    postup.faze(FAZE_ZAPIS, len(polozky))
    with pripoj() as spojeni:
        smazano = _smaz_v_transakci(spojeni)
        prikaz = f"INSERT INTO polozky ({', '.join(pole)}) VALUES ({', '.join('?' * len(pole))})"
        for zacatek in range(0, len(polozky), VELIKOST_DAVKY_ZAPISU):
            spojeni.executemany(prikaz, [
                tuple(p.get(k, "") for k in pole)
                for p in polozky[zacatek:zacatek + VELIKOST_DAVKY_ZAPISU]
            ])
            postup.posun(min(zacatek + VELIKOST_DAVKY_ZAPISU, len(polozky)))
        spojeni.execute(
            "INSERT INTO katalog (id, nazev_souboru, zdroj, importovano, kdo, "
            "sloupce_json, nastaveni_json, pocet_polozek, preskoceno) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
            (nazev_souboru, zdroj, nyni(), kdo,
             json.dumps([asdict(s) for s in sloupce], ensure_ascii=False),
             nastaveni_json, len(polozky), preskoceno),
        )
    smaz_volbu(KLIC_SMAZANO)
    _invaliduj()
    logger.info("Importován katalog %s: %d položek (%s).", nazev_souboru, len(polozky), kdo)
    return {
        "pocet_polozek": len(polozky),
        "preskoceno": preskoceno,
        "pocet_sloupcu": len(sloupce),
        "nazev_souboru": nazev_souboru,
        "smazano": smazano,
    }


def importuj_soubor(
    cesta: Path, kdo: str = "systém", zdroj: str = ZDROJ_IMPORT
) -> dict[str, Any]:
    if not cesta.exists():
        raise FileNotFoundError(f"Soubor katalogu nebyl nalezen: {cesta}.")
    obsah = nacti_csv(cesta.read_bytes())
    return importuj_obsah(obsah, nastaveni_podle_navrhu(obsah), cesta.name, zdroj, kdo)


def _adresar_nahledu() -> Path:
    adresar = nastaveni().adresar_cache / "import"
    adresar.mkdir(parents=True, exist_ok=True)
    return adresar


def uloz_nahled(
    data: bytes,
    nazev_souboru: str,
    kodovani: str | None = None,
    oddelovac: str | None = None,
) -> dict[str, Any]:
    if len(data) > MAX_VELIKOST_CSV:
        raise ChybaImportu("Soubor je větší než 50 MB.")
    obsah = nacti_csv(data, kodovani=kodovani, oddelovac=oddelovac)

    adresar = _adresar_nahledu()
    for stary in adresar.glob("*.csv"):
        if time.time() - stary.stat().st_mtime > PLATNOST_NAHLEDU_S:
            stary.unlink(missing_ok=True)
            stary.with_suffix(".json").unlink(missing_ok=True)
    token = uuid.uuid4().hex
    (adresar / f"{token}.csv").write_bytes(data)
    (adresar / f"{token}.json").write_text(json.dumps({
        "nazev_souboru": nazev_souboru,
        "kodovani": obsah.kodovani,
        "oddelovac": obsah.oddelovac,
    }), encoding="utf-8")

    navrh = nastaveni_podle_navrhu(obsah)
    return {
        "token": token,
        "nazev_souboru": nazev_souboru,
        "kodovani": obsah.kodovani,
        "oddelovac": obsah.oddelovac,
        "pocet_radku": len(obsah.radky),
        "radku_s_prebytkem": obsah.radku_s_prebytkem,
        "sloupce": [asdict(n) for n in navrhni_sloupce(obsah)],
        "navrh": {
            "ma_id": navrh.ma_id,
            "vicejazycny": navrh.vicejazycny,
            "mapa_jazyku": navrh.mapa_jazyku,
        },
    }


def importuj_nahled(token: str, nast: NastaveniImportu, kdo: str = "neznámý") -> dict[str, Any]:
    if not token.isalnum():
        raise ChybaImportu("Neplatný identifikátor nahraného souboru.")
    adresar = _adresar_nahledu()
    soubor, popis = adresar / f"{token}.csv", adresar / f"{token}.json"
    if not soubor.exists() or not popis.exists():
        raise ChybaImportu("Nahraný soubor už není k dispozici, nahrajte jej prosím znovu.")
    udaje = json.loads(popis.read_text(encoding="utf-8"))
    velikost = soubor.stat().st_size
    POSTUP_IMPORTU.zacni("import", [
        (FAZE_CTENI, "Čtení souboru", velikost * SEKUND_NA_BAJT_CTENI),
        (FAZE_ZPRACOVANI, "Zpracování řádků", velikost * SEKUND_NA_BAJT_ZPRACOVANI),
        (FAZE_ZAPIS, "Zápis do databáze", velikost * SEKUND_NA_BAJT_ZAPISU),
    ])
    try:
        POSTUP_IMPORTU.faze(FAZE_CTENI)
        obsah = nacti_csv(
            soubor.read_bytes(), kodovani=udaje["kodovani"], oddelovac=udaje["oddelovac"]
        )
        vysledek = importuj_obsah(
            obsah, nast, udaje["nazev_souboru"], ZDROJ_IMPORT, kdo, POSTUP_IMPORTU
        )
    except Exception as chyba:
        POSTUP_IMPORTU.selhej(str(chyba))
        raise
    POSTUP_IMPORTU.dokonci()
    soubor.unlink(missing_ok=True)
    popis.unlink(missing_ok=True)
    return vysledek


def generuj(pocet: int = 5000, seed: int | None = None, kdo: str = "neznámý") -> dict[str, Any]:
    from app.data.generator_katalogu import (
        VYCHOZI_SEED,
        generuj_katalog,
        zapis_ground_truth,
        zapis_katalog,
    )

    cesta = nastaveni().soubor_katalogu
    cesta.parent.mkdir(parents=True, exist_ok=True)
    katalog = generuj_katalog(pocet, VYCHOZI_SEED if seed is None else seed)
    zapis_katalog(katalog, cesta)
    zapis_ground_truth(katalog, cesta.parent / "ground_truth.csv")
    return importuj_soubor(cesta, kdo=kdo, zdroj=ZDROJ_GENEROVANY)


def zajisti_metadata() -> bool:
    if metadata() is not None:
        return False
    with pripoj() as spojeni:
        radky = spojeni.execute("SELECT * FROM polozky ORDER BY poradi").fetchall()
        if not radky:
            return False
        sloupce = [
            SloupecKatalogu(nazev=nazev, role=ROLE_MAXIMO.get(nazev, ""), puvodni=nazev, index=i)
            for i, nazev in enumerate(SLOUPCE_MAXIMO.values())
        ]
        jazyky = sorted({r["lang_code"] for r in radky if r["lang_code"]})
        spojeni.executemany(
            "UPDATE polozky SET data_json = ? WHERE itemnum = ?",
            [
                (json.dumps({nazev: str(r[klic] if r[klic] is not None else "")
                             for klic, nazev in SLOUPCE_MAXIMO.items()}, ensure_ascii=False),
                 r["itemnum"])
                for r in radky
            ],
        )
        spojeni.execute(
            "INSERT INTO katalog (id, nazev_souboru, zdroj, importovano, kdo, "
            "sloupce_json, nastaveni_json, pocet_polozek, preskoceno) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0)",
            (nastaveni().soubor_katalogu.name, ZDROJ_PUVODNI, nyni(), "systém",
             json.dumps([asdict(s) for s in sloupce], ensure_ascii=False),
             json.dumps({"ma_id": True, "vicejazycny": "sloupec" if jazyky else "ne",
                         "mapa_jazyku": {j: rozpoznej_jazyk(j) for j in jazyky},
                         "jazyk_katalogu": ""}, ensure_ascii=False),
             len(radky)),
        )
    logger.info("Ke stávajícímu katalogu doplněna metadata sloupců (%d položek).", len(radky))
    return True


def pri_startu() -> None:
    if zajisti_metadata():
        return
    if metadata() is not None or precti_volbu(KLIC_SMAZANO):
        return
    cesta = nastaveni().soubor_katalogu
    if cesta.exists():
        try:
            vysledek = importuj_soubor(cesta, kdo="systém", zdroj=ZDROJ_GENEROVANY)
            logger.info("Při startu načteno %d položek katalogu.", vysledek["pocet_polozek"])
        except (ChybaCsv, ChybaImportu, OSError) as chyba:
            logger.warning("Katalog se při startu nepodařilo načíst: %s", chyba)
