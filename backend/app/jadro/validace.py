# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.jadro.atributy import vytez_atributy
from app.jadro.glosar import NalezenyTermin
from app.jadro.jazyky import obsahuje_cjk
from app.jadro.normalizace import odstran_diakritiku

DELKA_KONCOVKY_PODLE_DELKY: tuple[tuple[int, int], ...] = (
    (6, 2),
    (4, 1),
    (0, 0),
)

MAXIMALNI_ROZDIL_KMENU = 2
JAZYKY_SE_SLOZENINAMI: frozenset[str] = frozenset({"de"})
MINIMALNI_DELKA_CASTI_SLOZENINY = 4
MAXIMALNI_KONCOVKA_SLOZENINY = 3
MINIMALNI_DELKA_PRO_POMER = 20
MINIMALNI_SPOLECNY_ZACATEK = 5
MINIMALNI_PODIL_SPOLECNEHO_ZACATKU = 0.6

SPOJKY: frozenset[str] = frozenset({"and", "or", "a", "nebo"})

NEVYZNAMOVA_SLOVA: frozenset[str] = frozenset({
    "a", "i", "o", "u", "v", "s", "z", "k", "na", "pro", "do", "od", "se", "je",
    "the", "a", "an", "of", "for", "to", "in", "on", "and", "or",
})


def _kmen(slovo: str) -> str:
    for minimalni_delka, koncovka in DELKA_KONCOVKY_PODLE_DELKY:
        if len(slovo) >= minimalni_delka:
            return slovo[: len(slovo) - koncovka] if koncovka else slovo
    return slovo


def _kmeny_odpovidaji(prvni: str, druhy: str) -> bool:
    if prvni == druhy:
        return True
    if abs(len(prvni) - len(druhy)) > MAXIMALNI_ROZDIL_KMENU:
        return False
    return prvni.startswith(druhy) or druhy.startswith(prvni)


def _slova(text: str) -> list[str]:
    normalizovany = odstran_diakritiku(text.replace("ß", "ss")).lower()
    return [s for s in re.findall(r"[a-z0-9]+", normalizovany) if s]


def _kmeny(text: str) -> list[str]:
    return [_kmen(s) for s in _slova(text)]


def _je_zakoncenim_slozeniny(kmen_textu: str, kmen_hledany: str) -> bool:
    if len(kmen_hledany) < MINIMALNI_DELKA_CASTI_SLOZENINY:
        return False
    pozice = kmen_textu.rfind(kmen_hledany)
    return pozice > 0 and (
        len(kmen_textu) - pozice - len(kmen_hledany) <= MAXIMALNI_KONCOVKA_SLOZENINY
    )


def _odpovida(kmen_textu: str, kmen_hledany: str, jazyk: str) -> bool:
    if _kmeny_odpovidaji(kmen_textu, kmen_hledany):
        return True
    return jazyk in JAZYKY_SE_SLOZENINAMI and _je_zakoncenim_slozeniny(
        kmen_textu, kmen_hledany
    )


def _shoda_v_poradi(okno: list[str], hledane: list[str], jazyk: str) -> bool:
    return all(_odpovida(a, b, jazyk) for a, b in zip(okno, hledane))


def _shoda_v_libovolnem_poradi(okno: list[str], hledane: list[str], jazyk: str) -> bool:
    volne = list(okno)
    for kmen in hledane:
        for index, kandidat in enumerate(volne):
            if _odpovida(kandidat, kmen, jazyk):
                del volne[index]
                break
        else:
            return False
    return True


def obsahuje_termin(
    text: str, termin: str, zachovat_poradi: bool = False, jazyk: str = ""
) -> bool:
    if obsahuje_cjk(termin):
        return bool(termin.strip()) and termin.strip() in text
    slova_terminu = _slova(termin)
    if not slova_terminu or all(s in NEVYZNAMOVA_SLOVA for s in slova_terminu):
        return False

    hledane = [_kmen(s) for s in slova_terminu]
    kmeny_textu = _kmeny(text)
    delka = len(hledane)
    shoda = _shoda_v_poradi if zachovat_poradi else _shoda_v_libovolnem_poradi
    return any(
        shoda(kmeny_textu[zacatek:zacatek + delka], hledane, jazyk)
        for zacatek in range(len(kmeny_textu) - delka + 1)
    )


def _normalizuj_slovo(slovo: str) -> str:
    return odstran_diakritiku(slovo.replace("ß", "ss")).lower()


def _delka_spolecneho_zacatku(prvni: str, druhy: str) -> int:
    delka = 0
    for a, b in zip(prvni, druhy):
        if a != b:
            break
        delka += 1
    return delka


