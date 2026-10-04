# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.config import Nastaveni, aktivni_model, nastaveni
from app.jadro.embeddingy import spravce_embeddingu
from app.jadro.llm import ZNACKA_KONCE, ZNACKA_ZACATKU, obal_uzivatelsky_vstup
from app.jadro.normalizace import normalizuj_pro_embedding
from app.jadro.rag import (
    KRATKY_VSTUP_MAX_SLOV,
    ZPUSOB_GLOSAR,
    PozadavekPrekladu,
    PrekladacRAG,
    je_kratky_vstup,
    zpracuj_odpoved,
)
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
    pozadavek = PozadavekPrekladu(
        text=text, zdrojovy_jazyk=zdrojovy_jazyk, cilovy_jazyk=cilovy_jazyk,
        model=model,
    )

    cas = time.perf_counter()
    kratky = je_kratky_vstup(text)
    doba_urceni = time.perf_counter() - cas

    normalizovany = ""
    vektor = None
    doba_normalizace = doba_vektorizace = 0.0
    if not kratky:
        cas = time.perf_counter()
        normalizovany = normalizuj_pro_embedding(text)
        doba_normalizace = time.perf_counter() - cas
        cas = time.perf_counter()
        vektor = spravce_embeddingu().zakoduj_jeden(normalizovany)
        doba_vektorizace = time.perf_counter() - cas

    plan = prekladac.naplanuj(pozadavek)

    zaznam.krok(
        "Určení způsobu překladu",
        "Krátký vstup — slovo, sousloví nebo popisek o nejvýše "
        f"{KRATKY_VSTUP_MAX_SLOV} slovech bez větné interpunkce — se překládá "
        "jinak než věta. Je-li přesně termínem glosáře, odpovědí je glosář "
        "a model se nevolá. Ostatní krátké vstupy dostanou stručnou "
        "instrukci, věty instrukci úplnou.",
        doba_urceni,
        zpusob=plan.zpusob,
        kratky_vstup=kratky,
        pocet_slov=len(text.split()),
    )

    if vektor is not None:
        zaznam.krok(
            "Normalizace vstupu",
            "Sjednocení zápisu před vektorizací. Do promptu vstupuje původní "
            "text; normalizovaná podoba slouží pouze k vyhledání termínů.",
            doba_normalizace,
            vstup=text,
            vystup=normalizovany,
            zmeneno=normalizovany != text.lower().strip(),
        )

        zaznam.krok(
            "Vektorová reprezentace vstupu",
            "Normalizovaný text je převeden na vektor, podle jehož blízkosti "
            "se hledají termíny glosáře. Změní-li se ve vstupu jediný znak, "
            "změní se i tato čísla.",
            doba_vektorizace,
            model=nast.model_embeddingu,
            vektor=_ukazka_vektoru(vektor),
        )
        popis_vyhledani = (
            "Nejprve se hledá doslovný výskyt termínu ve vstupu, poté se "
            "vektorovým dotazem doplňují termíny významově blízké. Do promptu "
            f"se zařadí nejvýše {nast.pocet_termu_z_glosare} termínů "
            f"s podobností nad {nast.prah_relevance_glosare:.2f}."
        )
    elif plan.zpusob == ZPUSOB_GLOSAR:
        popis_vyhledani = (
            "Celý vstup je termínem glosáře ve zdrojovém jazyce. Překladem je "
            "závazný termín z glosáře; u češtiny v přirozeném slovosledu."
        )
    else:
        popis_vyhledani = (
            "U krátkého vstupu se hledají jen doslovné výskyty termínů. "
            "Vektorové vyhledávání se nepoužívá: sousedé jediného slova "
            "ve vektorovém prostoru jsou významově nesouvisející termíny."
        )

    zaznam.krok(
        "Vyhledání termínů glosáře",
        popis_vyhledani,
        plan.doba_vyhledani_s,
        pocet=len(plan.nalezene_terminy),
        terminy=[
            {
                "id": n.polozka.id,
                "zdroj": n.polozka.termin(zdrojovy_jazyk),
                "cil": n.polozka.termin(cilovy_jazyk),
                "skore": round(float(n.skore), 4),
                "zpusob": n.zpusob,
                "je_primy": n.je_primy,
            }
            for n in plan.nalezene_terminy
        ],
    )

    if plan.primy_preklad is not None:
        preklad = plan.primy_preklad
        pouzity_model = ZPUSOB_GLOSAR
        odpoved_doslovne = None
    else:
        uzivatelska_zprava = obal_uzivatelsky_vstup(text)
        zaznam.krok(
            "Sestavení promptu",
            "Systémová instrukce a překládaný text se předávají jako oddělené "
            "zprávy s různou rolí. Text je navíc uzavřen do vymezeného bloku, "
            "o němž instrukce prohlašuje, že jeho obsah jsou data.",
            plan.doba_sestaveni_s,
            zpravy=[
                {"role": "system", "obsah": plan.systemova_instrukce},
                {"role": "user", "obsah": uzivatelska_zprava},
            ],
            znacka_zacatku=ZNACKA_ZACATKU,
            znacka_konce=ZNACKA_KONCE,
            delka_znaku=len(plan.systemova_instrukce) + len(uzivatelska_zprava),
        )

        cas = time.perf_counter()
        odpoved = prekladac.poskytovatel.generuj(
            systemova_instrukce=plan.systemova_instrukce,
            uzivatelsky_vstup=text,
            model=model or aktivni_model(),
            max_tokenu=plan.max_tokenu,
            stop=plan.stop,
        )
        zaznam.krok(
            "Volání jazykového modelu",
            "Požadavek je odeslán službě Ollama na místním počítači. Model běží "
            "lokálně; text neopouští tento stroj. Délka odpovědi je omezena "
            "úměrně délce vstupu a generování zastaví značka vstupního bloku.",
            time.perf_counter() - cas,
            adresa=nast.ollama_url,
            model=odpoved.model,
            temperature=nast.temperature,
            max_tokenu=plan.max_tokenu,
            kontext_tokenu=nast.kontext_modelu,
            zastavovaci_znacky=list(plan.stop),
            tokenu_vstup=odpoved.pocet_tokenu_vstup,
            tokenu_vystup=odpoved.pocet_tokenu_vystup,
            odpoved_doslovne=odpoved.text,
        )
        preklad = zpracuj_odpoved(odpoved.text, text, plan.zpusob)
        pouzity_model = odpoved.model
        odpoved_doslovne = odpoved.text

    cas = time.perf_counter()
    validace = zvaliduj_preklad(
        zdrojovy_text=text,
        preklad=preklad,
        nalezene_terminy=plan.nalezene_terminy,
        zdrojovy_jazyk=zdrojovy_jazyk,
        cilovy_jazyk=cilovy_jazyk,
    )
    zaznam.krok(
        "Kontrola výstupu",
        "Z odpovědi modelu se ponechá jen překlad. U každého termínu, který "
        "se ve zdrojovém textu vyskytl, se ověřuje, zda se jeho závazný "
        "překlad objevil i ve výsledku. Porovnávají se kmeny slov, protože "
        "čeština termíny ohýbá.",
        time.perf_counter() - cas,
        preklad=preklad,
        odpoved_upravena=(
            odpoved_doslovne is not None and odpoved_doslovne.strip() != preklad
        ),
        mira_dodrzeni=round(validace.mira_dodrzeni_glosare, 4),
        ocekavano=validace.pocet_ocekavanych,
        dodrzeno=validace.pocet_dodrzenych,
        identifikatory_zachovany=validace.identifikatory_zachovany,
        souhrn=validace.souhrn(),
    )

    return {
        "vstup": text,
        "vystup": preklad,
        "zpusob": plan.zpusob,
        "zdrojovy_jazyk": zdrojovy_jazyk,
        "cilovy_jazyk": cilovy_jazyk,
        "model": pouzity_model,
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
