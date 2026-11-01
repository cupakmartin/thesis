import { useState } from "react";
import { ZAKLAD } from "../api";
import { useJazyky } from "../hooky";
import {
  ChybovyStav,
  Kod,
  Metrika,
  Nacitani,
  Panel,
  VolbaJazyka,
  ZahlaviObrazovky,
} from "../komponenty";

interface Vektor {
  dimenze: number;
  prvnich_n: number[];
  norma: number;
  nejmensi: number;
  nejvetsi: number;
}

interface Krok {
  poradi: number;
  nazev: string;
  popis: string;
  doba_ms: number;
  udaje: Record<string, unknown>;
}

interface ZaznamPrekladu {
  vstup: string;
  vystup: string;
  model: string;
  doba_celkem_ms: number;
  kroky: Krok[];
}

interface ZaznamPodobnosti {
  prvni: { text: string; vektor: Vektor };
  druhy: { text: string; vektor: Vektor };
  kosinova_podobnost: number;
  skalarni_soucin: number;
  model: string;
  doba_ms: number;
  prah_kandidatu: number;
}

async function posli<T>(cesta: string, telo: unknown): Promise<T> {
  const odpoved = await fetch(`${ZAKLAD}${cesta}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(telo),
  });
  if (!odpoved.ok) {
    const chyba = await odpoved.json().catch(() => ({}));
    throw new Error(chyba.detail ?? `Požadavek selhal (${odpoved.status}).`);
  }
  return (await odpoved.json()) as T;
}

export default function Prubeh() {
  return (
    <div className="space-y-5">
      <ZahlaviObrazovky
        nadpis="Průběh zpracování"
      />
      <VektoroveJadro />
      <PrekladKrokPoKroku />
    </div>
  );
}

function VektoroveJadro() {
  const [prvni, nastavPrvni] = useState("Ložisko kuličkové 6204 2RS");
  const [druhy, nastavDruhy] = useState("Ball bearing 6204 2RS");
  const [data, nastavData] = useState<ZaznamPodobnosti | null>(null);
  const [probiha, nastavProbiha] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);

  async function spust() {
    nastavProbiha(true);
    nastavChybu(null);
    try {
      nastavData(await posli<ZaznamPodobnosti>("/prubeh/podobnost", { prvni, druhy }));
    } catch (e) {
      nastavChybu(e instanceof Error ? e.message : String(e));
    } finally {
      nastavProbiha(false);
    }
  }

  return (
    <Panel
      nadpis="Vektorová podobnost dvou textů"
      popis="Sémantické porovnání je výpočet nad vektory, nikoli tabulka připravených dvojic"
    >
      <div className="p-3 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="stitek-pole" htmlFor="text-prvni">
              První text
            </label>
            <input
              id="text-prvni"
              className="pole"
              value={prvni}
              onChange={(e) => nastavPrvni(e.target.value)}
            />
          </div>
          <div>
            <label className="stitek-pole" htmlFor="text-druhy">
              Druhý text
            </label>
            <input
              id="text-druhy"
              className="pole"
              value={druhy}
              onChange={(e) => nastavDruhy(e.target.value)}
            />
          </div>
        </div>

        <button
          className="tlacitko-hlavni"
          onClick={() => void spust()}
          disabled={probiha || !prvni.trim() || !druhy.trim()}
        >
          {probiha ? "Počítám…" : "Spočítat podobnost"}
        </button>

        {chyba && <ChybovyStav zprava={chyba} />}
        {probiha && <Nacitani text="Počítám vektory…" />}

        {data && !probiha && (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metrika
                popisek="Kosinová podobnost"
                hodnota={data.kosinova_podobnost.toFixed(4)}
              />
              <Metrika
                popisek="Práh pro kandidáty"
                hodnota={data.prah_kandidatu?.toFixed(2) ?? "-"}
              />
              <Metrika popisek="Doba výpočtu" hodnota={`${data.doba_ms} ms`} />
            </div>

            <p className="text-xs text-textTlumeny">
              Vektor má {data.prvni.vektor.dimenze} složek; níže je prvních{" "}
              {data.prvni.vektor.prvnich_n.length}. Model{" "}
              <Kod>{data.model}</Kod> je normalizuje na jednotkovou délku, takže
              kosinová podobnost odpovídá skalárnímu součinu (
              {data.skalarni_soucin.toFixed(4)}).
            </p>

            {[data.prvni, data.druhy].map((strana, i) => (
              <div key={i} className="panel p-2.5">
                <p className="text-sm mb-1">{strana.text}</p>
                <p className="font-mono text-2xs text-textTlumeny break-all">
                  [{strana.vektor.prvnich_n.map((h) => h.toFixed(5)).join(", ")}, …]
                </p>
                <p className="text-2xs text-textSlaby mt-1">
                  norma {strana.vektor.norma.toFixed(4)} · rozsah{" "}
                  {strana.vektor.nejmensi.toFixed(4)} až{" "}
                  {strana.vektor.nejvetsi.toFixed(4)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

function PrekladKrokPoKroku() {
  const [text, nastavText] = useState(
    "Replace the impeller and seal on the centrifugal pump.",
  );
  const [data, nastavData] = useState<ZaznamPrekladu | null>(null);
  const [probiha, nastavProbiha] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);
  const [zdrojovy, nastavZdrojovy] = useState("en");
  const [cilovy, nastavCilovy] = useState("cs");
  const jazyky = useJazyky();

  async function spust() {
    nastavProbiha(true);
    nastavChybu(null);
    try {
      nastavData(
        await posli<ZaznamPrekladu>("/prubeh/preklad", {
          text,
          zdrojovy_jazyk: zdrojovy,
          cilovy_jazyk: cilovy,
        }),
      );
    } catch (e) {
      nastavChybu(e instanceof Error ? e.message : String(e));
    } finally {
      nastavProbiha(false);
    }
  }

  return (
    <Panel
      nadpis="Překlad krok po kroku"
      popis="Kroky od vstupu k výsledku, každý s vlastním měřením"
    >
      <div className="p-3 space-y-3">
        <div className="flex items-end gap-2">
          <VolbaJazyka
            id="prubeh-zdroj"
            popisek="Z jazyka"
            hodnota={zdrojovy}
            jazyky={jazyky}
            naZmenu={nastavZdrojovy}
          />
          <VolbaJazyka
            id="prubeh-cil"
            popisek="Do jazyka"
            hodnota={cilovy}
            jazyky={jazyky}
            naZmenu={nastavCilovy}
          />
        </div>
        <div>
          <label className="stitek-pole" htmlFor="prubeh-text">
            Text k překladu
          </label>
          <textarea
            id="prubeh-text"
            className="pole"
            rows={2}
            value={text}
            onChange={(e) => nastavText(e.target.value)}
          />
        </div>

        <button
          className="tlacitko-hlavni"
          onClick={() => void spust()}
          disabled={probiha || !text.trim() || zdrojovy === cilovy}
        >
          {probiha ? "Zpracovávám…" : "Zpracovat a zaznamenat průběh"}
        </button>

        {chyba && <ChybovyStav zprava={chyba} />}
        {probiha && <Nacitani text="Probíhá zpracování…" />}

        {data && !probiha && (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metrika popisek="Model" hodnota={data.model} />
              <Metrika popisek="Celkem" hodnota={`${Math.round(data.doba_celkem_ms)} ms`} />
              <Metrika popisek="Kroků" hodnota={data.kroky.length} />
            </div>

            <div className="panel p-2.5">
              <p className="stitek-pole">Výsledek</p>
              <p className="text-sm">{data.vystup}</p>
            </div>

            {data.kroky.map((krok) => (
              <ZobrazKrok key={krok.poradi} krok={krok} />
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

function ZobrazKrok({ krok }: { krok: Krok }) {
  const [rozbaleno, nastavRozbaleno] = useState(false);
  return (
    <div className="panel">
      <button
        className="w-full text-left px-3 py-2 flex items-baseline justify-between gap-3"
        onClick={() => nastavRozbaleno(!rozbaleno)}
      >
        <span className="text-sm">
          <span className="font-mono text-textSlaby mr-2">{krok.poradi}.</span>
          {krok.nazev}
        </span>
        <span className="font-mono text-2xs text-textTlumeny shrink-0">
          {krok.doba_ms.toFixed(2)} ms {rozbaleno ? "▲" : "▼"}
        </span>
      </button>
      {rozbaleno && (
        <div className="border-t border-obrys px-3 py-2 space-y-2">
          <p className="text-xs text-textTlumeny">{krok.popis}</p>
          <UdajeKroku udaje={krok.udaje} />
        </div>
      )}
    </div>
  );
}

function UdajeKroku({ udaje }: { udaje: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      {Object.entries(udaje).map(([klic, hodnota]) => {
        if (klic === "zpravy" && Array.isArray(hodnota)) {
          return (
            <div key={klic} className="space-y-2">
              {(hodnota as { role: string; obsah: string }[]).map((z, i) => (
                <div key={i}>
                  <p className="stitek-pole">role: {z.role}</p>
                  <pre className="font-mono text-2xs whitespace-pre-wrap bg-plocha2 border border-obrys p-2 max-h-64 overflow-y-auto">
                    {z.obsah}
                  </pre>
                </div>
              ))}
            </div>
          );
        }

        if (klic === "terminy" && Array.isArray(hodnota)) {
          const terminy = hodnota as {
            zdroj: string;
            cil: string;
            skore: number;
            zpusob: string;
          }[];
          return (
            <table key={klic} className="tabulka">
              <thead>
                <tr>
                  <th>Termín ve zdroji</th>
                  <th>Závazný překlad</th>
                  <th>Skóre</th>
                  <th>Způsob nalezení</th>
                </tr>
              </thead>
              <tbody>
                {terminy.map((t, i) => (
                  <tr key={i}>
                    <td>{t.zdroj}</td>
                    <td>{t.cil}</td>
                    <td className="font-mono">{t.skore.toFixed(4)}</td>
                    <td>{t.zpusob}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }

        if (klic === "vektor" && hodnota && typeof hodnota === "object") {
          const v = hodnota as Vektor;
          return (
            <div key={klic}>
              <p className="stitek-pole">
                vektor - {v.dimenze} složek, norma {v.norma.toFixed(4)}
              </p>
              <p className="font-mono text-2xs break-all text-textTlumeny">
                [{v.prvnich_n.map((h) => h.toFixed(5)).join(", ")}, …]
              </p>
            </div>
          );
        }

        return (
          <div key={klic} className="flex flex-wrap gap-2 text-xs">
            <span className="text-textSlaby shrink-0">{klic}:</span>
            <span className="font-mono break-all">
              {typeof hodnota === "object"
                ? JSON.stringify(hodnota)
                : String(hodnota)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
