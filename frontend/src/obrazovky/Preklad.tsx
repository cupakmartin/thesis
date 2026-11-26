import { useRef, useState } from "react";
import {
  api,
  type HotovyDokument,
  type UdalostDokumentu,
  type UsekDokumentu,
  type VysledekPrekladu,
} from "../api";
import { useJazyky, useNacti, useOdhadZbyvajiciDoby } from "../hooky";
import {
  Ikona,
  Panel,
  PrazdnyStav,
  VolbaJazyka,
  ZahlaviObrazovky,
  formatujProcenta,
  textZbyvajiciDoby,
  useOznameni,
} from "../komponenty";

const MAX_ZNAKU_JEDNOHO = 1000;
const MAX_ZNAKU_DOKUMENTU = 100_000;

interface StavDokumentu {
  celkem: number;
  useky: UsekDokumentu[];
  hotovo: HotovyDokument | null;
  chyba: string | null;
}

interface InfoPdf {
  nazev: string;
  pocet_stran: number;
  pocet_znaku: number;
}

function aktualizujDokument(
  stav: StavDokumentu | null,
  udalost: UdalostDokumentu,
): StavDokumentu {
  const d = stav ?? { celkem: 0, useky: [], hotovo: null, chyba: null };
  if (udalost.typ === "plan") return { ...d, celkem: udalost.pocet_useku };
  if (udalost.typ === "usek") return { ...d, useky: [...d.useky, udalost] };
  if (udalost.typ === "hotovo") return { ...d, hotovo: udalost };
  return { ...d, chyba: udalost.zprava };
}

function popisZpusobu(zpusob: string): string {
  if (zpusob === "glosář") return "z glosáře";
  if (zpusob === "krátký výraz") return "krátký výraz";
  return "věta";
}

function stahniText(text: string, nazev: string) {
  const odkaz = document.createElement("a");
  odkaz.href = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  odkaz.download = nazev;
  odkaz.click();
  setTimeout(() => URL.revokeObjectURL(odkaz.href), 1000);
}