def chybne_tvary(preklad: str, termin: str) -> list[tuple[str, str]]:
    if obsahuje_cjk(termin):
        return []
    slova_terminu = [
        s for s in re.findall(r"[^\W\d_]+", termin)
        if len(s) >= MINIMALNI_SPOLECNY_ZACATEK
    ]
    vzory = [_normalizuj_slovo(s) for s in slova_terminu]
    nalezene: list[tuple[str, str]] = []
    for slovo in dict.fromkeys(re.findall(r"[^\W\d_]+", preklad)):
        normalizovane = _normalizuj_slovo(slovo)
        kmen = _kmen(normalizovane)
        if any(_kmeny_odpovidaji(kmen, _kmen(vzor)) for vzor in vzory):
            continue
        for slovo_terminu, vzor in zip(slova_terminu, vzory):
            spolecny = _delka_spolecneho_zacatku(normalizovane, vzor)
            if (
                spolecny >= MINIMALNI_SPOLECNY_ZACATEK
                and spolecny >= MINIMALNI_PODIL_SPOLECNEHO_ZACATKU
                * min(len(normalizovane), len(vzor))
            ):
                nalezene.append((slovo, slovo_terminu))
                break
    return nalezene


def _vyskyt_s_velkym_pismenem(text: str, termin: str) -> bool:
    hledany = _kmen(_normalizuj_slovo(termin.strip()))
    return any(
        slovo[0].isupper() and _kmeny_odpovidaji(_kmen(_normalizuj_slovo(slovo)), hledany)
        for slovo in re.findall(r"[^\W\d_]+", text)
    )


def je_privlastkem(text: str, termin: str) -> bool:
    if len(_slova(termin)) != 1:
        return False
    hledany = _kmen(_slova(termin)[0])
    casti = re.findall(r"[a-z0-9]+|[^\sa-z0-9]", _normalizuj_slovo(text))
    for poradi, cast in enumerate(casti):
        if not cast.isalnum() or not _kmeny_odpovidaji(_kmen(cast), hledany):
            continue
        dalsi = poradi + 1
        if dalsi < len(casti) and casti[dalsi] in SPOJKY:
            dalsi += 2
        if (
            dalsi < len(casti)
            and casti[dalsi].isalpha()
            and casti[dalsi] not in NEVYZNAMOVA_SLOVA
        ):
            return True
    return False


@dataclass(frozen=True)
class KontrolaTerminu:
    termin_zdroj: str
    termin_cil: str
    ocekavan: bool
    dodrzen: bool
    nespravna_varianta: str = ""
    nespravna_varianta_pouzita: bool = False
    chybne_tvary: tuple[tuple[str, str], ...] = ()
    odvozeny_tvar: str = ""

    @property
    def je_problem(self) -> bool:
        return (self.ocekavan and not self.dodrzen) or self.nespravna_varianta_pouzita


@dataclass
class VysledekValidace:
    kontroly: list[KontrolaTerminu] = field(default_factory=list)
    chybejici_identifikatory: list[str] = field(default_factory=list)
    pocet_identifikatoru: int = 0
    varovani: list[str] = field(default_factory=list)

    @property
    def pocet_ocekavanych(self) -> int:
        return sum(1 for k in self.kontroly if k.ocekavan)

    @property
    def pocet_dodrzenych(self) -> int:
        return sum(1 for k in self.kontroly if k.ocekavan and k.dodrzen)

    @property
    def mira_dodrzeni_glosare(self) -> float:
        ocekavano = self.pocet_ocekavanych
        if ocekavano == 0:
            return 1.0
        return self.pocet_dodrzenych / ocekavano

    @property
    def pocet_nespravnych_variant(self) -> int:
        return sum(1 for k in self.kontroly if k.nespravna_varianta_pouzita)

    @property
    def identifikatory_zachovany(self) -> bool:
        return not self.chybejici_identifikatory

    @property
    def problemy(self) -> list[KontrolaTerminu]:
        return [k for k in self.kontroly if k.je_problem]

    @property
    def je_v_poradku(self) -> bool:
        return (
            self.mira_dodrzeni_glosare >= 1.0
            and self.pocet_nespravnych_variant == 0
            and self.identifikatory_zachovany
        )

    def souhrn(self) -> str:
        if self.je_v_poradku:
            return "Překlad splňuje všechny kontrolované podmínky."
        casti: list[str] = []
        if self.pocet_ocekavanych and self.pocet_dodrzenych < self.pocet_ocekavanych:
            casti.append(
                f"dodrženo {self.pocet_dodrzenych} z {self.pocet_ocekavanych} termínů glosáře"
            )
        if self.pocet_nespravnych_variant:
            casti.append(f"použito {self.pocet_nespravnych_variant} nesprávných variant")
        if self.chybejici_identifikatory:
            casti.append(
                f"v překladu chybí identifikátory: {', '.join(self.chybejici_identifikatory)}"
            )
        return "; ".join(casti)


