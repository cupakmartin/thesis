import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Prehled as DataPrehledu, type StatistikaPrekladu } from "../api";
import { useJazyky, useNacti } from "../hooky";
import KontrolaModelu from "../KontrolaModelu";
import {
  ChybovyStav,
  Ikona,
  Metrika,
  Nacitani,
  Panel,
  PrazdnyStav,
  ZahlaviObrazovky,
  formatujCas,
  formatujCislo,
  formatujProcenta,
  sklonuj,
} from "../komponenty";

const MAX_SLOUPCU_GRAFU = 12;
const VYSKA_RADKU_GRAFU = 26;
const MAX_ZNAKU_POPISKU = 30;

interface Hodnota {
  nazev: string;
  pocet: number;
  celyNazev?: string;
}

function omezNaNejvetsi(hodnoty: Hodnota[]): Hodnota[] {
  if (hodnoty.length <= MAX_SLOUPCU_GRAFU) return hodnoty;
  const zobrazene = hodnoty.slice(0, MAX_SLOUPCU_GRAFU - 1);
  const zbytek = hodnoty.slice(MAX_SLOUPCU_GRAFU - 1);
  return [
    ...zobrazene,
    {
      nazev: `ostatní (${sklonuj(zbytek.length, "skupina", "skupiny", "skupin")})`,
      pocet: zbytek.reduce((s, h) => s + h.pocet, 0),
    },
  ];
}

function zkrat(text: string): string {
  return text.length > MAX_ZNAKU_POPISKU
    ? `${text.slice(0, MAX_ZNAKU_POPISKU - 1)}…`
    : text;
}

export default function Prehled() {
  const prehled = useNacti(() => api.system.prehled(), []);
  const stav = useNacti(() => api.system.stav(), []);
  const jazyky = useJazyky();

  if (prehled.nacita) return <Nacitani text="Načítám přehled…" />;
  if (prehled.chyba)
    return <ChybovyStav zprava={prehled.chyba} naObnoveni={prehled.obnov} />;
  if (!prehled.data) return null;

  const { katalog, posledni_beh, slucovani, preklady, glosar } = prehled.data;
  const nazevJazyka = (kod: string) =>
    jazyky.find((j) => j.kod === kod.toLowerCase())?.nazev ?? kod;
  const podilDuplicit =
    posledni_beh && katalog.pocet_polozek
      ? posledni_beh.pocet_duplicit / katalog.pocet_polozek
      : 0;

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Přehled"
        akce={
          <Link to="/deduplikace" className="tlacitko-hlavni">
            <Ikona.Spustit velikost={14} /> Spustit deduplikaci
          </Link>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <Metrika
          popisek="Položek v katalogu"
          hodnota={formatujCislo(katalog.pocet_polozek)}
          napoveda={
            katalog.nazev_souboru
              ? `Aktivní katalog: ${katalog.nazev_souboru}`
              : "Celkový počet záznamů kmenových dat."
          }
        />
        <Metrika
          popisek="Nadbytečných záznamů"
          hodnota={posledni_beh ? formatujCislo(posledni_beh.pocet_duplicit) : "-"}
          jednotka={posledni_beh ? formatujProcenta(podilDuplicit, 1) : undefined}
          zvyrazneni="vystraha"
          napoveda="Záznamy nad rámec jednoho referenčního v každé skupině duplicit podle posledního běhu, a jejich podíl na katalogu."
        />
        <Metrika
          popisek="Skupin ke kontrole"
          hodnota={posledni_beh ? formatujCislo(slucovani.ke_kontrole) : "-"}
          jednotka={
            posledni_beh ? `z ${formatujCislo(posledni_beh.pocet_klastru)}` : undefined
          }
          zvyrazneni="akcent"
          napoveda="Skupiny duplicit z posledního běhu, o nichž správce dat dosud nerozhodl."
        />
        <Metrika
          popisek="Sloučených záznamů"
          hodnota={formatujCislo(slucovani.sloucenych_zaznamu)}
          zvyrazneni="uspech"
          napoveda="Záznamy, u nichž správce dat sloučení potvrdil."
        />
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <GrafSkupin katalog={katalog} />

        <div className="space-y-4">
          <PanelKatalogu katalog={katalog} nazevJazyka={nazevJazyka} />

          <Panel nadpis="Stav systému">
            {stav.data ? (
              <dl className="space-y-2 text-sm">
                <RadekStavu
                  popisek="Jazykový model"
                  hodnota={
                    stav.data.ollama_dostupna
                      ? stav.data.aktivni_model
                      : "Ollama neběží"
                  }
                  vPoradku={stav.data.ollama_dostupna}
                />
                <RadekStavu
                  popisek="Vektorový index"
                  hodnota={stav.data.index_pripraven ? "připraven" : "nesestaven"}
                  vPoradku={stav.data.index_pripraven}
                />
                <RadekStavu
                  popisek="Glosář"
                  hodnota={`${stav.data.pocet_terminu} termínů`}
                  vPoradku={stav.data.glosar_nacten}
                />
                <RadekStavu
                  popisek="Zpracování dat"
                  hodnota={stav.data.offline_rezim ? "lokálně" : "vzdáleně"}
                  vPoradku={stav.data.offline_rezim}
                />
              </dl>
            ) : (
              <Nacitani text="Zjišťuji stav…" />
            )}
          </Panel>
        </div>
      </div>

      <div className="mt-4">
        <KontrolaModelu />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <PanelDeduplikace beh={posledni_beh} slucovani={slucovani} />
        <PanelPrekladu preklady={preklady} nazevJazyka={nazevJazyka} />
      </div>

      <div className="mt-4">
        <PanelGlosare glosar={glosar} nazevJazyka={nazevJazyka} />
      </div>
    </>
  );
}

