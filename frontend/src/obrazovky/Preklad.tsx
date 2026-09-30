import { useState } from "react";
import { api, type VysledekPrekladu } from "../api";
import {useNacti} from "../hooky";
import {
  Ikona,
  Panel,
  PrazdnyStav,
  ZahlaviObrazovky,
  formatujProcenta,
  useOznameni,
} from "../komponenty";

const UKAZKY = [
  "Replace the impeller and seal on the centrifugal pump.",
  "Tighten the nut on the mounting bolt to 45 Nm.",
  "Install check valve DN50 PN16 and replace the seal kit.",
  "Check the gate valve for internal leakage and inspect the shaft seal.",
];

export default function Preklad() {
  const { pridej, vykresli } = useOznameni();
  const stav = useNacti(() => api.system.stav(), []);

  const [text, nastavText] = useState(UKAZKY[0]);
  const [zdrojovy, nastavZdrojovy] = useState("en");
  const [cilovy, nastavCilovy] = useState("cs");
  const [model, nastavModel] = useState<string>("");
  const [temperature, nastavTemperature] = useState(0.1);
  const [srovnat, nastavSrovnat] = useState(true);

  const [sGlosarem, nastavSGlosarem] = useState<VysledekPrekladu | null>(null);
  const [bezGlosare, nastavBezGlosare] = useState<VysledekPrekladu | null>(null);
  const [pracuje, nastavPracuje] = useState(false);
  const [zobrazitPrompt, nastavZobrazitPrompt] = useState(false);

  const prohodJazyky = () => {
    nastavZdrojovy(cilovy);
    nastavCilovy(zdrojovy);
  };

  const prelozi = async () => {
    if (!text.trim()) return;
    nastavPracuje(true);
    nastavSGlosarem(null);
    nastavBezGlosare(null);

    const zaklad = {
      text,
      zdrojovy_jazyk: zdrojovy,
      cilovy_jazyk: cilovy,
      model: model || null,
      temperature
    };

    try {
      if (srovnat) {
        nastavBezGlosare(
          await api.preklad.prelozit({ ...zaklad, pouzit_glosar: false }),
        );
      }
      nastavSGlosarem(
        await api.preklad.prelozit({ ...zaklad, pouzit_glosar: true }),
      );
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Překlad se nezdařil.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  const ollamaNebezi = stav.data && !stav.data.ollama_dostupna;

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Překlad technických textů"
      />

      {ollamaNebezi && (
        <div className="panel mb-4 border-chyba/40 bg-chybaTlumena p-3.5 flex items-start gap-2.5">
          <span className="text-chyba mt-0.5">
            <Ikona.Vystraha velikost={17} />
          </span>
          <p className="text-sm text-text">
            Služba <span className="font-mono">Ollama</span> neběží, překlad proto
            není dostupný. Spusťte ji a obnovte stránku.
          </p>
        </div>
      )}

      <div className="grid xl:grid-cols-[minmax(0,25rem)_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel nadpis="Zdrojový text">
            <div className="space-y-3.5">
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="stitek-pole">Z jazyka</label>
                  <select
                    className="pole"
                    value={zdrojovy}
                    onChange={(e) => nastavZdrojovy(e.target.value)}
                  >
                    <option value="en">angličtina</option>
                    <option value="cs">čeština</option>
                  </select>
                </div>
                <button
                  className="tlacitko-vedlejsi px-2 mb-px"
                  onClick={prohodJazyky}
                  title="Prohodit jazyky"
                  aria-label="Prohodit jazyky"
                >
                  ⇄
                </button>
                <div className="flex-1">
                  <label className="stitek-pole">Do jazyka</label>
                  <select
                    className="pole"
                    value={cilovy}
                    onChange={(e) => nastavCilovy(e.target.value)}
                  >
                    <option value="cs">čeština</option>
                    <option value="en">angličtina</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="stitek-pole" htmlFor="zdrojovy-text">
                  Text k překladu
                </label>
                <textarea
                  id="zdrojovy-text"
                  className="pole min-h-[132px] resize-y leading-relaxed"
                  value={text}
                  onChange={(e) => nastavText(e.target.value)}
                  placeholder="Vložte technický text…"
                />
              </div>

              <details className="group">
                <summary className="cursor-pointer text-xs text-textTlumeny hover:text-text select-none">
                  Pokročilé nastavení
                </summary>
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="stitek-pole">Jazykový model</label>
                    <select
                      className="pole"
                      value={model}
                      onChange={(e) => nastavModel(e.target.value)}
                    >
                      <option value="">
                        výchozí ({stav.data?.aktivni_model ?? "—"})
                      </option>
                      {stav.data?.dostupne_modely.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="stitek-pole">
                      Temperature — {temperature.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      className="w-full accent-akcent"
                      min={0}
                      max={1}
                      step={0.05}
                      value={temperature}
                      onChange={(e) => nastavTemperature(Number(e.target.value))}
                    />
                    <p className="text-xs text-textSlaby mt-1">
                      Nízká hodnota omezuje kreativitu modelu a podporuje
                      předvídatelný výstup (kap. 2.6.3).
                    </p>
                  </div>
                </div>
              </details>

              <label className="flex items-center gap-2 text-sm text-textTlumeny cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-akcent"
                  checked={srovnat}
                  onChange={(e) => nastavSrovnat(e.target.checked)}
                />
                Přeložit i bez glosáře pro srovnání
              </label>

              <button
                className="tlacitko-hlavni w-full"
                onClick={() => void prelozi()}
                disabled={pracuje || !text.trim() || Boolean(ollamaNebezi)}
              >
                {pracuje ? "Překládám…" : "Přeložit"}
              </button>
            </div>
          </Panel>

          <Panel nadpis="Ukázkové věty">
            <div className="space-y-2">
              {UKAZKY.map((u) => (
                <button
                  key={u}
                  className="w-full text-left rounded-xs border border-obrys bg-plocha2 px-3 py-2 text-[0.8125rem] leading-snug text-textTlumeny transition-colors hover:border-akcent hover:bg-akcentTlumeny hover:text-akcent"
                  onClick={() => nastavText(u)}
                >
                  {u}
                </button>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          {pracuje && !sGlosarem && (
            <Panel>
              <div className="py-10 text-center">
                <div className="ukazatel h-2 max-w-sm mx-auto">
                  <div className="ukazatel-vypln prubeh-neurcity w-full" />
                </div>
                <p className="mt-3 text-sm text-textTlumeny">
                  {bezGlosare
                    ? "Překládám s glosářem…"
                    : srovnat
                      ? "Překládám bez glosáře…"
                      : "Překládám…"}
                </p>
                <p className="mt-1 text-xs text-textSlaby">
                  Model běží lokálně; první volání po spuštění bývá pomalejší.
                </p>
              </div>
            </Panel>
          )}

          {!pracuje && !sGlosarem && (
            <Panel>
              <PrazdnyStav
                nadpis="Zadejte text a spusťte překlad"
                popis="Výsledek se zobrazí spolu s termíny vyhledanými z glosáře a s kontrolou jejich dodržení."
              />
            </Panel>
          )}

          {(bezGlosare || sGlosarem) && (
            <div className={srovnat ? "grid lg:grid-cols-2 gap-4" : ""}>
              {srovnat && bezGlosare && (
                <VysledekPanelu
                  nadpis="Bez glosáře"
                  popis="Samotný jazykový model"
                  vysledek={bezGlosare}
                  barva="vystraha"
                />
              )}
              {sGlosarem && (
                <VysledekPanelu
                  nadpis="S glosářem (RAG)"
                  popis="Model s kontextem z firemního glosáře"
                  vysledek={sGlosarem}
                  barva="uspech"
                />
              )}
            </div>
          )}

          {sGlosarem && sGlosarem.nalezene_terminy.length > 0 && (
            <Panel
              nadpis="Termíny vyhledané z glosáře"
              popis={`${sGlosarem.nalezene_terminy.length} termínů předaných modelu jako závazný kontext`}
              bezOdsazeni
            >
              <div className="overflow-x-auto">
                <table className="tabulka">
                  <thead>
                    <tr>
                      <th>Termín ve zdroji</th>
                      <th>Závazný překlad</th>
                      <th>Nalezeno</th>
                      <th>Dodrženo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sGlosarem.nalezene_terminy.map((t) => {
                      const kontrola = sGlosarem.validace.kontroly.find(
                        (k) => k.termin_zdroj === t.termin_en,
                      );
                      return (
                        <tr key={t.id}>
                          <td>
                            <span className="text-text">{t.termin_en}</span>
                            {t.nespravne && (
                              <span className="block text-2xs text-chyba mt-0.5">
                                nepoužívat: {t.nespravne}
                              </span>
                            )}
                          </td>
                          <td className="text-text">{t.termin_cs}</td>
                          <td>
                            <span
                              className={
                                t.zpusob === "přímý výskyt"
                                  ? "odznak-akcent"
                                  : "odznak-neutralni"
                              }
                            >
                              {t.zpusob === "přímý výskyt" ? "v textu" : "významově"}
                            </span>
                          </td>
                          <td>
                            {!kontrola?.ocekavan ? (
                              <span className="text-textSlaby text-xs">
                                nevyžadováno
                              </span>
                            ) : kontrola.dodrzen ? (
                              <span className="text-uspech">
                                <Ikona.Fajfka velikost={15} />
                              </span>
                            ) : (
                              <span className="text-chyba">
                                <Ikona.Krizek velikost={15} />
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {sGlosarem && (
            <Panel
              nadpis="Prompt předaný modelu"
              popis="Systémová instrukce sestavená metodou RAG"
              akce={
                <button
                  className="tlacitko-tichy text-xs"
                  onClick={() => nastavZobrazitPrompt(!zobrazitPrompt)}
                >
                  {zobrazitPrompt ? "Skrýt" : "Zobrazit"}
                </button>
              }
            >
              {zobrazitPrompt ? (
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xs border border-obrys bg-plocha2 p-3.5 font-mono text-[0.7rem] leading-relaxed text-textTlumeny">
                  {sGlosarem.systemova_instrukce}
                </pre>
              ) : (
                <p className="text-sm text-textTlumeny">
                  Systémová instrukce a překládaný text jsou modelu předány jako
                  oddělené zprávy. Text je uzavřen do vymezeného bloku označeného
                  za data, nikoli za instrukce — tím je omezeno riziko vložení
                  cizího pokynu do vstupu (kap. 2.6.4).
                </p>
              )}
            </Panel>
          )}
        </div>
      </div>

      {vykresli}
    </>
  );
}

function VysledekPanelu({
  nadpis,
  popis,
  vysledek,
  barva,
}: {
  nadpis: string;
  popis: string;
  vysledek: VysledekPrekladu;
  barva: "uspech" | "vystraha";
}) {
  const v = vysledek.validace;
  const okraj = barva === "uspech" ? "border-l-uspech" : "border-l-vystraha";

  return (
    <section className={`panel border-l-[3px] ${okraj}`}>
      <header className="panel-hlavicka">
        <div>
          <h2 className="text-sm font-semibold text-text">{nadpis}</h2>
          <p className="text-xs text-textTlumeny mt-0.5">{popis}</p>
        </div>
        <span className="font-mono text-2xs text-textSlaby whitespace-nowrap">
          {vysledek.doba_generovani_s.toFixed(1)} s
        </span>
      </header>

      <div className="p-4 space-y-3.5">
        <p className="text-text leading-relaxed">{vysledek.preklad}</p>

        <div className="pt-3 border-t border-obrys space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="nadpis-sekce">Dodržení glosáře</span>
            <span className="font-mono text-sm tabular-nums text-text">
              {v.pocet_ocekavanych > 0
                ? `${formatujProcenta(v.mira_dodrzeni_glosare, 0)} (${v.pocet_dodrzenych}/${v.pocet_ocekavanych})`
                : "—"}
            </span>
          </div>
          {v.pocet_ocekavanych > 0 && (
            <div className="ukazatel h-2">
              <div
                className="ukazatel-vypln"
                style={{
                  width: `${v.mira_dodrzeni_glosare * 100}%`,
                  background:
                    v.mira_dodrzeni_glosare >= 1
                      ? "rgb(var(--barva-uspech))"
                      : v.mira_dodrzeni_glosare >= 0.6
                        ? "rgb(var(--barva-vystraha))"
                        : "rgb(var(--barva-chyba))",
                }}
              />
            </div>
          )}

          <div className="flex flex-wrap gap-1.5 pt-0.5">
            <span
              className={
                v.identifikatory_zachovany ? "odznak-uspech" : "odznak-chyba"
              }
              title="Čísla dílů, rozměry a jmenovité hodnoty musí zůstat beze změny."
            >
              {v.identifikatory_zachovany
                ? "identifikátory zachovány"
                : `ztraceno: ${v.chybejici_identifikatory.join(", ")}`}
            </span>
            {v.pocet_nespravnych_variant > 0 && (
              <span className="odznak-chyba">
                {v.pocet_nespravnych_variant}× zakázaná varianta
              </span>
            )}
          </div>

          {v.varovani.length > 0 && (
            <ul className="space-y-1 pt-1">
              {v.varovani.map((varovani, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-xs text-vystraha"
                >
                  <span className="mt-px shrink-0">
                    <Ikona.Info velikost={12} />
                  </span>
                  {varovani}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