def _identifikatory(text: str) -> set[str]:
    atributy = vytez_atributy(text)
    hodnoty: set[str] = set()
    hodnoty |= {f"DN{v}" for v in atributy.dn}
    hodnoty |= {f"PN{v}" for v in atributy.pn}
    hodnoty |= {f"IP{v}" for v in atributy.ip}
    hodnoty |= set(atributy.kody)
    hodnoty |= set(atributy.zavity)
    hodnoty |= set(atributy.rozmery)
    return hodnoty


def _vzor_identifikatoru(identifikator: str) -> re.Pattern[str]:
    casti: list[str] = []
    predchozi = ""
    for znak in identifikator:
        if predchozi and predchozi.isalpha() != znak.isalpha() and (
            predchozi.isdigit() or znak.isdigit()
        ):
            casti.append(r"\s?")
        if znak.lower() in "x×" and predchozi.isdigit():
            casti.append(r"\s?[x×]\s?")
        elif znak in ".,":
            casti.append("[.,]")
        else:
            casti.append(re.escape(znak))
        predchozi = znak
    zacatek = r"(?<![0-9])" if identifikator[:1].isdigit() else r"(?<![0-9a-z])"
    return re.compile(zacatek + "".join(casti) + r"(?![0-9])", re.IGNORECASE)


def identifikator_v_textu(identifikator: str, text: str) -> bool:
    return bool(identifikator) and _vzor_identifikatoru(identifikator).search(text) is not None


def zvaliduj_preklad(
    zdrojovy_text: str,
    preklad: str,
    nalezene_terminy: list[NalezenyTermin],
    zdrojovy_jazyk: str = "en",
    cilovy_jazyk: str = "cs",
) -> VysledekValidace:
    vysledek = VysledekValidace()

    for nalezeny in nalezene_terminy:
        polozka = nalezeny.polozka
        termin_zdroj = polozka.termin(zdrojovy_jazyk)
        termin_cil = polozka.termin(cilovy_jazyk)
        if not termin_zdroj or not termin_cil:
            continue

        ocekavan = obsahuje_termin(
            zdrojovy_text, termin_zdroj, zachovat_poradi=True, jazyk=zdrojovy_jazyk
        )
        if ocekavan and polozka.jen_s_velkym_pismenem:
            ocekavan = _vyskyt_s_velkym_pismenem(zdrojovy_text, termin_zdroj)
        dodrzen = (
            obsahuje_termin(preklad, termin_cil, jazyk=cilovy_jazyk) if ocekavan else False
        )

        tvary = chybne_tvary(preklad, termin_cil) if ocekavan and not dodrzen else []
        odvozeny = ""
        if tvary and len(_slova(termin_cil)) == 1 and (
            polozka.je_udrzbova_cinnost or je_privlastkem(zdrojovy_text, termin_zdroj)
        ):
            odvozeny, tvary, dodrzen = tvary[0][0], [], True

        nespravna = polozka.nespravne_v(cilovy_jazyk)
        nespravna_pouzita = bool(
            ocekavan and nespravna
            and obsahuje_termin(preklad, nespravna, jazyk=cilovy_jazyk)
        )

        vysledek.kontroly.append(KontrolaTerminu(
            termin_zdroj=termin_zdroj,
            termin_cil=termin_cil,
            ocekavan=ocekavan,
            dodrzen=dodrzen,
            nespravna_varianta=nespravna,
            nespravna_varianta_pouzita=nespravna_pouzita,
            chybne_tvary=tuple(tvary),
            odvozeny_tvar=odvozeny,
        ))

    ve_zdroji = _identifikatory(zdrojovy_text)
    chybejici = sorted(i for i in ve_zdroji if not identifikator_v_textu(i, preklad))
    vysledek.pocet_identifikatoru = len(ve_zdroji)
    vysledek.chybejici_identifikatory = chybejici
    if chybejici:
        vysledek.varovani.append(
            "Překlad nezachoval všechny technické identifikátory ze zdrojového textu."
        )

    if len(zdrojovy_text.strip()) >= MINIMALNI_DELKA_PRO_POMER and preklad.strip():
        pomer = len(preklad) / len(zdrojovy_text)
        if pomer < 0.4:
            vysledek.varovani.append(
                "Překlad je výrazně kratší než zdrojový text; mohla být vynechána část obsahu."
            )
        elif pomer > 2.5:
            vysledek.varovani.append(
                "Překlad je výrazně delší než zdrojový text; model mohl doplnit informace navíc."
            )

    return vysledek
