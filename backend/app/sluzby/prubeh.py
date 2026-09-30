# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.config import Nastaveni, aktivni_model, nastaveni
from app.jadro.embeddingy import spravce_embeddingu
from app.jadro.llm import ZNACKA_KONCE, ZNACKA_ZACATKU, obal_uzivatelsky_vstup
from app.jadro.normalizace import normalizuj_pro_embedding
from app.jadro.rag import PrekladacRAG
from app.jadro.validace import zvaliduj_preklad

POCET_SLOZEK_VEKTORU = 16

@dataclass
class Krok:
    """Jeden krok zpracování."""

    poradi: int
    nazev: str
    popis: str
    doba_ms: float = 0.0
    udaje: dict[str, Any] = field(default_factory=dict)

    def jako_slovnik(self) -> dict[str, Any]:
        return {
            "poradi": self.poradi,
            "nazev": self.nazev,
            "popis": self.popis,
            "doba_ms": round(self.doba_ms, 2),
            "udaje": self.udaje,
        }


class ZaznamPrubehu:
    def __init__(self) -> None:
        self._kroky: list[Krok] = []

    def krok(self, nazev: str, popis: str, doba_s: float,
             **udaje: Any) -> None:
        self._kroky.append(
            Krok(len(self._kroky) + 1, nazev, popis, doba_s * 1000.0, udaje)
        )

    def jako_slovnik(self) -> list[dict[str, Any]]:
        return [k.jako_slovnik() for k in self._kroky]


def _ukazka_vektoru(vektor) -> dict[str, Any]:
    import numpy as np

    pole = np.asarray(vektor, dtype=float).ravel()
    return {
        "dimenze": int(pole.size),
        "prvnich_n": [round(float(h), 5) for h in pole[:POCET_SLOZEK_VEKTORU]],
        "norma": round(float(np.linalg.norm(pole)), 5),
        "nejmensi": round(float(pole.min()), 5),
        "nejvetsi": round(float(pole.max()), 5),
    }