export default function Preklad() {
  const { pridej, vykresli } = useOznameni();
  const stav = useNacti(() => api.system.stav(), []);
  const jazyky = useJazyky();

  const [text, nastavText] = useState("");
  const [zdrojovy, nastavZdrojovy] = useState("en");
  const [cilovy, nastavCilovy] = useState("cs");
  const [model, nastavModel] = useState<string>("");
  const [temperature, nastavTemperature] = useState(0.1);
  const [srovnat, nastavSrovnat] = useState(true);

  const [sGlosarem, nastavSGlosarem] = useState<VysledekPrekladu | null>(null);
  const [bezGlosare, nastavBezGlosare] = useState<VysledekPrekladu | null>(null);
  const [dokument, nastavDokument] = useState<StavDokumentu | null>(null);
  const [pracuje, nastavPracuje] = useState(false);
  const [zobrazitPrompt, nastavZobrazitPrompt] = useState(false);

  const [infoPdf, nastavInfoPdf] = useState<InfoPdf | null>(null);
  const [nacitaPdf, nastavNacitaPdf] = useState(false);
  const vyberSouboru = useRef<HTMLInputElement>(null);
  const ovladac = useRef<AbortController | null>(null);

  const pocetRadku = text.split("\n").filter((r) => r.trim()).length;
  const jeDokument = pocetRadku > 1 || text.length > MAX_ZNAKU_JEDNOHO;
  const prilisDlouhy = text.length > MAX_ZNAKU_DOKUMENTU;

  const vycistiVysledky = () => {
    nastavSGlosarem(null);
    nastavBezGlosare(null);
    nastavDokument(null);
  };

  const prohodJazyky = () => {
    nastavZdrojovy(cilovy);
    nastavCilovy(zdrojovy);
  };

  const preloziJeden = async () => {
    const zaklad = {
      text,
      zdrojovy_jazyk: zdrojovy,
      cilovy_jazyk: cilovy,
      model: model || null,
      temperature,
    };
    if (srovnat) {
      nastavBezGlosare(
        await api.preklad.prelozit({ ...zaklad, pouzit_glosar: false }),
      );
    }
    nastavSGlosarem(
      await api.preklad.prelozit({ ...zaklad, pouzit_glosar: true }),
    );
  };

  const preloziDokument = async () => {
    const ovl = new AbortController();
    ovladac.current = ovl;
    nastavDokument({ celkem: 0, useky: [], hotovo: null, chyba: null });
    try {
      await api.preklad.dokument(
        {
          text,
          zdrojovy_jazyk: zdrojovy,
          cilovy_jazyk: cilovy,
          pouzit_glosar: true,
          model: model || null,
        },
        (udalost) => {
          if (udalost.typ === "chyba") pridej("chyba", udalost.zprava);
          nastavDokument((d) => aktualizujDokument(d, udalost));
        },
        ovl.signal,
      );
    } finally {
      ovladac.current = null;
    }
  };

  const prelozi = async () => {
    if (!text.trim() || prilisDlouhy) return;
    nastavPracuje(true);
    vycistiVysledky();
    try {
      if (jeDokument) await preloziDokument();
      else await preloziJeden();
    } catch (duvod) {
      if (duvod instanceof DOMException && duvod.name === "AbortError") {
        pridej("informace", "Překlad byl zastaven.");
      } else {
        pridej(
          "chyba",
          duvod instanceof Error ? duvod.message : "Překlad se nezdařil.",
        );
      }
    } finally {
      nastavPracuje(false);
    }
  };

  const nahrajPdf = async (soubor: File) => {
    nastavNacitaPdf(true);
    try {
      const vysledek = await api.preklad.pdf(soubor);
      nastavText(vysledek.text);
      nastavInfoPdf({
        nazev: soubor.name,
        pocet_stran: vysledek.pocet_stran,
        pocet_znaku: vysledek.pocet_znaku,
      });
      vycistiVysledky();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "PDF se nepodařilo načíst.",
      );
    } finally {
      nastavNacitaPdf(false);
      if (vyberSouboru.current) vyberSouboru.current.value = "";
    }
  };

  const kopiruj = (obsah: string) => {
    navigator.clipboard
      .writeText(obsah)
      .then(() => pridej("uspech", "Překlad zkopírován do schránky."))
      .catch(() => pridej("chyba", "Kopírování se nezdařilo."));
  };

  const ollamaNebezi = stav.data && !stav.data.ollama_dostupna;
  const nazevSouboru = infoPdf
    ? `${infoPdf.nazev.replace(/\.pdf$/i, "")}_preklad.txt`
    : "preklad.txt";

  return (
    <>
      <ZahlaviObrazovky nadpis="Překlad technických textů" />

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
                <VolbaJazyka
                  id="preklad-zdroj"
                  popisek="Z jazyka"
                  hodnota={zdrojovy}
                  jazyky={jazyky}
                  naZmenu={nastavZdrojovy}
                />
                <button
                  className="tlacitko-vedlejsi px-2 mb-px"
                  onClick={prohodJazyky}
                  title="Prohodit jazyky"
                  aria-label="Prohodit jazyky"
                >
                  ⇄
                </button>
                <VolbaJazyka
                  id="preklad-cil"
                  popisek="Do jazyka"
                  hodnota={cilovy}
                  jazyky={jazyky}
                  naZmenu={nastavCilovy}
                />
              </div>

              <div>
                <div className="flex items-end justify-between gap-2">
                  <label className="stitek-pole" htmlFor="zdrojovy-text">
                    Text k překladu
                  </label>
                  <button
                    className="tlacitko-tichy text-xs mb-1"
                    onClick={() => vyberSouboru.current?.click()}
                    disabled={nacitaPdf || pracuje}
                    title="Text se z PDF vytěží a vloží do pole, kde jej lze před překladem upravit."
                  >
                    {nacitaPdf ? "Načítám PDF…" : "Nahrát PDF…"}
                  </button>
                  <input
                    ref={vyberSouboru}
                    type="file"
                    accept="application/pdf,.pdf"
                    className="hidden"
                    onChange={(e) => {
                      const soubor = e.target.files?.[0];
                      if (soubor) void nahrajPdf(soubor);
                    }}
                  />
                </div>
                <textarea
                  id="zdrojovy-text"
                  className={`pole resize-y leading-relaxed ${jeDokument ? "min-h-[260px]" : "min-h-[132px]"}`}
                  value={text}
                  onChange={(e) => nastavText(e.target.value)}
                  placeholder="Vložte technický text nebo nahrajte PDF…"
                />
                {infoPdf && (
                  <p className="text-xs text-textTlumeny mt-1">
                    Načteno z „{infoPdf.nazev}“: {infoPdf.pocet_stran}{" "}
                    {infoPdf.pocet_stran === 1 ? "strana" : infoPdf.pocet_stran < 5 ? "strany" : "stran"},{" "}
                    {infoPdf.pocet_znaku.toLocaleString("cs-CZ")} znaků. Text můžete
                    před překladem upravit.
                  </p>
                )}
                {jeDokument && !prilisDlouhy && (
                  <p className="text-xs text-textTlumeny mt-1">
                    Text bude přeložen jako dokument - po odstavcích, nadpisech
                    a položkách seznamu, se zachováním struktury.
                  </p>
                )}
                {prilisDlouhy && (
                  <p className="text-xs text-chyba mt-1">
                    Text má {text.length.toLocaleString("cs-CZ")} znaků; najednou lze
                    přeložit nejvýše {MAX_ZNAKU_DOKUMENTU.toLocaleString("cs-CZ")}.
                    Rozdělte jej na menší části.
                  </p>
                )}
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
                        výchozí ({stav.data?.aktivni_model ?? "-"})
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
                      Temperature - {temperature.toFixed(2)}
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

              <label
                className={`flex items-center gap-2 text-sm cursor-pointer ${jeDokument ? "text-textSlaby" : "text-textTlumeny"}`}
                title={jeDokument ? "U dokumentu se srovnání neprovádí - zdvojnásobilo by dobu překladu." : undefined}
              >
                <input
                  type="checkbox"
                  className="accent-akcent"
                  checked={srovnat && !jeDokument}
                  disabled={jeDokument}
                  onChange={(e) => nastavSrovnat(e.target.checked)}
                />
                Přeložit i bez glosáře pro srovnání
              </label>

              {pracuje && jeDokument ? (
                <button
                  className="tlacitko-vedlejsi w-full"
                  onClick={() => ovladac.current?.abort()}
                >
                  Zastavit překlad
                </button>
              ) : (
                <button
                  className="tlacitko-hlavni w-full"
                  onClick={() => void prelozi()}
                  disabled={
                    pracuje || !text.trim() || prilisDlouhy || Boolean(ollamaNebezi)
                  }
                >
                  {pracuje
                    ? "Překládám…"
                    : jeDokument
                      ? "Přeložit dokument"
                      : "Přeložit"}
                </button>
              )}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          {dokument ? (
            <PrekladDokumentu
              stav={dokument}
              pracuje={pracuje}
              naKopirovani={kopiruj}
              naStazeni={(obsah) => stahniText(obsah, nazevSouboru)}
            />
          ) : (
            <>
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
                    popis="Přeložit lze slovo, větu, delší text i obsah PDF. Výsledek se zobrazí spolu s termíny vyhledanými z glosáře a s kontrolou jejich dodržení."
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
                <TerminyGlosare vysledek={sGlosarem} />
              )}

              {sGlosarem && (
                <Panel
                  nadpis="Prompt předaný modelu"
                  popis="Systémová instrukce sestavená metodou RAG"
                  akce={
                    sGlosarem.zpusob !== "glosář" && (
                      <button
                        className="tlacitko-tichy text-xs"
                        onClick={() => nastavZobrazitPrompt(!zobrazitPrompt)}
                      >
                        {zobrazitPrompt ? "Skrýt" : "Zobrazit"}
                      </button>
                    )
                  }
                >
                  {sGlosarem.zpusob === "glosář" ? (
                    <p className="text-sm text-textTlumeny">
                      Vstup je přesně termínem firemního glosáře, překlad je proto
                      převzat přímo z glosáře. Jazykový model nebyl volán a prompt
                      se nesestavoval.
                    </p>
                  ) : zobrazitPrompt ? (
                    <div className="space-y-3">
                      <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xs border border-obrys bg-plocha2 p-3.5 font-mono text-[0.7rem] leading-relaxed text-textTlumeny">
                        {sGlosarem.systemova_instrukce}
                      </pre>
                      {sGlosarem.oprava && (
                        <div>
                          <p className="stitek-pole">
                            Instrukce 2. pokusu (oprava podle kontroly)
                          </p>
                          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xs border border-obrys bg-plocha2 p-3.5 font-mono text-[0.7rem] leading-relaxed text-textTlumeny">
                            {sGlosarem.oprava.systemova_instrukce.slice(
                              sGlosarem.systemova_instrukce.length,
                            ).trim()}
                          </pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-textTlumeny">
                      Systémová instrukce a překládaný text jsou modelu předány jako
                      oddělené zprávy. Text je uzavřen do vymezeného bloku označeného
                      za data, nikoli za instrukce - tím je omezeno riziko vložení
                      cizího pokynu do vstupu (kap. 2.6.4).
                      {sGlosarem.zpusob === "krátký výraz" &&
                        " Krátký vstup dostává stručnou instrukci bez příkladů, aby je model nezopakoval místo překladu."}
                    </p>
                  )}
                </Panel>
              )}
            </>
          )}
        </div>
      </div>

      {vykresli}
    </>
  );
}