function GrafSkupin({ katalog }: { katalog: DataPrehledu["katalog"] }) {
  const podleSkupiny = katalog.sloupec_skupiny && katalog.podle_komoditni_skupiny.length > 0;
  const zdroj: Hodnota[] = podleSkupiny
    ? katalog.podle_komoditni_skupiny.map((h) => ({
        nazev: h.nazev || "(bez hodnoty)",
        pocet: h.pocet,
      }))
    : katalog.podle_iso_tridy;
  const data = omezNaNejvetsi(zdroj).map((h) => ({
    ...h,
    celyNazev: h.nazev,
    nazev: zkrat(h.nazev),
  }));
  const nejdelsi = Math.max(0, ...data.map((h) => h.nazev.length));
  const sirkaOsy = Math.min(230, Math.max(64, nejdelsi * 6.2 + 16));

  return (
    <Panel
      nadpis={
        podleSkupiny
          ? `Rozložení podle sloupce „${katalog.sloupec_skupiny}“`
          : "Rozložení podle třídy ISO 14224"
      }
      popis={
        zdroj.length > MAX_SLOUPCU_GRAFU
          ? `${formatujCislo(zdroj.length)} hodnot; zobrazeno ${MAX_SLOUPCU_GRAFU - 1} nejčetnějších, zbytek je sečten`
          : `${sklonuj(zdroj.length, "hodnota", "hodnoty", "hodnot")} ve struktuře katalogu`
      }
      trida="xl:col-span-2"
    >
      {data.length === 0 ? (
        <PrazdnyStav
          nadpis="Katalog nemá sloupec skupiny"
          popis="Při importu lze některý sloupec označit jako skupinu; jinak se zobrazí rozložení podle třídy ISO 14224, jakmile ji položky mají."
        />
      ) : (
        <ResponsiveContainer width="100%" height={data.length * VYSKA_RADKU_GRAFU + 32}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 4, right: 24, top: 4, bottom: 4 }}
            barCategoryGap={5}
          >
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 11, fill: "rgb(var(--barva-text-slaby))" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="nazev"
              width={sirkaOsy}
              interval={0}
              tick={(vlastnosti: PopisekOsyVlastnosti) => (
                <PopisekOsy {...vlastnosti} data={data} />
              )}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "rgb(var(--barva-plocha-3))" }}
              contentStyle={stylPopisku}
              labelFormatter={(_, payload) =>
                String(payload?.[0]?.payload?.celyNazev ?? "")
              }
              formatter={(h: number) => [formatujCislo(h), "položek"]}
            />
            <Bar
              dataKey="pocet"
              fill="rgb(var(--barva-akcent))"
              radius={[0, 2, 2, 0]}
              maxBarSize={16}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