def prubeh_prekladu(
    text: str,
    zdrojovy_jazyk: str = "en",
    cilovy_jazyk: str = "cs",
    model: str | None = None,
    konfigurace: Nastaveni | None = None,
) -> dict[str, Any]:
    nast = konfigurace or nastaveni()
    zaznam = ZaznamPrubehu()
    prekladac = PrekladacRAG(nast)

    cas = time.perf_counter()
    normalizovany = normalizuj_pro_embedding(text)
    zaznam.krok(
        "Normalizace vstupu",
        "Sjednocení zápisu před vektorizací. Do promptu vstupuje původní "
        "text; normalizovaná podoba slouží pouze k vyhledání termínů.",
        time.perf_counter() - cas,
        vstup=text,
        vystup=normalizovany,
        zmeneno=normalizovany != text.lower().strip(),
    )

    cas = time.perf_counter()
    vektor = spravce_embeddingu().zakoduj_jeden(text)
    zaznam.krok(
        "Vektorová reprezentace vstupu",
        "Text je převeden na vektor, podle jehož blízkosti se hledají "
        "termíny glosáře. Změní-li se ve vstupu jediný znak, změní se "
        "i tato čísla.",
        time.perf_counter() - cas,
        model=nast.model_embeddingu,
        vektor=_ukazka_vektoru(vektor),
    )

    cas = time.perf_counter()
    nalezene = prekladac.glosar.najdi_relevantni(text)
    doba_hledani = time.perf_counter() - cas
    zaznam.krok(
        "Vyhledání termínů glosáře",
        "Nejprve se hledá doslovný výskyt termínu ve vstupu, poté se "
        "vektorovým dotazem doplňují termíny významově blízké. Do promptu "
        f"se zařadí nejvýše {nast.pocet_termu_z_glosare} termínů "
        f"s podobností nad {nast.prah_relevance_glosare:.2f}.",
        doba_hledani,
        pocet=len(nalezene),
        terminy=[
            {
                "id": n.polozka.id,
                "en": n.polozka.termin_en,
                "cs": n.polozka.termin_cs,
                "skore": round(float(n.skore), 4),
                "zpusob": n.zpusob,
                "je_primy": n.je_primy,
            }
            for n in nalezene
        ],
    )

    cas = time.perf_counter()
    instrukce = prekladac.sestav_instrukci(nalezene, zdrojovy_jazyk, cilovy_jazyk)
    uzivatelska_zprava = obal_uzivatelsky_vstup(text)
    zaznam.krok(
        "Sestavení promptu",
        "Systémová instrukce a překládaný text se předávají jako oddělené "
        "zprávy s různou rolí. Text je navíc uzavřen do vymezeného bloku, "
        "o němž instrukce prohlašuje, že jeho obsah jsou data.",
        time.perf_counter() - cas,
        zpravy=[
            {"role": "system", "obsah": instrukce},
            {"role": "user", "obsah": uzivatelska_zprava},
        ],
        znacka_zacatku=ZNACKA_ZACATKU,
        znacka_konce=ZNACKA_KONCE,
        delka_znaku=len(instrukce) + len(uzivatelska_zprava),
    )

    pouzity_model = model or aktivni_model()
    cas = time.perf_counter()
    odpoved = prekladac.poskytovatel.generuj(
        systemova_instrukce=instrukce,
        uzivatelsky_vstup=text,
        model=pouzity_model,
    )
    doba_modelu = time.perf_counter() - cas
    zaznam.krok(
        "Volání jazykového modelu",
        "Požadavek je odeslán službě Ollama na místním počítači. Model běží "
        "lokálně; text neopouští tento stroj.",
        doba_modelu,
        adresa=nast.ollama_url,
        model=odpoved.model,
        temperature=nast.temperature,
        max_tokenu=nast.max_tokenu_odpovedi,
        tokenu_vstup=odpoved.pocet_tokenu_vstup,
        tokenu_vystup=odpoved.pocet_tokenu_vystup,
        odpoved_doslovne=odpoved.text,
    )

    cas = time.perf_counter()
    validace = zvaliduj_preklad(
        zdrojovy_text=text,
        preklad=odpoved.text,
        nalezene_terminy=nalezene,
        zdrojovy_jazyk=zdrojovy_jazyk,
        cilovy_jazyk=cilovy_jazyk,
    )
    zaznam.krok(
        "Kontrola výstupu",
        "U každého termínu, který se ve zdrojovém textu vyskytl, se ověřuje, "
        "zda se jeho závazný překlad objevil i ve výsledku. Porovnávají se "
        "kmeny slov, protože čeština termíny ohýbá.",
        time.perf_counter() - cas,
        mira_dodrzeni=round(validace.mira_dodrzeni_glosare, 4),
        ocekavano=validace.pocet_ocekavanych,
        dodrzeno=validace.pocet_dodrzenych,
        identifikatory_zachovany=validace.identifikatory_zachovany,
        souhrn=validace.souhrn(),
    )

    return {
        "vstup": text,
        "vystup": odpoved.text,
        "zdrojovy_jazyk": zdrojovy_jazyk,
        "cilovy_jazyk": cilovy_jazyk,
        "model": odpoved.model,
        "doba_celkem_ms": round(
            sum(k["doba_ms"] for k in zaznam.jako_slovnik()), 2
        ),
        "kroky": zaznam.jako_slovnik(),
    }


def prubeh_podobnosti(
    prvni: str, druhy: str, konfigurace: Nastaveni | None = None
) -> dict[str, Any]:
    import numpy as np

    nast = konfigurace or nastaveni()
    spravce = spravce_embeddingu()

    cas = time.perf_counter()
    vektory = [spravce.zakoduj_jeden(prvni), spravce.zakoduj_jeden(druhy)]
    doba = time.perf_counter() - cas

    a = np.asarray(vektory[0], dtype=float).ravel()
    b = np.asarray(vektory[1], dtype=float).ravel()
    podobnost = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

    return {
        "prvni": {"text": prvni, "vektor": _ukazka_vektoru(a)},
        "druhy": {"text": druhy, "vektor": _ukazka_vektoru(b)},
        "kosinova_podobnost": round(podobnost, 5),
        "skalarni_soucin": round(float(a @ b), 5),
        "model": nast.model_embeddingu,
        "doba_ms": round(doba * 1000.0, 2),
        "prah_kandidatu": nast.prah_podobnosti,
    }