function popisChybnychTvaru(tvary: [string, string][]): string {
  if (tvary.length === 0) return "";
  return ` - v překladu ${tvary.map(([chybne, spravne]) => `„${chybne}“ místo tvaru od „${spravne}“`).join(", ")}`;
}

function maProblem(u: UsekDokumentu): boolean {
  return (
    u.problemy.length > 0 ||
    u.chybejici_identifikatory.length > 0 ||
    u.varovani.length > 0
  );
}

function PrekladDokumentu({
  stav,
  pracuje,
  naKopirovani,
  naStazeni,
}: {
  stav: StavDokumentu;
  pracuje: boolean;
  naKopirovani: (obsah: string) => void;
  naStazeni: (obsah: string) => void;
}) {
  const [vsechnyUseky, nastavVsechnyUseky] = useState(false);
  const hotovo = stav.hotovo;
  const prelozeno = stav.useky.length;
  const podil = stav.celkem ? prelozeno / stav.celkem : 0;
  const odhad = useOdhadZbyvajiciDoby(prelozeno, stav.celkem, pracuje && !hotovo);
  const zGlosare = stav.useky.filter((u) => u.zpusob === "glosář").length;
  const problemove = stav.useky.filter(maProblem);
  const zobrazene = vsechnyUseky ? stav.useky : problemove;
  const nahled = hotovo
    ? hotovo.preklad
    : stav.useky.map((u) => u.odrazka + u.preklad).join("\n");

  return (
    <>
      <Panel
        nadpis="Překlad dokumentu"
        popis={
          hotovo
            ? `${hotovo.pocet_useku} úseků · ${hotovo.doba_s.toFixed(1)} s · model ${hotovo.model}`
            : pracuje
              ? `Přeloženo ${prelozeno} z ${stav.celkem || "…"} úseků · ${textZbyvajiciDoby(odhad.zbyva_s)}`
              : `Přerušeno po ${prelozeno} z ${stav.celkem} úseků`
        }
        akce={
          nahled && (
            <div className="flex gap-2">
              <button
                className="tlacitko-vedlejsi text-xs"
                onClick={() => naKopirovani(nahled)}
              >
                Kopírovat
              </button>
              <button
                className="tlacitko-vedlejsi text-xs"
                onClick={() => naStazeni(nahled)}
              >
                Stáhnout .txt
              </button>
            </div>
          )
        }
      >
        {!hotovo && (
          <div className="ukazatel h-2 mb-3">
            <div
              className="ukazatel-vypln"
              style={{ width: `${Math.max(podil * 100, pracuje ? 2 : 0)}%` }}
            />
          </div>
        )}
        {hotovo && (
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span
              className={
                hotovo.mira_dodrzeni_glosare >= 1 ? "odznak-uspech" : "odznak-chyba"
              }
              title="Kolikrát byl termín glosáře, který se vyskytl ve zdrojovém úseku, správně použit i v překladu. Nedodržené výskyty jsou vypsány v tabulce úseků."
            >
              glosář{" "}
              {hotovo.pocet_ocekavanych > 0
                ? `dodržen ${hotovo.pocet_dodrzenych} z ${hotovo.pocet_ocekavanych} (${formatujProcenta(hotovo.mira_dodrzeni_glosare, 0)})`
                : "- žádný termín v textu"}
            </span>
            {hotovo.pocet_nespravnych_variant > 0 && (
              <span className="odznak-chyba">
                {hotovo.pocet_nespravnych_variant}× zakázaná varianta
              </span>
            )}
            {hotovo.pocet_identifikatoru > 0 && (
              <span
                className={
                  hotovo.identifikatory_zachovany ? "odznak-uspech" : "odznak-chyba"
                }
                title="Čísla dílů, rozměry, závity a jmenovité hodnoty (např. DN50, M20x1.5, 6204) musí v překladu zůstat beze změny."
              >
                {hotovo.identifikatory_zachovany
                  ? `identifikátory zachovány (${hotovo.pocet_identifikatoru})`
                  : `v překladu chybí: ${hotovo.chybejici_identifikatory.join(", ")}`}
              </span>
            )}
            {hotovo.pocet_opravenych > 0 && (
              <span
                className="odznak-neutralni"
                title="Úseky, v nichž kontrola zjistila nedodržený termín a model je přeložil podruhé s upozorněním na chybu."
              >
                {hotovo.pocet_opravenych}× opraveno 2. pokusem
              </span>
            )}
            {zGlosare > 0 && (
              <span
                className="odznak-neutralni"
                title="Úseky, které byly přesně termínem glosáře, se přeložily bez jazykového modelu."
              >
                {zGlosare}× přímo z glosáře
              </span>
            )}
          </div>
        )}
        {nahled ? (
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap font-sans text-sm text-text leading-relaxed">
            {nahled}
          </pre>
        ) : (
          <p className="text-sm text-textTlumeny">
            Text se dělí na úseky; první úsek se překládá…
          </p>
        )}
      </Panel>

      {stav.useky.length > 0 && (
        <Panel
          nadpis={vsechnyUseky ? "Všechny úseky" : "Úseky s nálezem kontroly"}
          popis={
            vsechnyUseky
              ? "Každý odstavec, nadpis a položka seznamu se překládá samostatně; odstavec se nedělí na věty, aby nepřišel o kontext."
              : `Úseky, v nichž kontrola našla nedodržený termín, zakázanou variantu, chybějící identifikátor nebo nepoměr délky - ${problemove.length} z ${prelozeno}.`
          }
          akce={
            <button
              className="tlacitko-tichy text-xs"
              onClick={() => nastavVsechnyUseky(!vsechnyUseky)}
            >
              {vsechnyUseky ? "Jen úseky s nálezem" : "Zobrazit všechny úseky"}
            </button>
          }
          bezOdsazeni
        >
          {zobrazene.length === 0 ? (
            <p className="p-4 text-sm text-textTlumeny">
              {pracuje
                ? "Zatím bez nálezu."
                : "Kontrola v žádném úseku nic nenašla: termíny glosáře jsou dodrženy a identifikátory zachovány."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="tabulka">
                <thead>
                  <tr>
                    <th className="w-8">#</th>
                    <th>Zdroj</th>
                    <th>Překlad</th>
                    <th>Nález kontroly</th>
                    <th>Způsob</th>
                  </tr>
                </thead>
                <tbody>
                  {zobrazene.map((u) => (
                    <tr key={u.poradi}>
                      <td className="font-mono text-2xs text-textSlaby">{u.poradi}</td>
                      <td className="text-textTlumeny">{u.zdroj}</td>
                      <td className="text-text">
                        {u.preklad}
                        {u.prvni_pokus && (
                          <span className="block text-2xs text-textSlaby mt-1">
                            1. pokus:{" "}
                            <span className="line-through">{u.prvni_pokus}</span>
                          </span>
                        )}
                      </td>
                      <td className="min-w-[14rem]">
                        <NalezyUseku usek={u} />
                      </td>
                      <td>
                        <span
                          className={
                            u.zpusob === "glosář" ? "odznak-uspech" : "odznak-neutralni"
                          }
                        >
                          {popisZpusobu(u.zpusob)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

function NalezyUseku({ usek }: { usek: UsekDokumentu }) {
  if (!maProblem(usek)) {
    return <span className="text-xs text-textSlaby">bez nálezu</span>;
  }
  return (
    <ul className="space-y-1 text-xs">
      {usek.problemy.map((p, i) => (
        <li key={i} className="text-chyba">
          {p.nespravna_varianta
            ? `zakázaná varianta „${p.nespravna_varianta}“ - správně „${p.termin_cil}“`
            : `nepoužit termín: ${p.termin_zdroj} → „${p.termin_cil}“${popisChybnychTvaru(p.chybne_tvary)}`}
        </li>
      ))}
      {usek.chybejici_identifikatory.length > 0 && (
        <li className="text-chyba">
          v překladu chybí: {usek.chybejici_identifikatory.join(", ")}
        </li>
      )}
      {usek.varovani.map((v, i) => (
        <li key={`v${i}`} className="text-vystraha">
          {v}
        </li>
      ))}
    </ul>
  );
}

function TerminyGlosare({ vysledek }: { vysledek: VysledekPrekladu }) {
  return (
    <Panel
      nadpis="Termíny vyhledané z glosáře"
      popis={
        vysledek.zpusob === "glosář"
          ? "Vstup je přesně tímto termínem glosáře"
          : `${vysledek.nalezene_terminy.length} termínů předaných modelu jako závazný kontext`
      }
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
            {vysledek.nalezene_terminy.map((t) => {
              const kontrola = vysledek.validace.kontroly.find(
                (k) => k.termin_zdroj === t.termin_zdroj,
              );
              return (
                <tr key={t.id}>
                  <td>
                    <span className="text-text">{t.termin_zdroj}</span>
                    {t.nespravne && (
                      <span className="block text-2xs text-chyba mt-0.5">
                        nepoužívat: {t.nespravne}
                      </span>
                    )}
                  </td>
                  <td className="text-text">
                    {t.termin_cil}
                    {t.cil_neoveren && (
                      <span
                        className="odznak-vystraha ml-1.5"
                        title="Překlad termínu doplnil jazykový model a zatím jej nikdo neověřil."
                      >
                        neověřeno
                      </span>
                    )}
                  </td>
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
                      <span
                        className="text-textSlaby text-xs"
                        title="Termín se ve zdrojovém textu v tomto znění nevyskytuje; model jej dostal jen jako významově blízký kontext."
                      >
                        nevyžadováno
                      </span>
                    ) : kontrola.nespravna_varianta_pouzita ? (
                      <span className="text-chyba text-xs">zakázaná varianta</span>
                    ) : kontrola.dodrzen ? (
                      <span
                        className="text-uspech"
                        title={
                          kontrola.odvozeny_tvar
                            ? `Termín ve zdroji rozvíjí další slovo, překlad jej proto vyjadřuje odvozeným tvarem „${kontrola.odvozeny_tvar}“.`
                            : undefined
                        }
                      >
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
  const zGlosare = vysledek.zpusob === "glosář";

  return (
    <section className={`panel border-l-[3px] ${okraj}`}>
      <header className="panel-hlavicka">
        <div>
          <h2 className="text-sm font-semibold text-text">{nadpis}</h2>
          <p className="text-xs text-textTlumeny mt-0.5">{popis}</p>
        </div>
        <span
          className="font-mono text-2xs text-textSlaby whitespace-nowrap"
          title={
            zGlosare
              ? "Vstup je přesně termínem glosáře; překlad byl převzat z glosáře a jazykový model se nevolal."
              : "Doba generování jazykovým modelem"
          }
        >
          {zGlosare
            ? `${vysledek.doba_s.toFixed(2)} s · model nevolán`
            : `${vysledek.doba_generovani_s.toFixed(1)} s`}
        </span>
      </header>

      <div className="p-4 space-y-3.5">
        <p className="text-text leading-relaxed whitespace-pre-wrap">
          {vysledek.preklad}
        </p>

        <div className="pt-3 border-t border-obrys space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="nadpis-sekce">Dodržení glosáře</span>
            <span className="font-mono text-sm tabular-nums text-text">
              {v.pocet_ocekavanych > 0
                ? `${formatujProcenta(v.mira_dodrzeni_glosare, 0)} (${v.pocet_dodrzenych}/${v.pocet_ocekavanych})`
                : "-"}
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
            {zGlosare && (
              <span
                className="odznak-uspech"
                title="Vstup je přesně termínem firemního glosáře; jazykový model nebyl volán."
              >
                přímo z glosáře
              </span>
            )}
            {vysledek.zpusob === "krátký výraz" && (
              <span
                className="odznak-neutralni"
                title="Slovo nebo krátký popisek se překládá stručnou instrukcí; větná pravidla by z něj udělala větu."
              >
                krátký výraz
              </span>
            )}
            {v.pocet_identifikatoru > 0 && (
              <span
                className={
                  v.identifikatory_zachovany ? "odznak-uspech" : "odznak-chyba"
                }
                title="Čísla dílů, rozměry, závity a jmenovité hodnoty (např. DN50, M20x1.5, 6204) musí v překladu zůstat beze změny."
              >
                {v.identifikatory_zachovany
                  ? `identifikátory zachovány (${v.pocet_identifikatoru})`
                  : `v překladu chybí: ${v.chybejici_identifikatory.join(", ")}`}
              </span>
            )}
            {v.pocet_nespravnych_variant > 0 && (
              <span className="odznak-chyba">
                {v.pocet_nespravnych_variant}× zakázaná varianta
              </span>
            )}
            {vysledek.oprava?.prijata && (
              <span
                className="odznak-neutralni"
                title="Kontrola v prvním pokusu našla nedodržený termín; model text přeložil znovu s upozorněním na chybu."
              >
                opraveno 2. pokusem
              </span>
            )}
          </div>

          {(v.kontroly.some((k) => (k.ocekavan && !k.dodrzen) || k.nespravna_varianta_pouzita) ||
            vysledek.oprava) && (
            <ul className="space-y-1 text-xs">
              {v.kontroly
                .filter((k) => (k.ocekavan && !k.dodrzen) || k.nespravna_varianta_pouzita)
                .map((k) => (
                  <li key={k.termin_zdroj} className="text-chyba">
                    {k.nespravna_varianta_pouzita
                      ? `zakázaná varianta „${k.nespravna_varianta}“ - glosář: ${k.termin_zdroj} → „${k.termin_cil}“`
                      : `nepoužit termín: ${k.termin_zdroj} → „${k.termin_cil}“${popisChybnychTvaru(k.chybne_tvary)}`}
                  </li>
                ))}
              {vysledek.oprava && (
                <li className="text-textTlumeny">
                  {vysledek.oprava.prijata ? (
                    <>
                      1. pokus:{" "}
                      <span className="line-through">{vysledek.oprava.prvni_pokus}</span>{" "}
                      - nedodržen termín {vysledek.oprava.terminy.join(", ")}
                    </>
                  ) : (
                    <>
                      Opakovaný překlad s upozorněním na termín{" "}
                      {vysledek.oprava.terminy.join(", ")} výsledek nezlepšil, ponechán
                      první pokus.
                    </>
                  )}
                </li>
              )}
            </ul>
          )}

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
