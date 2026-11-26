import { useEffect, useRef, useState } from "react";
import {
  api,
  type Jazyk,
  type NahledCsv,
  type SloupecKatalogu,
  type StavKatalogu,
} from "../api";
import { useJazyky, useNacti, useOdlozeno, useSledovaniPostupu } from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Nacitani,
  OdznakJazyka,
  Panel,
  PrazdnyStav,
  Strankovac,
  UkazatelPostupu,
  ZahlaviObrazovky,
  formatujCas,
  formatujCislo,
  sklonuj,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 25;

const NAZVY_ROLI: Record<string, string> = {
  "": "-",
  id: "ID položky",
  popis: "Popis (porovnává se)",
  jazyk: "Jazyk záznamu",
  skupina: "Skupina / kategorie",
  trida: "Třída ISO 14224",
};

const POPIS_ZDROJE: Record<string, string> = {
  import: "importovaný soubor",
  generovany: "vygenerovaný testovací katalog",
  puvodni: "původní katalog",
};

type Rezim = "ne" | "sloupec" | "sloupce";

export default function Katalog() {
  const { pridej, vykresli } = useOznameni();
  const katalog = useNacti(() => api.katalog.stav(), []);
  const [dialog, nastavDialog] = useState<"import" | "generovat" | "smazat" | null>(null);
  const [verze, nastavVerzi] = useState(0);

  const poZmene = (zprava: string) => {
    pridej("uspech", zprava);
    nastavDialog(null);
    katalog.obnov();
    nastavVerzi((v) => v + 1);
  };

  const stav = katalog.data;

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Katalog položek"
        akce={
          stav?.existuje ? (
            <>
              <button className="tlacitko-vedlejsi" onClick={() => nastavDialog("import")}>
                Importovat CSV…
              </button>
              <button className="tlacitko-vedlejsi" onClick={() => nastavDialog("generovat")}>
                Vygenerovat testovací…
              </button>
              <button className="tlacitko-chyba" onClick={() => nastavDialog("smazat")}>
                Smazat katalog
              </button>
            </>
          ) : undefined
        }
      />

      {katalog.nacita && !stav ? (
        <Nacitani />
      ) : katalog.chyba ? (
        <ChybovyStav zprava={katalog.chyba} naObnoveni={katalog.obnov} />
      ) : stav && !stav.existuje ? (
        <Panel>
          <PrazdnyStav
            nadpis="Katalog je prázdný"
            popis="Importujte vlastní katalog ve formátu CSV, nebo vygenerujte testovací katalog náhradních dílů. Aktivní je vždy jen jeden katalog."
            akce={
              <div className="flex flex-wrap justify-center gap-2">
                <button className="tlacitko-hlavni" onClick={() => nastavDialog("import")}>
                  Importovat CSV…
                </button>
                <button className="tlacitko-vedlejsi" onClick={() => nastavDialog("generovat")}>
                  Vygenerovat testovací katalog
                </button>
              </div>
            }
          />
        </Panel>
      ) : stav ? (
        <SeznamPolozek stav={stav} verze={verze} />
      ) : null}

      {dialog === "import" && stav && (
        <DialogImportu
          stav={stav}
          naZavreni={() => nastavDialog(null)}
          naHotovo={(v) =>
            poZmene(
              `Importováno ${sklonuj(v.pocet_polozek, "položka", "položky", "položek")} ze souboru ${v.nazev_souboru}` +
                (v.preskoceno
                  ? `; přeskočeno ${sklonuj(v.preskoceno, "řádek", "řádky", "řádků")} bez popisu.`
                  : "."),
            )
          }
        />
      )}
      {dialog === "generovat" && stav && (
        <DialogGenerovani
          stav={stav}
          naZavreni={() => nastavDialog(null)}
          naHotovo={(pocet) =>
            poZmene(`Vygenerován testovací katalog (${sklonuj(pocet, "položka", "položky", "položek")}).`)
          }
        />
      )}
      {dialog === "smazat" && stav && (
        <DialogSmazani
          stav={stav}
          naZavreni={() => nastavDialog(null)}
          naHotovo={(pocet) =>
            poZmene(`Katalog smazán (${sklonuj(pocet, "položka", "položky", "položek")}).`)
          }
        />
      )}

      {vykresli}
    </>
  );
}

