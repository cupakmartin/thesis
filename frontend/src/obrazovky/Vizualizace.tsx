import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { useNacti } from "../hooky";
import {
  ChybovyStav,
  Metrika,
  Nacitani,
  Panel,
  ZahlaviObrazovky,
  formatujCislo,
} from "../komponenty";

const PALETA = [
  "#0b6f80", "#c77700", "#2e7d4f", "#b02722", "#6b4fa0",
  "#0f8fa8", "#a35c00", "#3f7d20", "#8c2f6d", "#1f6f9f",
  "#7a6a1f", "#4a5568", "#9c3d54",
];

interface Bod {
  itemnum: string;
  popis: string;
  skupina: string;
  trida: string;
  x: number;
  y: number;
}

export default function Vizualizace() {
  const [metoda, nastavMetodu] = useState<"pca" | "tsne">("pca");
  const [vzorek, nastavVzorek] = useState(800);
  const [prah, nastavPrah] = useState(0.72);

  const projekce = useNacti(() => zavolejProjekci(metoda, vzorek), [metoda, vzorek]);
  const rozlozeni = useNacti(() => zavolejRozlozeni(), []);

  const skupiny = Array.from(
    new Set((projekce.data?.body ?? []).map((b) => b.skupina)),
  ).sort();

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Vektorový prostor"
      />

      <div className="grid xl:grid-cols-[1fr_minmax(0,21rem)] gap-4 items-start">
        <Panel
          nadpis="Mapa vektorového prostoru"
          popis={
            projekce.data
              ? `${formatujCislo(projekce.data.pocet)} položek, metoda ${projekce.data.metoda.toUpperCase()}`
              : undefined
          }
          akce={
            <div className="flex items-center gap-2">
              <select
                className="pole w-auto py-1 text-[0.8125rem]"
                value={metoda}
                onChange={(e) => nastavMetodu(e.target.value as "pca" | "tsne")}
              >
                <option value="pca">PCA - rychlé</option>
                <option value="tsne">t-SNE - přesnější shluky</option>
              </select>
              <select
                className="pole w-auto py-1 text-[0.8125rem]"
                value={vzorek}
                onChange={(e) => nastavVzorek(Number(e.target.value))}
              >
                <option value={400}>400 položek</option>
                <option value={800}>800 položek</option>
                <option value={1500}>1500 položek</option>
              </select>
            </div>
          }
        >
          {projekce.nacita ? (
            <Nacitani
              text={
                metoda === "tsne"
                  ? "Počítám t-SNE - může trvat desítky sekund…"
                  : "Počítám projekci…"
              }
            />
          ) : projekce.chyba ? (
            <ChybovyStav zprava={projekce.chyba} naObnoveni={projekce.obnov} />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={430}>
                <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                  <CartesianGrid
                    stroke="rgb(var(--barva-obrys))"
                    strokeDasharray="2 4"
                  />
                  <XAxis
                    type="number"
                    dataKey="x"
                    domain={[-1.05, 1.05]}
                    tick={false}
                    axisLine={false}
                    label={{
                      value: "1. hlavní komponenta",
                      position: "insideBottom",
                      offset: -2,
                      style: {
                        fill: "rgb(var(--barva-text-slaby))",
                        fontSize: 11,
                      },
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    domain={[-1.05, 1.05]}
                    tick={false}
                    axisLine={false}
                  />
                  <ZAxis range={[26, 26]} />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={({ payload }) => {
                      const bod = payload?.[0]?.payload as Bod | undefined;
                      if (!bod) return null;
                      return (
                        <div className="panel px-3 py-2 shadow-vyzdvih max-w-xs">
                          <p className="font-mono text-2xs text-textTlumeny">
                            {bod.itemnum}
                          </p>
                          <p className="text-sm text-text">{bod.popis}</p>
                          <p className="mt-1 text-2xs text-textSlaby">
                            {bod.skupina} · ISO {bod.trida}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Scatter data={projekce.data?.body ?? []} fillOpacity={0.72}>
                    {(projekce.data?.body ?? []).map((b, i) => (
                      <Cell
                        key={i}
                        fill={PALETA[skupiny.indexOf(b.skupina) % PALETA.length]}
                      />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>

              <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 pt-3 border-t border-obrys">
                {skupiny.map((s, i) => (
                  <span key={s} className="flex items-center gap-1.5 text-xs">
                    <span
                      className="h-2 w-2 rounded-sm"
                      style={{ background: PALETA[i % PALETA.length] }}
                    />
                    <span className="text-textTlumeny">{s}</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel nadpis="Jak číst tento obrázek">
            <p className="text-sm text-textTlumeny leading-relaxed">
              Každý bod je jedna položka katalogu, barva označuje hodnotu
              sloupce „{projekce.data?.barva_podle ?? "skupina"}“. Body ležící blízko sebe mají podobný význam popisu.
              Vzniká-li pro každou skupinu souvislá oblast, znamená to, že model
              zachycuje význam textu - a právě na tom stojí schopnost rozpoznat
              duplicitu napříč jazyky.
            </p>
            {projekce.data?.vysvetlena_variance && (
              <p className="mt-3 pt-3 border-t border-obrys text-xs text-textSlaby">
                Zobrazené dvě komponenty vysvětlují{" "}
                <span className="font-mono text-textTlumeny">
                  {(
                    projekce.data.vysvetlena_variance.reduce((a, b) => a + b, 0) *
                    100
                  ).toFixed(1)}{" "}
                  %
                </span>{" "}
                celkového rozptylu. Zbytek informace se do roviny nevejde -
                obrázek je proto orientační.
              </p>
            )}
          </Panel>

          {rozlozeni.data && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Metrika
                  popisek="Průměrná podobnost"
                  hodnota={rozlozeni.data.prumer.toFixed(3)}
                />
                <Metrika
                  popisek="Medián"
                  hodnota={rozlozeni.data.median.toFixed(3)}
                />
              </div>

              <Panel
                nadpis="Rozložení podobností"
                popis="Nejbližší sousedé napříč katalogem"
              >
                <ResponsiveContainer width="100%" height={188}>
                  <BarChart data={rozlozeni.data.sloupce}>
                    <XAxis
                      dataKey="stred"
                      tick={{ fontSize: 10, fill: "rgb(var(--barva-text-slaby))" }}
                      axisLine={false}
                      tickLine={false}
                      interval={4}
                    />
                    <YAxis hide />
                    <Tooltip
                      cursor={{ fill: "rgb(var(--barva-plocha-3))" }}
                      contentStyle={{
                        background: "rgb(var(--barva-plocha))",
                        border: "1px solid rgb(var(--barva-obrys))",
                        borderRadius: 4,
                        fontSize: 12,
                      }}
                      formatter={(h: number) => [formatujCislo(h), "dvojic"]}
                      labelFormatter={(l) => `podobnost ≈ ${l}`}
                    />
                    <ReferenceLine
                      x={prah}
                      stroke="rgb(var(--barva-chyba))"
                      strokeDasharray="4 3"
                    />
                    <Bar dataKey="pocet" radius={[2, 2, 0, 0]}>
                      {rozlozeni.data.sloupce.map((s, i) => (
                        <Cell
                          key={i}
                          fill={
                            s.stred >= prah
                              ? "rgb(var(--barva-akcent))"
                              : "rgb(var(--barva-obrys-2))"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>

                <div className="mt-3">
                  <label className="stitek-pole">
                    Práh - <span className="font-mono">{prah.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    className="w-full accent-akcent"
                    min={0.3}
                    max={0.95}
                    step={0.01}
                    value={prah}
                    onChange={(e) => nastavPrah(Number(e.target.value))}
                  />
                  <p className="mt-1.5 text-xs text-textSlaby">
                    Zvýrazněná část odpovídá dvojicím nad prahem. Rozložení je
                    spojité - neexistuje mezera, která by práh určila sama.
                    Proto je nutná druhá, atributová fáze rozhodování.
                  </p>
                </div>
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}

async function zavolejProjekci(metoda: string, vzorek: number) {
  const odpoved = await fetch(
    `/api/vizualizace/projekce?metoda=${metoda}&vzorek=${vzorek}`,
  );
  if (!odpoved.ok) throw new Error("Projekci se nepodařilo spočítat.");
  return (await odpoved.json()) as {
    metoda: string;
    pocet: number;
    vysvetlena_variance: number[] | null;
    barva_podle?: string;
    body: Bod[];
  };
}

async function zavolejRozlozeni() {
  const odpoved = await fetch("/api/vizualizace/rozlozeni-podobnosti");
  if (!odpoved.ok) throw new Error("Rozložení se nepodařilo spočítat.");
  return (await odpoved.json()) as {
    pocet_hodnot: number;
    prumer: number;
    median: number;
    sloupce: { od: number; do: number; stred: number; pocet: number }[];
  };
}