interface PopisekOsyVlastnosti {
  x?: number | string;
  y?: number | string;
  index?: number;
  payload?: { value: string };
}

function PopisekOsy({
  x,
  y,
  index,
  payload,
  data,
}: PopisekOsyVlastnosti & { data: Hodnota[] }) {
  return (
    <text
      x={Number(x)}
      y={Number(y)}
      dy={4}
      textAnchor="end"
      fontSize={11}
      fill="rgb(var(--barva-text-tlumeny))"
    >
      <title>{data[index ?? 0]?.celyNazev ?? payload?.value}</title>
      {payload?.value}
    </text>
  );
}

function PanelKatalogu({
  katalog,
  nazevJazyka,
}: {
  katalog: DataPrehledu["katalog"];
  nazevJazyka: (kod: string) => string;
}) {
  const k = katalog.kvalita;
  const celkem = katalog.pocet_polozek;
  const jazykyKatalogu = [...katalog.podle_jazyka].sort((a, b) => b.pocet - a.pocet);

  return (
    <Panel
      nadpis="Aktivní katalog"
      popis={
        katalog.nazev_souboru
          ? `${katalog.nazev_souboru} · ${katalog.zdroj === "generovany" ? "vygenerován" : "načten"} ${formatujCas(katalog.importovano)}`
          : "Kmenová data náhradních dílů"
      }
      akce={
        <Link to="/katalog" className="tlacitko-tichy text-xs">
          Katalog <Ikona.Sipka velikost={13} />
        </Link>
      }
    >
      {celkem === 0 ? (
        <p className="text-sm text-textTlumeny">Katalog je prázdný.</p>
      ) : (
        <div className="space-y-3.5">
          <div>
            <p className="nadpis-sekce mb-1.5">Jazyk záznamů</p>
            <div className="space-y-1.5">
              {jazykyKatalogu.length === 0 && (
                <p className="text-xs text-textSlaby">Katalog jazyk záznamů neuvádí.</p>
              )}
              {jazykyKatalogu.map((j) => (
                <PodilovyRadek
                  key={j.nazev}
                  popisek={nazevJazyka(j.nazev)}
                  pocet={j.pocet}
                  celkem={celkem}
                />
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-obrys">
            <p className="nadpis-sekce mb-1.5">Kvalita kmenových dat</p>
            <dl className="space-y-1.5 text-sm">
              <RadekKvality
                popisek="Shodný popis u více položek"
                hodnota={k.se_shodnym_popisem}
                napoveda={`${sklonuj(k.shodnych_popisu, "popis se opakuje", "popisy se opakují", "popisů se opakuje")} doslovně - zjevné duplicity, které deduplikace zachytí vždy.`}
              />
              <RadekKvality popisek="Položky bez popisu" hodnota={k.bez_popisu} />
              {katalog.sloupec_skupiny && (
                <RadekKvality
                  popisek={`Bez hodnoty „${katalog.sloupec_skupiny}“`}
                  hodnota={k.bez_skupiny}
                />
              )}
              <RadekKvality
                popisek="Nezařazeno do třídy ISO 14224"
                hodnota={k.bez_iso_tridy}
                neutralni
                napoveda="Položky, jejichž popis pravidlové zařazení nerozpoznalo. Zařazení lze ověřit na obrazovce Nová položka."
              />
            </dl>
          </div>
        </div>
      )}
    </Panel>
  );
}

function PanelDeduplikace({
  beh,
  slucovani,
}: {
  beh: DataPrehledu["posledni_beh"];
  slucovani: DataPrehledu["slucovani"];
}) {
  const rozhodnuto = slucovani.schvaleno + slucovani.zamitnuto + slucovani.odlozeno;
  const celkem = rozhodnuto + slucovani.ke_kontrole;
  const casti = [
    { popisek: "schváleno", pocet: slucovani.schvaleno, barva: "rgb(var(--barva-uspech))" },
    { popisek: "zamítnuto", pocet: slucovani.zamitnuto, barva: "rgb(var(--barva-chyba))" },
    { popisek: "odloženo", pocet: slucovani.odlozeno, barva: "rgb(var(--barva-vystraha))" },
    { popisek: "ke kontrole", pocet: slucovani.ke_kontrole, barva: "rgb(var(--barva-plocha-3))" },
  ];

  return (
    <Panel
      nadpis="Poslední běh deduplikace"
      akce={
        <Link to="/deduplikace" className="tlacitko-tichy text-xs">
          Podrobnosti <Ikona.Sipka velikost={13} />
        </Link>
      }
    >
      {beh ? (
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
            <Udaj popisek="Dokončeno" hodnota={formatujCas(beh.dokonceno)} />
            <Udaj popisek="Metoda" hodnota={beh.metoda} mono />
            <Udaj
              popisek="Zpracováno položek"
              hodnota={formatujCislo(beh.pocet_polozek)}
              mono
            />
            <Udaj popisek="Doba výpočtu" hodnota={`${beh.doba_s.toFixed(2)} s`} mono />
            <Udaj
              popisek="Nalezeno skupin"
              hodnota={formatujCislo(beh.pocet_klastru)}
              mono
            />
            <Udaj popisek="Spustil" hodnota={beh.spustil ?? "-"} />
          </dl>

          {celkem > 0 && (
            <div className="pt-3 border-t border-obrys">
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="nadpis-sekce">Kontrola skupin správcem dat</span>
                <span className="font-mono text-xs tabular-nums text-textTlumeny">
                  {formatujCislo(rozhodnuto)} z {formatujCislo(celkem)} rozhodnuto
                </span>
              </div>
              <div className="flex h-2 overflow-hidden rounded-xs bg-plocha3">
                {casti.map(
                  (c) =>
                    c.pocet > 0 && (
                      <div
                        key={c.popisek}
                        style={{ width: `${(c.pocet / celkem) * 100}%`, background: c.barva }}
                        title={`${c.popisek}: ${c.pocet}`}
                      />
                    ),
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                {casti.map((c) => (
                  <span key={c.popisek} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-sm" style={{ background: c.barva }} />
                    <span className="text-textTlumeny">{c.popisek}</span>
                    <span className="font-mono tabular-nums text-text">
                      {formatujCislo(c.pocet)}
                    </span>
                  </span>
                ))}
              </div>
              {slucovani.ke_kontrole > 0 && (
                <Link to="/slucovani" className="tlacitko-tichy text-xs mt-2 -ml-1">
                  Pokračovat v kontrole <Ikona.Sipka velikost={13} />
                </Link>
              )}
            </div>
          )}
        </div>
      ) : (
        <PrazdnyStav
          nadpis="Deduplikace dosud neproběhla"
          popis="Spusťte první běh a systém navrhne skupiny duplicitních položek."
          akce={
            <Link to="/deduplikace" className="tlacitko-hlavni">
              <Ikona.Spustit velikost={14} /> Spustit
            </Link>
          }
        />
      )}
    </Panel>
  );
}

function PanelPrekladu({
  preklady,
  nazevJazyka,
}: {
  preklady: DataPrehledu["preklady"];
  nazevJazyka: (kod: string) => string;
}) {
  const sGlosarem = preklady.podle_glosare["s glosářem"];
  const bezGlosare = preklady.podle_glosare["bez glosáře"];

  return (
    <Panel
      nadpis="Dodržení terminologie při překladu"
      popis="Hlavní ukazatel přínosu metody RAG"
      akce={
        <Link to="/preklad" className="tlacitko-tichy text-xs">
          Přeložit text <Ikona.Sipka velikost={13} />
        </Link>
      }
    >
      {preklady.pocet_prekladu > 0 ? (
        <div className="space-y-3.5">
          <PorovnaniDodrzeni
            popisek="S glosářem (RAG)"
            statistika={sGlosarem}
            barva="rgb(var(--barva-uspech))"
          />
          <PorovnaniDodrzeni
            popisek="Bez glosáře"
            statistika={bezGlosare}
            barva="rgb(var(--barva-vystraha))"
          />
          <p className="text-xs text-textTlumeny">
            Podíl výskytů termínů glosáře ve zdrojovém textu, jejichž závazný překlad
            se objevil i ve výsledku. Překlad bez glosáře se měří stejnými termíny,
            model je ale nedostal. Celkem {formatujCislo(preklady.pocet_prekladu)}{" "}
            překladů.
          </p>

          {preklady.posledni.length > 0 && (
            <div className="pt-3 border-t border-obrys">
              <p className="nadpis-sekce mb-1.5">Poslední překlady</p>
              <ul className="space-y-2">
                {preklady.posledni.map((p) => (
                  <li key={p.id} className="text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-textSlaby">
                        {formatujCas(p.vytvoreno)} · {nazevJazyka(p.zdrojovy_jazyk)} →{" "}
                        {nazevJazyka(p.cilovy_jazyk)} ·{" "}
                        {p.pouzity_glosar ? "s glosářem" : "bez glosáře"}
                      </span>
                      {p.mira_dodrzeni !== null && (
                        <span
                          className={`font-mono tabular-nums ${p.mira_dodrzeni >= 1 ? "text-uspech" : "text-chyba"}`}
                        >
                          {formatujProcenta(p.mira_dodrzeni, 0)}
                        </span>
                      )}
                    </div>
                    <p className="text-textTlumeny truncate" title={p.zdroj}>
                      {p.zdroj}
                    </p>
                    <p className="text-text truncate" title={p.preklad}>
                      {p.preklad}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <PrazdnyStav
          nadpis="Zatím neproběhl žádný překlad"
          popis="Po prvním překladu se zde zobrazí srovnání s glosářem a bez něj."
          akce={
            <Link to="/preklad" className="tlacitko-hlavni">
              Přejít k překladu
            </Link>
          }
        />
      )}
    </Panel>
  );
}

function PanelGlosare({
  glosar,
  nazevJazyka,
}: {
  glosar: DataPrehledu["glosar"];
  nazevJazyka: (kod: string) => string;
}) {
  return (
    <Panel
      nadpis="Firemní glosář"
      popis={`${sklonuj(glosar.celkem, "termín", "termíny", "termínů")} v ${sklonuj(glosar.kategorii, "kategorii", "kategoriích", "kategoriích")}`}
      akce={
        <Link to="/glosar" className="tlacitko-tichy text-xs">
          Glosář <Ikona.Sipka velikost={13} />
        </Link>
      }
    >
      <div className="grid md:grid-cols-[minmax(0,14rem)_1fr] gap-x-8 gap-y-4">
        <dl className="space-y-2 text-sm">
          <RadekKvality
            popisek="Termínů s neověřeným překladem"
            hodnota={glosar.neovereno}
            napoveda="Termíny, u nichž některý jazyk doplnil jazykový model a člověk jej zatím neověřil."
          />
          <RadekKvality
            popisek="Ověřených termínů"
            hodnota={glosar.celkem - glosar.neovereno}
            neutralni
          />
        </dl>
        <div>
          <p className="nadpis-sekce mb-1.5">Pokrytí jazyků</p>
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
            {Object.entries(glosar.pokryti).map(([kod, pocet]) => (
              <PodilovyRadek
                key={kod}
                popisek={nazevJazyka(kod)}
                pocet={pocet}
                celkem={glosar.celkem}
              />
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

const stylPopisku = {
  background: "rgb(var(--barva-plocha))",
  border: "1px solid rgb(var(--barva-obrys))",
  borderRadius: 4,
  fontSize: 12,
  color: "rgb(var(--barva-text))",
  boxShadow: "0 8px 24px -12px rgb(0 0 0 / 0.3)",
};

function Udaj({
  popisek,
  hodnota,
  mono,
}: {
  popisek: string;
  hodnota: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="nadpis-sekce">{popisek}</dt>
      <dd className={`mt-0.5 text-text ${mono ? "font-mono tabular-nums" : ""}`}>
        {hodnota}
      </dd>
    </div>
  );
}

function RadekStavu({
  popisek,
  hodnota,
  vPoradku,
}: {
  popisek: string;
  hodnota: string;
  vPoradku: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-textTlumeny">{popisek}</dt>
      <dd className="flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            vPoradku ? "bg-uspech" : "bg-chyba"
          }`}
        />
        <span className="font-mono text-[0.8125rem] text-text">{hodnota}</span>
      </dd>
    </div>
  );
}

function RadekKvality({
  popisek,
  hodnota,
  napoveda,
  neutralni,
}: {
  popisek: string;
  hodnota: number;
  napoveda?: string;
  neutralni?: boolean;
}) {
  const barva = neutralni || hodnota === 0 ? "text-text" : "text-vystraha";
  return (
    <div className="flex items-center justify-between gap-3" title={napoveda}>
      <dt className="text-textTlumeny">{popisek}</dt>
      <dd className={`font-mono text-[0.8125rem] tabular-nums ${barva}`}>
        {formatujCislo(hodnota)}
      </dd>
    </div>
  );
}

function PodilovyRadek({
  popisek,
  pocet,
  celkem,
}: {
  popisek: string;
  pocet: number;
  celkem: number;
}) {
  const podil = celkem ? pocet / celkem : 0;
  return (
    <div className="grid grid-cols-[6.5rem_1fr_3.5rem] items-center gap-2 text-xs">
      <span className="text-textTlumeny truncate">{popisek}</span>
      <div className="ukazatel h-1.5">
        <div className="ukazatel-vypln" style={{ width: `${podil * 100}%` }} />
      </div>
      <span className="font-mono tabular-nums text-text text-right">
        {formatujCislo(pocet)}
      </span>
    </div>
  );
}

function PorovnaniDodrzeni({
  popisek,
  statistika,
  barva,
}: {
  popisek: string;
  statistika: StatistikaPrekladu | undefined;
  barva: string;
}) {
  const merena = statistika && statistika.ocekavano > 0;
  const hodnota = merena ? statistika.prumerne_dodrzeni : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-sm text-text">{popisek}</span>
        <span className="font-mono text-sm tabular-nums text-text">
          {merena ? formatujProcenta(hodnota) : "-"}
          <span className="ml-2 text-xs text-textSlaby">
            {merena
              ? `${formatujCislo(statistika.dodrzeno)} z ${formatujCislo(statistika.ocekavano)} výskytů · ${formatujCislo(statistika.pocet)}×`
              : `${formatujCislo(statistika?.pocet ?? 0)}× · bez měřitelného termínu`}
          </span>
        </span>
      </div>
      <div className="ukazatel h-2">
        <div
          className="ukazatel-vypln"
          style={{ width: `${hodnota * 100}%`, background: barva }}
        />
      </div>
      {merena && statistika.nespravnych_variant > 0 && (
        <p className="mt-1 text-xs text-chyba">
          {statistika.nespravnych_variant}× použita zakázaná varianta
        </p>
      )}
    </div>
  );
}
