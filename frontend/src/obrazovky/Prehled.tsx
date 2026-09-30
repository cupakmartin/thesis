import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { useNacti } from "../hooky";
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
} from "../komponenty";

const BARVY_GRAFU = [
  "rgb(var(--barva-akcent))",
  "rgb(var(--barva-vystraha))",
  "rgb(var(--barva-uspech))",
  "rgb(var(--barva-chyba))",
];

export default function Prehled() {
  const prehled = useNacti(() => api.system.prehled(), []);
  const stav = useNacti(() => api.system.stav(), []);

  if (prehled.nacita) return <Nacitani text="Načítám přehled…" />;
  if (prehled.chyba)
    return <ChybovyStav zprava={prehled.chyba} naObnoveni={prehled.obnov} />;
  if (!prehled.data) return null;

  const { katalog, posledni_beh, slucovani, preklady } = prehled.data;
  const dodrzeniSGlosarem = preklady.podle_glosare["s glosářem"];
  const dodrzeniBezGlosare = preklady.podle_glosare["bez glosáře"];

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
          napoveda="Celkový počet záznamů kmenových dat."
        />
        <Metrika
          popisek="Nalezených skupin"
          hodnota={posledni_beh ? formatujCislo(posledni_beh.pocet_klastru) : "—"}
          zvyrazneni="akcent"
          napoveda="Skupiny záznamů označené jako tentýž fyzický díl."
        />
        <Metrika
          popisek="Nadbytečných záznamů"
          hodnota={posledni_beh ? formatujCislo(posledni_beh.pocet_duplicit) : "—"}
          zvyrazneni="vystraha"
          napoveda="Záznamy nad rámec jednoho referenčního v každé skupině."
        />
        <Metrika
          popisek="Schváleno ke sloučení"
          hodnota={formatujCislo(slucovani.sloucenych_zaznamu)}
          zvyrazneni="uspech"
          napoveda="Záznamy, u nichž správce dat sloučení potvrdil."
        />
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <Panel
          nadpis="Rozložení podle komoditní skupiny"
          popis="Struktura katalogu náhradních dílů"
          trida="xl:col-span-2"
        >
          <ResponsiveContainer width="100%" height={272}>
            <BarChart
              data={katalog.podle_komoditni_skupiny}
              layout="vertical"
              margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
            >
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "rgb(var(--barva-text-slaby))" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="nazev"
                width={104}
                tick={{ fontSize: 11, fill: "rgb(var(--barva-text-tlumeny))" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgb(var(--barva-plocha-3))" }}
                contentStyle={stylPopisku}
                formatter={(h: number) => [formatujCislo(h), "položek"]}
              />
              <Bar
                dataKey="pocet"
                fill="rgb(var(--barva-akcent))"
                radius={[0, 2, 2, 0]}
                maxBarSize={15}
              />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <div className="space-y-4">
          <Panel nadpis="Jazyk záznamů" popis="Zdroj jazykové bariéry v katalogu">
            <ResponsiveContainer width="100%" height={140}>
              <PieChart>
                <Pie
                  data={katalog.podle_jazyka}
                  dataKey="pocet"
                  nameKey="nazev"
                  innerRadius={38}
                  outerRadius={62}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {katalog.podle_jazyka.map((_, i) => (
                    <Cell key={i} fill={BARVY_GRAFU[i % BARVY_GRAFU.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={stylPopisku}
                  formatter={(h: number) => [formatujCislo(h), "položek"]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 text-xs">
              {katalog.podle_jazyka.map((j, i) => (
                <span key={j.nazev} className="flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ background: BARVY_GRAFU[i % BARVY_GRAFU.length] }}
                  />
                  <span className="text-textTlumeny">
                    {j.nazev === "CS" ? "čeština" : "angličtina"}
                  </span>
                  <span className="font-mono tabular-nums text-text">
                    {formatujCislo(j.pocet)}
                  </span>
                </span>
              ))}
            </div>
          </Panel>

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
        <Panel
          nadpis="Poslední běh deduplikace"
          akce={
            <Link to="/deduplikace" className="tlacitko-tichy text-xs">
              Podrobnosti <Ikona.Sipka velikost={13} />
            </Link>
          }
        >
          {posledni_beh ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
              <Udaj popisek="Dokončeno" hodnota={formatujCas(posledni_beh.dokonceno)} />
              <Udaj popisek="Metoda" hodnota={posledni_beh.metoda} mono />
              <Udaj
                popisek="Zpracováno položek"
                hodnota={formatujCislo(posledni_beh.pocet_polozek)}
                mono
              />
              <Udaj
                popisek="Doba výpočtu"
                hodnota={`${posledni_beh.doba_s.toFixed(2)} s`}
                mono
              />
              <Udaj
                popisek="Nalezeno skupin"
                hodnota={formatujCislo(posledni_beh.pocet_klastru)}
                mono
              />
              <Udaj popisek="Spustil" hodnota={posledni_beh.spustil ?? "—"} />
            </dl>
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
                hodnota={dodrzeniSGlosarem?.prumerne_dodrzeni ?? 0}
                pocet={dodrzeniSGlosarem?.pocet ?? 0}
                barva="rgb(var(--barva-uspech))"
              />
              <PorovnaniDodrzeni
                popisek="Bez glosáře"
                hodnota={dodrzeniBezGlosare?.prumerne_dodrzeni ?? 0}
                pocet={dodrzeniBezGlosare?.pocet ?? 0}
                barva="rgb(var(--barva-vystraha))"
              />
              <p className="text-xs text-textTlumeny pt-1 border-t border-obrys">
                Podíl termínů firemního glosáře, které se ve výsledném překladu
                skutečně objevily. Celkem {formatujCislo(preklady.pocet_prekladu)}{" "}
                překladů.
              </p>
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
      </div>
    </>
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

function PorovnaniDodrzeni({
  popisek,
  hodnota,
  pocet,
  barva,
}: {
  popisek: string;
  hodnota: number;
  pocet: number;
  barva: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-sm text-text">{popisek}</span>
        <span className="font-mono text-sm tabular-nums text-text">
          {pocet > 0 ? formatujProcenta(hodnota) : "—"}
          <span className="ml-2 text-xs text-textSlaby">
            {formatujCislo(pocet)}×
          </span>
        </span>
      </div>
      <div className="ukazatel h-2">
        <div
          className="ukazatel-vypln"
          style={{ width: `${hodnota * 100}%`, background: barva }}
        />
      </div>
    </div>
  );
}
