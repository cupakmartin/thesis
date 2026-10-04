import { useEffect, useRef, useState } from "react";
import { api, type Jazyk, type TerminGlosare } from "../api";
import { useJazyky, useNacti, useOdlozeno } from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Nacitani,
  Panel,
  PrazdnyStav,
  Strankovac,
  ZahlaviObrazovky,
  formatujCislo,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 25;
const MIN_JAZYKU = 2;

interface Formular {
  id?: string;
  terminy: Record<string, string>;
  nespravne: Record<string, string>;
  kategorie: string;
  definice: string;
  strojove: string[];
  overene: string[];
}

interface Doplnovani {
  celkem: number;
  hotovo: number;
  bezi: boolean;
}

const PRAZDNY: Formular = {
  terminy: {},
  nespravne: {},
  kategorie: "",
  definice: "",
  strojove: [],
  overene: [],
};

function velkym(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

function vyplnene(hodnoty: Record<string, string>): string[] {
  return Object.keys(hodnoty).filter((k) => hodnoty[k]?.trim());
}

export default function Glosar() {
  const { pridej, vykresli } = useOznameni();
  const jazyky = useJazyky();

  const [hledani, nastavHledani] = useState("");
  const [kategorie, nastavKategorii] = useState("");
  const [jenNeoverene, nastavJenNeoverene] = useState(false);
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [formular, nastavFormular] = useState<Formular | null>(null);
  const [uklada, nastavUklada] = useState(false);
  const [doplnovani, nastavDoplnovani] = useState<Doplnovani | null>(null);
  const ovladac = useRef<AbortController | null>(null);

  const hledaniOdlozene = useOdlozeno(hledani, 300);
  useEffect(() => nastavOdsazeni(0), [hledaniOdlozene, kategorie, jenNeoverene]);

  const kategorieSeznam = useNacti(() => api.glosar.kategorie(), []);
  const stav = useNacti(() => api.glosar.stav(), []);
  const seznam = useNacti(
    () =>
      api.glosar.seznam({
        hledany_text: hledaniOdlozene,
        kategorie,
        jen_strojove: jenNeoverene || undefined,
        limit: NA_STRANKU,
        odsazeni,
      }),
    [hledaniOdlozene, kategorie, jenNeoverene, odsazeni],
  );

  const obnovVse = () => {
    seznam.obnov();
    stav.obnov();
    kategorieSeznam.obnov();
  };

  const uloz = async () => {
    if (!formular) return;
    nastavUklada(true);
    try {
      const telo = {
        terminy: formular.terminy,
        kategorie: formular.kategorie,
        definice: formular.definice,
        nespravne: formular.nespravne,
        overene: formular.overene,
      };
      const ulozeny = formular.id
        ? await api.glosar.upravit(formular.id, telo)
        : await api.glosar.pridat(telo);
      const pocetDoplnenych = ulozeny.strojove.filter(
        (k) => !formular.strojove.includes(k),
      ).length;
      pridej(
        "uspech",
        `Termín ${ulozeny.id} uložen` +
          (pocetDoplnenych
            ? `; jazykový model doplnil ${pocetDoplnenych} jazyků.`
            : "."),
      );
      nastavFormular(null);
      obnovVse();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Termín se nepodařilo uložit.",
      );
    } finally {
      nastavUklada(false);
    }
  };

  const smaz = async (termin: TerminGlosare) => {
    const nazev = termin.terminy.cs || termin.terminy.en || termin.id;
    if (!window.confirm(`Opravdu odstranit termín „${nazev}“ z glosáře?`)) return;
    try {
      const odpoved = await api.glosar.smazat(termin.id);
      pridej("uspech", odpoved.zprava);
      obnovVse();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Termín se nepodařilo odstranit.",
      );
    }
  };

  const doplnJazyky = async () => {
    const ovl = new AbortController();
    ovladac.current = ovl;
    nastavDoplnovani({ celkem: stav.data?.k_doplneni ?? 0, hotovo: 0, bezi: true });
    try {
      await api.glosar.doplnitJazyky((udalost) => {
        if (udalost.typ === "plan") {
          nastavDoplnovani({ celkem: udalost.pocet, hotovo: 0, bezi: true });
        } else if (udalost.typ === "termin") {
          nastavDoplnovani((d) => (d ? { ...d, hotovo: udalost.poradi } : d));
        } else if (udalost.typ === "chyba") {
          pridej("chyba", udalost.zprava);
        } else {
          pridej("uspech", `Jazyky doplněny u ${udalost.pocet} termínů.`);
        }
      }, ovl.signal);
    } catch (duvod) {
      if (duvod instanceof DOMException && duvod.name === "AbortError") {
        pridej("informace", "Doplňování zastaveno; hotové termíny zůstávají uloženy.");
      } else {
        pridej(
          "chyba",
          duvod instanceof Error ? duvod.message : "Doplnění jazyků se nezdařilo.",
        );
      }
    } finally {
      ovladac.current = null;
      nastavDoplnovani(null);
      obnovVse();
    }
  };

  const otevri = (termin?: TerminGlosare) => {
    nastavFormular(
      termin
        ? {
            id: termin.id,
            terminy: { ...termin.terminy },
            nespravne: { ...termin.nespravne },
            kategorie: termin.kategorie,
            definice: termin.definice,
            strojove: [...termin.strojove],
            overene: [],
          }
        : { ...PRAZDNY, terminy: {}, nespravne: {} },
    );
  };

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Firemní glosář"
        akce={
          <button className="tlacitko-hlavni" onClick={() => otevri()}>
            Přidat termín
          </button>
        }
      />

      {(doplnovani || (stav.data && stav.data.k_doplneni > 0)) && (
        <div className="panel p-3.5 mb-4 flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[260px]">
            {doplnovani ? (
              <>
                <p className="text-sm text-text">
                  Doplňuji jazyky: {doplnovani.hotovo} z {doplnovani.celkem} termínů
                </p>
                <div className="ukazatel h-2 mt-2">
                  <div
                    className="ukazatel-vypln"
                    style={{
                      width: `${doplnovani.celkem ? (doplnovani.hotovo / doplnovani.celkem) * 100 : 2}%`,
                    }}
                  />
                </div>
              </>
            ) : (
              <p className="text-sm text-text">
                {formatujCislo(stav.data?.k_doplneni ?? 0)} termínů nemá všechny
                jazyky. Chybějící jazyky doplní jazykový model z vyplněných tvarů;
                doplněné překlady budou označeny jako neověřené.
              </p>
            )}
          </div>
          {doplnovani ? (
            <button
              className="tlacitko-vedlejsi"
              onClick={() => ovladac.current?.abort()}
            >
              Zastavit
            </button>
          ) : (
            <button className="tlacitko-hlavni" onClick={() => void doplnJazyky()}>
              Doplnit chybějící jazyky
            </button>
          )}
        </div>
      )}

      <Panel bezOdsazeni>
        <div className="flex flex-wrap items-end gap-2.5 p-3.5 border-b border-obrys">
          <div className="flex-1 min-w-[220px]">
            <label className="stitek-pole" htmlFor="hledani-glosar">
              Hledat
            </label>
            <input
              id="hledani-glosar"
              className="pole"
              placeholder="Termín v kterémkoli jazyce nebo text poznámky…"
              value={hledani}
              onChange={(e) => nastavHledani(e.target.value)}
            />
          </div>
          <div>
            <label className="stitek-pole" htmlFor="filtr-kategorie">
              Kategorie
            </label>
            <select
              id="filtr-kategorie"
              className="pole w-auto min-w-[12rem]"
              value={kategorie}
              onChange={(e) => nastavKategorii(e.target.value)}
            >
              <option value="">vše</option>
              {kategorieSeznam.data?.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-textTlumeny pb-2 cursor-pointer">
            <input
              type="checkbox"
              className="accent-akcent"
              checked={jenNeoverene}
              onChange={(e) => nastavJenNeoverene(e.target.checked)}
            />
            jen s neověřenými překlady
            {stav.data ? ` (${formatujCislo(stav.data.neovereno)})` : ""}
          </label>
          {seznam.data && (
            <p className="ml-auto text-sm text-textTlumeny pb-1.5">
              {formatujCislo(seznam.data.celkem)} termínů
            </p>
          )}
        </div>

        {seznam.nacita && !seznam.data ? (
          <Nacitani />
        ) : seznam.chyba ? (
          <ChybovyStav zprava={seznam.chyba} naObnoveni={seznam.obnov} />
        ) : seznam.data && seznam.data.celkem === 0 ? (
          <PrazdnyStav nadpis="Žádný termín neodpovídá zadání" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="tabulka">
                <thead>
                  <tr>
                    <th>Termín</th>
                    <th>Kategorie</th>
                    <th>Poznámka</th>
                    <th className="w-24" />
                  </tr>
                </thead>
                <tbody>
                  {seznam.data?.polozky.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <TerminVJazycich termin={t} jazyky={jazyky} />
                      </td>
                      <td>
                        <span className="odznak-neutralni">{t.kategorie}</span>
                      </td>
                      <td className="max-w-[36ch]">
                        {t.definice && (
                          <span className="block text-xs text-textTlumeny">
                            {t.definice}
                          </span>
                        )}
                        {Object.entries(t.nespravne).map(([kod, hodnota]) => (
                          <span key={kod} className="block text-xs text-chyba mt-0.5">
                            nepoužívat ({kod}): {hodnota}
                          </span>
                        ))}
                      </td>
                      <td>
                        <div className="flex justify-end gap-1">
                          <button
                            className="tlacitko-tichy px-1.5 py-1 text-xs"
                            onClick={() => otevri(t)}
                          >
                            Upravit
                          </button>
                          <button
                            className="tlacitko-tichy px-1.5 py-1 text-xs hover:text-chyba"
                            onClick={() => void smaz(t)}
                            aria-label={`Odstranit ${t.id}`}
                          >
                            <Ikona.Krizek velikost={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {seznam.data && (
              <Strankovac
                celkem={seznam.data.celkem}
                limit={NA_STRANKU}
                odsazeni={odsazeni}
                naZmenu={nastavOdsazeni}
              />
            )}
          </>
        )}
      </Panel>

      {formular && (
        <DialogTerminu
          formular={formular}
          jazyky={jazyky}
          kategorie={kategorieSeznam.data ?? []}
          uklada={uklada}
          naZmenu={nastavFormular}
          naUlozeni={() => void uloz()}
          naZavreni={() => nastavFormular(null)}
        />
      )}

      {vykresli}
    </>
  );
}

function TerminVJazycich({
  termin,
  jazyky,
}: {
  termin: TerminGlosare;
  jazyky: Jazyk[];
}) {
  const poradi = jazyky.length ? jazyky.map((j) => j.kod) : Object.keys(termin.terminy);
  return (
    <div className="flex flex-wrap gap-1">
      {poradi
        .filter((kod) => termin.terminy[kod])
        .map((kod) => {
          const strojove = termin.strojove.includes(kod);
          return (
            <span
              key={kod}
              className={`inline-flex items-baseline gap-1 rounded-xs border px-1.5 py-0.5 text-xs ${
                strojove
                  ? "border-dashed border-vystraha text-textTlumeny"
                  : "border-obrys text-text"
              }`}
              title={strojove ? "Strojově doplněno, neověřeno" : undefined}
            >
              <span className="font-mono text-2xs text-textSlaby uppercase">{kod}</span>
              {termin.terminy[kod]}
            </span>
          );
        })}
    </div>
  );
}

function DialogTerminu({
  formular,
  jazyky,
  kategorie,
  uklada,
  naZmenu,
  naUlozeni,
  naZavreni,
}: {
  formular: Formular;
  jazyky: Jazyk[];
  kategorie: string[];
  uklada: boolean;
  naZmenu: (formular: Formular) => void;
  naUlozeni: () => void;
  naZavreni: () => void;
}) {
  const pocetVyplnenych = vyplnene(formular.terminy).length;
  const chybiJazyky = pocetVyplnenych < MIN_JAZYKU;
  const chybiKategorie = !formular.kategorie.trim();
  const bezNespravnych = vyplnene(formular.nespravne).length === 0;
  const doplnitPocet = jazyky.length - pocetVyplnenych;

  const nastavTermin = (kod: string, hodnota: string) =>
    naZmenu({
      ...formular,
      terminy: { ...formular.terminy, [kod]: hodnota },
      overene: formular.overene.filter((k) => k !== kod),
    });

  const prepniOvereni = (kod: string, overeno: boolean) =>
    naZmenu({
      ...formular,
      overene: overeno
        ? [...formular.overene, kod]
        : formular.overene.filter((k) => k !== kod),
    });

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 animate-rozsvit"
        onClick={uklada ? undefined : naZavreni}
      />
      <div className="relative w-full max-w-2xl max-h-[92vh] overflow-y-auto panel shadow-vyzdvih animate-nastup">
        <header className="panel-hlavicka">
          <h2 className="text-sm font-semibold">
            {formular.id ? `Úprava termínu ${formular.id}` : "Nový termín"}
          </h2>
          <button
            className="tlacitko-tichy px-2"
            onClick={naZavreni}
            disabled={uklada}
            aria-label="Zavřít"
          >
            <Ikona.Krizek />
          </button>
        </header>

        <div className="p-4 space-y-4">
          <div>
            <div className="flex items-baseline justify-between gap-2 mb-1.5">
              <p className="stitek-pole mb-0">Termín *</p>
              <p className={`text-xs ${chybiJazyky ? "text-chyba" : "text-textTlumeny"}`}>
                vyplněno {pocetVyplnenych} z {jazyky.length} — alespoň {MIN_JAZYKU}
              </p>
            </div>
            <div className="grid sm:grid-cols-2 gap-x-3 gap-y-2.5">
              {jazyky.map((j, poradi) => {
                const strojove = formular.strojove.includes(j.kod);
                const overeno = strojove && formular.overene.includes(j.kod);
                return (
                  <div key={j.kod}>
                    <div className="flex items-center justify-between gap-2">
                      <label className="stitek-pole" htmlFor={`termin-${j.kod}`}>
                        {velkym(j.nazev)}
                      </label>
                      {strojove && formular.terminy[j.kod] && (
                        <label className="flex items-center gap-1 text-2xs text-vystraha cursor-pointer">
                          <input
                            type="checkbox"
                            className="accent-akcent"
                            checked={overeno}
                            onChange={(e) => prepniOvereni(j.kod, e.target.checked)}
                          />
                          ověřeno
                        </label>
                      )}
                    </div>
                    <input
                      id={`termin-${j.kod}`}
                      className={`pole ${strojove && !overeno ? "border-dashed border-vystraha" : ""}`}
                      value={formular.terminy[j.kod] ?? ""}
                      onChange={(e) => nastavTermin(j.kod, e.target.value)}
                      autoFocus={poradi === 0 && !formular.id}
                    />
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-textSlaby">
              {doplnitPocet > 0 && !chybiJazyky
                ? `Zbývajících ${doplnitPocet} jazyků doplní po uložení jazykový model; překlady budou označeny jako neověřené.`
                : "Nevyplněné jazyky doplní po uložení jazykový model z vyplněných tvarů."}{" "}
              Úprava strojově doplněného překladu jej označí za ověřený.
            </p>
          </div>

          <div>
            <label className="stitek-pole" htmlFor="termin-kategorie">
              Kategorie *
            </label>
            <input
              id="termin-kategorie"
              className="pole"
              list="seznam-kategorii"
              placeholder="vyberte nebo napište novou"
              value={formular.kategorie}
              onChange={(e) => naZmenu({ ...formular, kategorie: e.target.value })}
            />
            <datalist id="seznam-kategorii">
              {kategorie.map((k) => (
                <option key={k} value={k} />
              ))}
            </datalist>
            <p className="mt-1 text-xs text-textSlaby">
              {formular.kategorie.trim() && !kategorie.includes(formular.kategorie.trim())
                ? "Nová kategorie se uloží a bude nabízena i u dalších termínů."
                : "Kategorie označující komponentu se používá i k rozlišení druhu dílu při deduplikaci."}
            </p>
          </div>

          <div>
            <label className="stitek-pole" htmlFor="termin-poznamka">
              Poznámka
            </label>
            <textarea
              id="termin-poznamka"
              className="pole min-h-[64px] resize-y"
              placeholder="například: protikus šroubu se závitem, nikoli plod"
              value={formular.definice}
              onChange={(e) => naZmenu({ ...formular, definice: e.target.value })}
            />
            <p className="mt-1 text-xs text-textSlaby">
              Nepovinná. Předává se modelu jako vodítko k významu termínu.
            </p>
          </div>

          <details open={!bezNespravnych || !formular.id}>
            <summary className="cursor-pointer stitek-pole select-none">
              Nesprávné překlady
            </summary>
            <div className="mt-2 grid sm:grid-cols-2 gap-x-3 gap-y-2">
              {jazyky.map((j) => (
                <div key={j.kod}>
                  <label className="text-2xs text-textSlaby" htmlFor={`nespravne-${j.kod}`}>
                    {velkym(j.nazev)}
                  </label>
                  <input
                    id={`nespravne-${j.kod}`}
                    className="pole"
                    value={formular.nespravne[j.kod] ?? ""}
                    onChange={(e) =>
                      naZmenu({
                        ...formular,
                        nespravne: { ...formular.nespravne, [j.kod]: e.target.value },
                      })
                    }
                  />
                </div>
              ))}
            </div>
          </details>
          {bezNespravnych && (
            <p className="flex items-start gap-1.5 text-xs text-vystraha">
              <span className="mt-px shrink-0">
                <Ikona.Info velikost={12} />
              </span>
              Doporučujeme uvést alespoň jeden nesprávný překlad, například
              „ořech“ u termínu „nut“. Model se mu pak výslovně vyhne a kontrola
              kvality jej v překladu odhalí.
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 px-4 py-3 border-t border-obrys">
          {uklada && (
            <span className="mr-auto text-xs text-textTlumeny">
              Ukládám a doplňuji jazyky…
            </span>
          )}
          <button className="tlacitko-vedlejsi" onClick={naZavreni} disabled={uklada}>
            Zrušit
          </button>
          <button
            className="tlacitko-hlavni"
            onClick={naUlozeni}
            disabled={uklada || chybiJazyky || chybiKategorie}
            title={
              chybiJazyky
                ? "Vyplňte termín alespoň ve dvou jazycích."
                : chybiKategorie
                  ? "Vyberte nebo zadejte kategorii."
                  : undefined
            }
          >
            {uklada ? "Ukládám…" : "Uložit"}
          </button>
        </footer>
      </div>
    </div>
  );
}