function SeznamPolozek({ stav, verze }: { stav: StavKatalogu; verze: number }) {
  const sloupce = stav.sloupce ?? [];
  const sRoli = (role: string) => sloupce.find((s) => s.role === role);
  const sloupecSkupiny = sRoli("skupina");
  const sloupecTridy = sRoli("trida");
  const maJazyk =
    stav.nastaveni?.vicejazycny !== "ne" || Boolean(stav.nastaveni?.jazyk_katalogu);

  const [hledani, nastavHledani] = useState("");
  const [skupina, nastavSkupinu] = useState("");
  const [trida, nastavTridu] = useState("");
  const [jazyk, nastavJazyk] = useState("");
  const [stavKonsolidace, nastavStavKonsolidace] = useState("");
  const [sestupne, nastavSestupne] = useState(false);
  const [razeni, nastavRazeni] = useState("poradi");
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [vybrana, nastavVybranou] = useState<string | null>(null);

  const hledaniOdlozene = useOdlozeno(hledani, 300);
  useEffect(() => {
    nastavOdsazeni(0);
  }, [hledaniOdlozene, skupina, trida, jazyk, stavKonsolidace, razeni, sestupne, verze]);

  const filtry = useNacti(() => api.polozky.filtry(), [verze]);
  const seznam = useNacti(
    () =>
      api.polozky.seznam({
        hledany_text: hledaniOdlozene,
        komoditni_skupina: skupina,
        iso_trida: trida,
        jazyk,
        stav_konsolidace: stavKonsolidace,
        razeni,
        sestupne,
        limit: NA_STRANKU,
        odsazeni,
      }),
    [hledaniOdlozene, skupina, trida, jazyk, stavKonsolidace, razeni, sestupne, odsazeni, verze],
  );

  const jeFiltrovano = hledani || skupina || trida || jazyk || stavKonsolidace;
  const vycistiFiltry = () => {
    nastavHledani("");
    nastavSkupinu("");
    nastavTridu("");
    nastavJazyk("");
    nastavStavKonsolidace("");
  };
  const seradPodleId = () => {
    if (razeni === "itemnum") nastavSestupne(!sestupne);
    else {
      nastavRazeni("itemnum");
      nastavSestupne(false);
    }
  };

  return (
    <>
      <p className="mb-3 text-sm text-textTlumeny">
        {stav.nazev_souboru} · {POPIS_ZDROJE[stav.zdroj ?? ""] ?? stav.zdroj} ·{" "}
        {sklonuj(stav.pocet_polozek ?? 0, "položka", "položky", "položek")} ·{" "}
        {sklonuj(sloupce.length, "sloupec", "sloupce", "sloupců")} ·
        načteno {formatujCas(stav.importovano ?? null)}
      </p>

      <Panel bezOdsazeni>
        <div className="flex flex-wrap items-end gap-2.5 p-3.5 border-b border-obrys">
          <div className="flex-1 min-w-[220px]">
            <label className="stitek-pole" htmlFor="hledani">
              Hledat
            </label>
            <input
              id="hledani"
              className="pole"
              placeholder="Hodnota v kterémkoli sloupci…"
              value={hledani}
              onChange={(e) => nastavHledani(e.target.value)}
            />
          </div>
          {sloupecSkupiny && (
            <VyberFiltru
              popisek={sloupecSkupiny.nazev}
              hodnota={skupina}
              naZmenu={nastavSkupinu}
              moznosti={filtry.data?.komoditni_skupiny ?? []}
            />
          )}
          {sloupecTridy && (
            <VyberFiltru
              popisek={sloupecTridy.nazev}
              hodnota={trida}
              naZmenu={nastavTridu}
              moznosti={filtry.data?.iso_tridy ?? []}
            />
          )}
          {maJazyk && (
            <VyberFiltru
              popisek="Jazyk"
              hodnota={jazyk}
              naZmenu={nastavJazyk}
              moznosti={filtry.data?.jazyky ?? []}
            />
          )}
          <VyberFiltru
            popisek="Konsolidace"
            hodnota={stavKonsolidace}
            naZmenu={nastavStavKonsolidace}
            moznosti={["aktivni", "slouceno"]}
          />
          {jeFiltrovano && (
            <button className="tlacitko-tichy" onClick={vycistiFiltry}>
              <Ikona.Krizek velikost={14} /> Zrušit filtry
            </button>
          )}
        </div>

        {seznam.nacita && !seznam.data ? (
          <Nacitani />
        ) : seznam.chyba ? (
          <ChybovyStav zprava={seznam.chyba} naObnoveni={seznam.obnov} />
        ) : seznam.data && seznam.data.celkem === 0 ? (
          <PrazdnyStav
            nadpis="Žádná položka neodpovídá zadání"
            popis="Zkuste upravit hledaný výraz nebo zrušit některý z filtrů."
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="tabulka">
                <thead>
                  <tr>
                    {sloupce.map((s) => (
                      <th key={s.nazev} className="whitespace-nowrap">
                        {s.role === "id" ? (
                          <button
                            className={`flex items-center gap-1 hover:text-text ${razeni === "itemnum" ? "text-akcent" : ""}`}
                            onClick={seradPodleId}
                          >
                            {s.nazev}
                            <span className="text-[9px] leading-none">
                              {razeni === "itemnum" ? (sestupne ? "▼" : "▲") : "↕"}
                            </span>
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1">
                            {s.nazev}
                            {s.jazyk && <OdznakJazyka kod={s.jazyk.toUpperCase()} />}
                          </span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {seznam.data?.polozky.map((p) => (
                    <tr
                      key={p.itemnum}
                      className="cursor-pointer"
                      onClick={() => nastavVybranou(p.itemnum)}
                    >
                      {sloupce.map((s) => (
                        <td
                          key={s.nazev}
                          className={s.role === "popis" ? "max-w-[38ch]" : "max-w-[24ch] truncate"}
                          title={s.role === "popis" ? undefined : p.data[s.nazev]}
                        >
                          {s.role === "id" ? (
                            <>
                              <Kod>{p.itemnum}</Kod>
                              {p.stav_konsolidace === "slouceno" && p.slouceno_do && (
                                <span className="block text-2xs text-textSlaby mt-0.5">
                                  sloučeno do {p.slouceno_do}
                                </span>
                              )}
                            </>
                          ) : s.role === "jazyk" ? (
                            <OdznakJazyka kod={p.lang_code || p.data[s.nazev]} />
                          ) : (
                            p.data[s.nazev]
                          )}
                        </td>
                      ))}
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

      {vybrana && (
        <PanelDetailu
          itemnum={vybrana}
          sloupce={sloupce}
          naZavreni={() => nastavVybranou(null)}
        />
      )}
    </>
  );
}

function VyberFiltru({
  popisek,
  hodnota,
  naZmenu,
  moznosti,
}: {
  popisek: string;
  hodnota: string;
  naZmenu: (h: string) => void;
  moznosti: string[];
}) {
  return (
    <div>
      <label className="stitek-pole">{popisek}</label>
      <select
        className="pole w-auto min-w-[9rem]"
        value={hodnota}
        onChange={(e) => naZmenu(e.target.value)}
      >
        <option value="">vše</option>
        {moznosti.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  );
}

function Dialog({
  nadpis,
  sirka = "max-w-lg",
  zaneprazdnen = false,
  naZavreni,
  children,
  paticka,
}: {
  nadpis: string;
  sirka?: string;
  zaneprazdnen?: boolean;
  naZavreni: () => void;
  children: React.ReactNode;
  paticka: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 animate-rozsvit"
        onClick={zaneprazdnen ? undefined : naZavreni}
      />
      <div className={`relative w-full ${sirka} max-h-[92vh] flex flex-col panel shadow-vyzdvih animate-nastup`}>
        <header className="panel-hlavicka">
          <h2 className="text-sm font-semibold">{nadpis}</h2>
          <button
            className="tlacitko-tichy px-2"
            onClick={naZavreni}
            disabled={zaneprazdnen}
            aria-label="Zavřít"
          >
            <Ikona.Krizek />
          </button>
        </header>
        <div className="p-4 space-y-4 overflow-y-auto">{children}</div>
        <footer className="flex items-center justify-end gap-2 px-4 py-3 border-t border-obrys">
          {paticka}
        </footer>
      </div>
    </div>
  );
}

function VarovaniNahrazeni({ stav, co }: { stav: StavKatalogu; co: string }) {
  if (!stav.existuje) return null;
  return (
    <div className="panel p-3 border-vystraha bg-vystrahaTlumena text-sm text-text">
      {co} nahradí současný katalog „{stav.nazev_souboru}“ (
      {sklonuj(stav.pocet_polozek ?? 0, "položka", "položky", "položek")}).
      {stav.pocet_behu > 0 &&
        ` Smaže se také ${sklonuj(stav.pocet_behu, "běh", "běhy", "běhů")} deduplikace včetně skupin a rozhodnutí o sloučení.`}{" "}
      Glosář a historie překladů zůstanou.
    </div>
  );
}

function DialogSmazani({
  stav,
  naZavreni,
  naHotovo,
}: {
  stav: StavKatalogu;
  naZavreni: () => void;
  naHotovo: (pocet: number) => void;
}) {
  const [pracuje, nastavPracuje] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);

  const smaz = async () => {
    nastavPracuje(true);
    try {
      const vysledek = await api.katalog.smazat();
      naHotovo(vysledek.polozek);
    } catch (duvod) {
      nastavChybu(duvod instanceof Error ? duvod.message : "Katalog se nepodařilo smazat.");
      nastavPracuje(false);
    }
  };

  return (
    <Dialog
      nadpis="Smazat katalog?"
      zaneprazdnen={pracuje}
      naZavreni={naZavreni}
      paticka={
        <>
          <button className="tlacitko-vedlejsi" onClick={naZavreni} disabled={pracuje}>
            Zrušit
          </button>
          <button className="tlacitko-chyba" onClick={() => void smaz()} disabled={pracuje}>
            {pracuje ? "Mažu…" : "Smazat katalog"}
          </button>
        </>
      }
    >
      <p className="text-sm text-text">Smaže se:</p>
      <ul className="text-sm text-textTlumeny list-disc pl-5 space-y-1">
        <li>
          katalog „{stav.nazev_souboru}“ -{" "}
          {sklonuj(stav.pocet_polozek ?? 0, "položka", "položky", "položek")},
        </li>
        <li>
          {sklonuj(stav.pocet_behu, "běh", "běhy", "běhů")} deduplikace včetně navržených
          skupin a rozhodnutí o sloučení,
        </li>
        <li>záznamy událostí integrace na Maximo.</li>
      </ul>
      <p className="text-sm text-textTlumeny">
        Glosář a historie překladů zůstanou. Poté lze importovat jiný katalog.
      </p>
      {chyba && <ChybovyStav zprava={chyba} />}
    </Dialog>
  );
}

function DialogGenerovani({
  stav,
  naZavreni,
  naHotovo,
}: {
  stav: StavKatalogu;
  naZavreni: () => void;
  naHotovo: (pocet: number) => void;
}) {
  const [pocet, nastavPocet] = useState(5000);
  const [pracuje, nastavPracuje] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);
  const platny = pocet >= 100 && pocet <= 50000;

  const generuj = async () => {
    nastavPracuje(true);
    try {
      const vysledek = await api.katalog.generovat(pocet);
      naHotovo(vysledek.pocet_polozek);
    } catch (duvod) {
      nastavChybu(duvod instanceof Error ? duvod.message : "Katalog se nepodařilo vygenerovat.");
      nastavPracuje(false);
    }
  };

  return (
    <Dialog
      nadpis="Vygenerovat testovací katalog"
      zaneprazdnen={pracuje}
      naZavreni={naZavreni}
      paticka={
        <>
          <button className="tlacitko-vedlejsi" onClick={naZavreni} disabled={pracuje}>
            Zrušit
          </button>
          <button
            className="tlacitko-hlavni"
            onClick={() => void generuj()}
            disabled={pracuje || !platny}
          >
            {pracuje ? "Generuji…" : "Vygenerovat"}
          </button>
        </>
      }
    >
      <p className="text-sm text-textTlumeny">
        Vytvoří katalog náhradních dílů ve struktuře objektu ITEM systému Maximo, z něhož
        je 20 % záměrně vytvořených duplicit, a soubor s referenčním přiřazením pro
        vyhodnocení. Při stejném počtu je výsledek vždy stejný.
      </p>
      <div>
        <label className="stitek-pole" htmlFor="pocet-polozek">
          Počet položek
        </label>
        <input
          id="pocet-polozek"
          type="number"
          className="pole w-40"
          min={100}
          max={50000}
          step={100}
          value={pocet}
          onChange={(e) => nastavPocet(Number(e.target.value))}
        />
        {!platny && <p className="mt-1 text-xs text-chyba">Zadejte 100 až 50 000.</p>}
      </div>
      <VarovaniNahrazeni stav={stav} co="Vygenerovaný katalog" />
      {chyba && <ChybovyStav zprava={chyba} />}
    </Dialog>
  );
}

interface NastaveniSloupce {
  index: number;
  nazev: string;
  role: string;
  jazyk: string;
}

function DialogImportu({
  stav,
  naZavreni,
  naHotovo,
}: {
  stav: StavKatalogu;
  naZavreni: () => void;
  naHotovo: (vysledek: { pocet_polozek: number; preskoceno: number; nazev_souboru: string }) => void;
}) {
  const jazyky = useJazyky();
  const vyberSouboru = useRef<HTMLInputElement>(null);
  const [soubor, nastavSoubor] = useState<File | null>(null);
  const [maId, nastavMaId] = useState(true);
  const [rezim, nastavRezim] = useState<Rezim>("ne");
  const [kodovani, nastavKodovani] = useState("");
  const [oddelovac, nastavOddelovac] = useState("");
  const [nahled, nastavNahled] = useState<NahledCsv | null>(null);
  const [sloupce, nastavSloupce] = useState<NastaveniSloupce[]>([]);
  const [mapaJazyku, nastavMapuJazyku] = useState<Record<string, string>>({});
  const [jazykKatalogu, nastavJazykKatalogu] = useState("");
  const [pracuje, nastavPracuje] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);
  const postupImportu = useSledovaniPostupu(api.katalog.prubehImportu, pracuje && nahled !== null);

  const povoleneRole = Object.keys(NAZVY_ROLI).filter(
    (r) => (r !== "id" || maId) && (r !== "jazyk" || rezim === "sloupec"),
  );

  const nactiSoubor = async () => {
    if (!soubor) return;
    nastavPracuje(true);
    nastavChybu(null);
    try {
      const vysledek = await api.katalog.nahled(soubor, {
        kodovani: kodovani || undefined,
        oddelovac: oddelovac || undefined,
      });
      nastavNahled(vysledek);
      nastavSloupce(
        vysledek.sloupce.map((s) => ({
          index: s.index,
          nazev: s.puvodni,
          role:
            (s.navrh_role === "id" && !maId) || (s.navrh_role === "jazyk" && rezim !== "sloupec")
              ? ""
              : s.navrh_role,
          jazyk: rezim === "sloupce" ? s.navrh_jazyk : "",
        })),
      );
      nastavMapuJazyku(vysledek.navrh.mapa_jazyku);
    } catch (duvod) {
      nastavChybu(duvod instanceof Error ? duvod.message : "Soubor se nepodařilo načíst.");
    } finally {
      nastavPracuje(false);
    }
  };

  const zmenSloupec = (index: number, zmena: Partial<NastaveniSloupce>) =>
    nastavSloupce((puvodni) => puvodni.map((s) => (s.index === index ? { ...s, ...zmena } : s)));

  const sRoli = (role: string) => sloupce.filter((s) => s.role === role);
  const sloupecJazyka = sRoli("jazyk")[0];
  const navrhJazyka = nahled?.sloupce.find((s) => s.index === sloupecJazyka?.index);
  const sloupecId = sRoli("id")[0];
  const navrhId = nahled?.sloupce.find((s) => s.index === sloupecId?.index);
  const nazvy = sloupce.map((s) => s.nazev.trim().toLowerCase());

  const problemy: string[] = [];
  if (nahled) {
    if (nazvy.some((n) => !n)) problemy.push("Každý sloupec musí mít název.");
    if (new Set(nazvy).size !== nazvy.length) problemy.push("Názvy sloupců se nesmí opakovat.");
    if (sRoli("popis").length === 0)
      problemy.push("Označte alespoň jeden sloupec s popisem položky - ten se porovnává při deduplikaci.");
    if (maId && sRoli("id").length !== 1) problemy.push("Označte právě jeden sloupec s ID položek.");
    if (maId && navrhId && !navrhId.unikatni)
      problemy.push(`Hodnoty ve sloupci „${sloupecId.nazev}“ nejsou jedinečné nebo některé chybí - zvolte jiný sloupec, nebo nechte ID vygenerovat.`);
    if (rezim === "sloupec" && sRoli("jazyk").length !== 1)
      problemy.push("Označte právě jeden sloupec, který uvádí jazyk záznamu.");
    const bezJazyka = (navrhJazyka?.hodnoty ?? []).filter((h) => !mapaJazyku[h]);
    if (rezim === "sloupec" && bezJazyka.length > 0)
      problemy.push(
        `Přiřaďte jazyk ${bezJazyka.length === 1 ? "hodnotě" : "hodnotám"} ${bezJazyka.map((h) => `„${h}“`).join(", ")} ve sloupci „${sloupecJazyka?.nazev}“.`,
      );
    if (rezim === "sloupec" && navrhJazyka && navrhJazyka.hodnoty === null)
      problemy.push(`Sloupec „${sloupecJazyka.nazev}“ má více než 30 různých hodnot, zřejmě neuvádí jazyk.`);
    if (rezim === "sloupce" && sloupce.filter((s) => s.jazyk).length < 2)
      problemy.push("Označte jazyk alespoň u dvou sloupců.");
    if (rezim === "sloupce" && sRoli("popis").some((s) => !s.jazyk))
      problemy.push("U vícejazyčného souboru musí mít každý sloupec s popisem uvedený jazyk.");
    for (const role of ["skupina", "trida"])
      if (sRoli(role).length > 1) problemy.push(`Roli „${NAZVY_ROLI[role]}“ může mít jen jeden sloupec.`);
  }

  const importuj = async () => {
    if (!nahled) return;
    nastavPracuje(true);
    nastavChybu(null);
    try {
      const vysledek = await api.katalog.importovat({
        token: nahled.token,
        sloupce,
        ma_id: maId,
        vicejazycny: rezim,
        mapa_jazyku: Object.fromEntries(Object.entries(mapaJazyku).filter(([, v]) => v)),
        jazyk_katalogu: rezim === "ne" ? jazykKatalogu : "",
      });
      naHotovo(vysledek);
    } catch (duvod) {
      nastavChybu(duvod instanceof Error ? duvod.message : "Import se nezdařil.");
      nastavPracuje(false);
    }
  };

  return (
    <Dialog
      nadpis={nahled ? `Sloupce souboru ${nahled.nazev_souboru}` : "Import katalogu z CSV"}
      sirka={nahled ? "max-w-5xl" : "max-w-lg"}
      zaneprazdnen={pracuje}
      naZavreni={naZavreni}
      paticka={
        nahled ? (
          <>
            <button
              className="tlacitko-vedlejsi mr-auto"
              onClick={() => nastavNahled(null)}
              disabled={pracuje}
            >
              Zpět
            </button>
            <button className="tlacitko-vedlejsi" onClick={naZavreni} disabled={pracuje}>
              Zrušit
            </button>
            <button
              className="tlacitko-hlavni"
              onClick={() => void importuj()}
              disabled={pracuje || problemy.length > 0}
            >
              {pracuje
                ? "Importuji…"
                : `Importovat ${sklonuj(nahled.pocet_radku, "řádek", "řádky", "řádků")}`}
            </button>
          </>
        ) : (
          <>
            <button className="tlacitko-vedlejsi" onClick={naZavreni} disabled={pracuje}>
              Zrušit
            </button>
            <button
              className="tlacitko-hlavni"
              onClick={() => void nactiSoubor()}
              disabled={pracuje || !soubor}
            >
              {pracuje ? "Načítám…" : "Načíst soubor"}
            </button>
          </>
        )
      }
    >
      {pracuje && nahled && postupImportu?.stav === "bezi" && (
        <div className="panel p-3 mb-3">
          <UkazatelPostupu postup={postupImportu} />
        </div>
      )}
      {!nahled ? (
        <>
          <div>
            <p className="stitek-pole">Soubor CSV</p>
            <div className="flex items-center gap-2">
              <button
                className="tlacitko-vedlejsi"
                onClick={() => vyberSouboru.current?.click()}
              >
                Vybrat soubor…
              </button>
              <span className="text-sm text-textTlumeny truncate">
                {soubor ? `${soubor.name} (${formatujCislo(Math.ceil(soubor.size / 1024))} kB)` : "nevybrán"}
              </span>
              <input
                ref={vyberSouboru}
                type="file"
                accept=".csv,text/csv,text/plain"
                className="hidden"
                onChange={(e) => nastavSoubor(e.target.files?.[0] ?? null)}
              />
            </div>
            <p className="mt-1 text-xs text-textSlaby">
              První řádek musí obsahovat názvy sloupců. Sloupce mohou být libovolné.
            </p>
          </div>

          <fieldset>
            <legend className="stitek-pole">Obsahuje soubor sloupec s ID položek?</legend>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" className="accent-akcent" checked={maId} onChange={() => nastavMaId(true)} />
                ano, označím jej
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" className="accent-akcent" checked={!maId} onChange={() => nastavMaId(false)} />
                ne, vygenerovat
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend className="stitek-pole">Obsahuje soubor záznamy ve více jazycích?</legend>
            <div className="space-y-1.5 text-sm">
              {(
                [
                  ["ne", "ne, celý katalog je v jednom jazyce"],
                  ["sloupec", "ano - jazyk záznamu uvádí samostatný sloupec (např. LANGCODE = CS, EN)"],
                  ["sloupce", "ano - každý jazyk má vlastní sloupec (např. POPIS_CS, POPIS_EN)"],
                ] as [Rezim, string][]
              ).map(([hodnota, text]) => (
                <label key={hodnota} className="flex items-start gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    className="accent-akcent mt-1"
                    checked={rezim === hodnota}
                    onChange={() => nastavRezim(hodnota)}
                  />
                  {text}
                </label>
              ))}
            </div>
          </fieldset>

          <details>
            <summary className="cursor-pointer text-xs text-textTlumeny select-none">
              Kódování a oddělovač
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-3">
              <div>
                <label className="stitek-pole" htmlFor="kodovani">Kódování</label>
                <select id="kodovani" className="pole" value={kodovani} onChange={(e) => nastavKodovani(e.target.value)}>
                  <option value="">rozpoznat automaticky</option>
                  <option value="utf-8">UTF-8</option>
                  <option value="cp1250">Windows-1250 (Excel)</option>
                </select>
              </div>
              <div>
                <label className="stitek-pole" htmlFor="oddelovac">Oddělovač</label>
                <select id="oddelovac" className="pole" value={oddelovac} onChange={(e) => nastavOddelovac(e.target.value)}>
                  <option value="">rozpoznat automaticky</option>
                  <option value="strednik">středník ;</option>
                  <option value="carka">čárka ,</option>
                  <option value="tabulator">tabulátor</option>
                  <option value="svislice">svislice |</option>
                </select>
              </div>
            </div>
          </details>

          <VarovaniNahrazeni stav={stav} co="Import" />
        </>
      ) : (
        <>
          <p className="text-sm text-textTlumeny">
            Nalezeno {sklonuj(nahled.sloupce.length, "sloupec", "sloupce", "sloupců")} a{" "}
            {sklonuj(nahled.pocet_radku, "řádek", "řádky", "řádků")}
            (kódování {nahled.kodovani}, oddělovač{" "}
            {nahled.oddelovac === "\t" ? "tabulátor" : `„${nahled.oddelovac}“`}). Názvy sloupců
            lze upravit; u sloupců označte jejich význam.
            {!maId && " Na začátek katalogu se přidá sloupec ID s pořadovými čísly."}
          </p>
          {nahled.radku_s_prebytkem > 0 && (
            <div className="panel p-3 border-vystraha bg-vystrahaTlumena text-sm text-text">
              {sklonuj(nahled.radku_s_prebytkem, "řádek má", "řádky mají", "řádků má")} více
              hodnot, než je sloupců
              v záhlaví - nejspíš obsahují oddělovač uvnitř hodnoty, například desetinnou
              čárku v souboru odděleném čárkami. Přebývající hodnoty by se zahodily. Vraťte se
              zpět a zvolte jiný oddělovač, nebo soubor uložte znovu s hodnotami v uvozovkách.
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="tabulka">
              <thead>
                <tr>
                  <th>Sloupec v souboru</th>
                  <th>Název v aplikaci</th>
                  <th>Význam</th>
                  {rezim === "sloupce" && <th>Jazyk obsahu</th>}
                </tr>
              </thead>
              <tbody>
                {sloupce.map((s) => {
                  const navrh = nahled.sloupce.find((n) => n.index === s.index);
                  return (
                    <tr key={s.index}>
                      <td className="max-w-[26ch]">
                        <span className="font-mono text-xs text-text">{navrh?.puvodni}</span>
                        <span className="block text-2xs text-textSlaby truncate">
                          {navrh?.priklady.join(" · ") || "prázdný sloupec"}
                        </span>
                      </td>
                      <td>
                        <input
                          className="pole"
                          value={s.nazev}
                          onChange={(e) => zmenSloupec(s.index, { nazev: e.target.value })}
                        />
                      </td>
                      <td>
                        <select
                          className="pole"
                          value={s.role}
                          onChange={(e) => zmenSloupec(s.index, { role: e.target.value })}
                        >
                          {povoleneRole.map((r) => (
                            <option key={r} value={r}>
                              {NAZVY_ROLI[r]}
                            </option>
                          ))}
                        </select>
                      </td>
                      {rezim === "sloupce" && (
                        <td>
                          <VolbaJazykaObsahu
                            jazyky={jazyky}
                            hodnota={s.jazyk}
                            prazdna="-"
                            naZmenu={(kod) => zmenSloupec(s.index, { jazyk: kod })}
                          />
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {rezim === "sloupec" && sloupecJazyka && navrhJazyka?.hodnoty && (
            <div>
              <p className="stitek-pole">
                Jazyk podle hodnot ve sloupci „{sloupecJazyka.nazev}“
              </p>
              <div className="grid sm:grid-cols-3 gap-2">
                {navrhJazyka.hodnoty.map((hodnota) => (
                  <label key={hodnota} className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-xs w-20 truncate" title={hodnota}>
                      {hodnota}
                    </span>
                    <VolbaJazykaObsahu
                      jazyky={jazyky}
                      hodnota={mapaJazyku[hodnota] ?? ""}
                      prazdna="neurčen"
                      naZmenu={(kod) => nastavMapuJazyku({ ...mapaJazyku, [hodnota]: kod })}
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          {rezim === "ne" && (
            <div className="max-w-xs">
              <label className="stitek-pole">Jazyk katalogu</label>
              <VolbaJazykaObsahu
                jazyky={jazyky}
                hodnota={jazykKatalogu}
                prazdna="neuvádět"
                naZmenu={nastavJazykKatalogu}
              />
            </div>
          )}

          {problemy.length > 0 && (
            <ul className="space-y-1">
              {problemy.map((p) => (
                <li key={p} className="flex items-start gap-1.5 text-xs text-vystraha">
                  <span className="mt-px shrink-0">
                    <Ikona.Info velikost={12} />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
          )}
          <VarovaniNahrazeni stav={stav} co="Import" />
        </>
      )}
      {chyba && <ChybovyStav zprava={chyba} />}
    </Dialog>
  );
}

function VolbaJazykaObsahu({
  jazyky,
  hodnota,
  prazdna,
  naZmenu,
}: {
  jazyky: Jazyk[];
  hodnota: string;
  prazdna: string;
  naZmenu: (kod: string) => void;
}) {
  return (
    <select className="pole" value={hodnota} onChange={(e) => naZmenu(e.target.value)}>
      <option value="">{prazdna}</option>
      {jazyky.map((j) => (
        <option key={j.kod} value={j.kod}>
          {j.nazev}
        </option>
      ))}
    </select>
  );
}

function PanelDetailu({
  itemnum,
  sloupce,
  naZavreni,
}: {
  itemnum: string;
  sloupce: SloupecKatalogu[];
  naZavreni: () => void;
}) {
  const detail = useNacti(() => api.polozky.detail(itemnum), [itemnum]);
  const [xml, nastavXml] = useState<string | null>(null);

  useEffect(() => {
    const naKlavesu = (e: KeyboardEvent) => {
      if (e.key === "Escape") naZavreni();
    };
    window.addEventListener("keydown", naKlavesu);
    return () => window.removeEventListener("keydown", naKlavesu);
  }, [naZavreni]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/35 animate-rozsvit" onClick={naZavreni} />
      <aside className="relative w-[min(34rem,100vw)] h-full overflow-y-auto bg-plocha border-l border-obrys shadow-vyzdvih animate-nastup">
        <header className="sticky top-0 flex items-center justify-between gap-3 px-5 h-[57px] bg-plocha border-b border-obrys">
          <div className="min-w-0">
            <p className="nadpis-sekce">Detail položky</p>
            <p className="font-mono text-sm text-text truncate">{itemnum}</p>
          </div>
          <button className="tlacitko-tichy px-2" onClick={naZavreni} aria-label="Zavřít">
            <Ikona.Krizek />
          </button>
        </header>

        <div className="p-5">
          {detail.nacita ? (
            <Nacitani />
          ) : detail.chyba ? (
            <ChybovyStav zprava={detail.chyba} />
          ) : detail.data ? (
            <div className="space-y-5">
              <div>
                <p className="nadpis-sekce mb-1">Popis porovnávaný při deduplikaci</p>
                <p className="text-text leading-relaxed">{detail.data.description}</p>
              </div>

              {detail.data.zarazeni_iso && (
                <div className="panel p-3.5 bg-plocha2">
                  <p className="nadpis-sekce mb-1.5">Zařazení dle ISO 14224</p>
                  <p className="flex items-center gap-2">
                    <span className="odznak-akcent">{detail.data.zarazeni_iso.kod}</span>
                    <span className="text-sm text-text">{detail.data.zarazeni_iso.nazev_cs}</span>
                  </p>
                  <p className="mt-1.5 text-xs text-textTlumeny">
                    {detail.data.zarazeni_iso.zduvodneni} Jistota{" "}
                    <span className="font-mono">
                      {(detail.data.zarazeni_iso.jistota * 100).toFixed(0)} %
                    </span>
                    .
                  </p>
                </div>
              )}

              <dl className="grid grid-cols-2 gap-x-5 gap-y-3 text-sm">
                {sloupce.map((s) => (
                  <div key={s.nazev}>
                    <dt className="nadpis-sekce">
                      {s.nazev}
                      {s.jazyk && ` (${s.jazyk})`}
                    </dt>
                    <dd className="mt-0.5 text-text break-words">
                      {detail.data?.data[s.nazev] || "-"}
                    </dd>
                  </div>
                ))}
              </dl>

              {detail.data.stav_konsolidace === "slouceno" && (
                <div className="panel p-3.5 border-uspech/40 bg-uspechTlumeny">
                  <p className="text-sm text-uspech">
                    Tento záznam byl označen jako duplicita a sloučen do položky{" "}
                    <span className="font-mono font-semibold">{detail.data.slouceno_do}</span>.
                  </p>
                </div>
              )}

              <div>
                <button
                  className="tlacitko-vedlejsi w-full"
                  onClick={async () => nastavXml(await api.polozky.xml(itemnum))}
                >
                  <Ikona.Stahnout velikost={14} /> Zobrazit jako MXITEM (XML)
                </button>
                {xml && (
                  <pre className="mt-3 max-h-72 overflow-auto rounded-xs border border-obrys bg-plocha2 p-3 font-mono text-[0.7rem] leading-relaxed text-textTlumeny">
                    {xml}
                  </pre>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
