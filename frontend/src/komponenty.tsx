import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import type { Postup } from "./api";

type VlastnostiIkony = { velikost?: number; trida?: string };

const znacka =
  (znak: string) =>
  ({ trida }: VlastnostiIkony = {}) => (
    <span aria-hidden className={trida}>
      {znak}
    </span>
  );

const zadna = (_: VlastnostiIkony = {}) => null;

export const Ikona = {
  Prehled: zadna,
  Katalog: zadna,
  Deduplikace: zadna,
  Nova: zadna,
  Slouceni: zadna,
  Preklad: zadna,
  Glosar: zadna,
  Vizualizace: zadna,
  Maximo: zadna,
  Slunce: zadna,
  Mesic: zadna,

  // Značky nesoucí význam.
  Sipka: znacka("→"),
  Krizek: znacka("×"),
  Fajfka: znacka("✓"),
  Vystraha: znacka("!"),
  Obnovit: zadna,
  Stahnout: zadna,
  Spustit: zadna,
  Info: znacka("i"),
};

export function Panel({
  nadpis,
  popis,
  akce,
  children,
  trida = "",
  bezOdsazeni = false,
}: {
  nadpis?: ReactNode;
  popis?: ReactNode;
  akce?: ReactNode;
  children: ReactNode;
  trida?: string;
  bezOdsazeni?: boolean;
}) {
  return (
    <section className={`panel ${trida}`}>
      {(nadpis || akce) && (
        <header className="panel-hlavicka">
          <div className="min-w-0">
            {nadpis && (
              <h2 className="text-sm font-semibold text-text truncate">{nadpis}</h2>
            )}
            {popis && (
              <p className="text-xs text-textTlumeny mt-0.5">{popis}</p>
            )}
          </div>
          {akce && <div className="flex items-center gap-2 shrink-0">{akce}</div>}
        </header>
      )}
      <div className={bezOdsazeni ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function ZahlaviObrazovky({
  nadpis,
  akce,
}: {
  nadpis: string;
  akce?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-text">{nadpis}</h1>
      </div>
      {akce && <div className="flex items-center gap-2 shrink-0">{akce}</div>}
    </div>
  );
}

export function Nacitani({ text = "Načítám…" }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-14 text-sm text-textTlumeny">
      <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-obrys2 border-t-akcent animate-spin" />
      {text}
    </div>
  );
}

export function ChybovyStav({
  zprava,
  naObnoveni,
}: {
  zprava: string;
  naObnoveni?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <span className="text-chyba">
        <Ikona.Vystraha velikost={26} />
      </span>
      <p className="text-sm text-text max-w-md">{zprava}</p>
      {naObnoveni && (
        <button className="tlacitko-vedlejsi" onClick={naObnoveni}>
          <Ikona.Obnovit /> Zkusit znovu
        </button>
      )}
    </div>
  );
}

export function PrazdnyStav({
  nadpis,
  popis,
  akce,
}: {
  nadpis: string;
  popis?: string;
  akce?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2.5 py-14 text-center">
      <p className="text-sm font-medium text-text">{nadpis}</p>
      {popis && <p className="text-sm text-textTlumeny max-w-md">{popis}</p>}
      {akce && <div className="mt-2">{akce}</div>}
    </div>
  );
}

export function barvaSkore(hodnota: number): string {
  if (hodnota >= 0.85) return "rgb(var(--barva-uspech))";
  if (hodnota >= 0.7) return "rgb(var(--barva-akcent))";
  if (hodnota >= 0.55) return "rgb(var(--barva-vystraha))";
  return "rgb(var(--barva-chyba))";
}

export function Skore({
  hodnota,
  popisek,
  sirka = 68,
}: {
  hodnota: number;
  popisek?: string;
  sirka?: number;
}) {
  const procenta = Math.max(0, Math.min(1, hodnota)) * 100;
  return (
    <div className="flex items-center gap-2" title={popisek}>
      <div className="ukazatel" style={{ width: sirka }}>
        <div
          className="ukazatel-vypln"
          style={{ width: `${procenta}%`, background: barvaSkore(hodnota) }}
        />
      </div>
      <span className="font-mono text-[0.8125rem] tabular-nums text-textTlumeny">
        {hodnota.toFixed(3)}
      </span>
    </div>
  );
}

export function Metrika({
  popisek,
  hodnota,
  jednotka,
  napoveda,
  zvyrazneni,
}: {
  popisek: string;
  hodnota: ReactNode;
  jednotka?: string;
  napoveda?: string;
  zvyrazneni?: "akcent" | "uspech" | "vystraha" | "chyba";
}) {
  const barvy = {
    akcent: "text-akcent",
    uspech: "text-uspech",
    vystraha: "text-vystraha",
    chyba: "text-chyba",
  };
  return (
    <div className="panel p-3.5" title={napoveda}>
      <p className="nadpis-sekce">{popisek}</p>
      <p
        className={`mt-1.5 font-mono text-2xl font-semibold tabular-nums leading-none ${
          zvyrazneni ? barvy[zvyrazneni] : "text-text"
        }`}
      >
        {hodnota}
        {jednotka && (
          <span className="ml-1 text-sm font-normal text-textSlaby">{jednotka}</span>
        )}
      </p>
    </div>
  );
}

export function Kod({ children }: { children: ReactNode }) {
  return <span className="kod">{children}</span>;
}

export function OdznakJazyka({ kod }: { kod: string | null }) {
  if (!kod) return null;
  return (
    <span className="odznak-neutralni" title={kod === "CS" ? "čeština" : "angličtina"}>
      {kod}
    </span>
  );
}

export function OdznakStavu({ stav }: { stav: string }) {
  const mapa: Record<string, { trida: string; text: string }> = {
    ke_kontrole: { trida: "odznak-akcent", text: "ke kontrole" },
    schvaleno: { trida: "odznak-uspech", text: "schváleno" },
    zamitnuto: { trida: "odznak-chyba", text: "zamítnuto" },
    odlozeno: { trida: "odznak-vystraha", text: "odloženo" },
    aktivni: { trida: "odznak-neutralni", text: "aktivní" },
    slouceno: { trida: "odznak-uspech", text: "sloučeno" },
    ACTIVE: { trida: "odznak-uspech", text: "aktivní" },
    PENDING: { trida: "odznak-vystraha", text: "čeká" },
    OBSOLETE: { trida: "odznak-neutralni", text: "vyřazeno" },
  };
  const nastaveni = mapa[stav] ?? { trida: "odznak-neutralni", text: stav };
  return <span className={nastaveni.trida}>{nastaveni.text}</span>;
}

export function Strankovac({
  celkem,
  limit,
  odsazeni,
  naZmenu,
}: {
  celkem: number;
  limit: number;
  odsazeni: number;
  naZmenu: (odsazeni: number) => void;
}) {
  const stranka = Math.floor(odsazeni / limit) + 1;
  const stranek = Math.max(1, Math.ceil(celkem / limit));
  if (celkem === 0) return null;

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5 border-t border-obrys text-sm">
      <p className="text-textTlumeny tabular-nums">
        {odsazeni + 1}–{Math.min(odsazeni + limit, celkem)} z{" "}
        <span className="font-medium text-text">{celkem.toLocaleString("cs-CZ")}</span>
      </p>
      <div className="flex items-center gap-1.5">
        <button
          className="tlacitko-vedlejsi px-2 py-1"
          disabled={odsazeni === 0}
          onClick={() => naZmenu(Math.max(0, odsazeni - limit))}
        >
          Předchozí
        </button>
        <span className="px-2 font-mono text-[0.8125rem] tabular-nums text-textTlumeny">
          {stranka} / {stranek}
        </span>
        <button
          className="tlacitko-vedlejsi px-2 py-1"
          disabled={odsazeni + limit >= celkem}
          onClick={() => naZmenu(odsazeni + limit)}
        >
          Další
        </button>
      </div>
    </div>
  );
}

export type DruhOznameni = "uspech" | "chyba" | "informace";

export function Oznameni({
  druh,
  zprava,
  naZavreni,
}: {
  druh: DruhOznameni;
  zprava: string;
  naZavreni: () => void;
}) {
  useEffect(() => {
    const casovac = setTimeout(naZavreni, druh === "chyba" ? 8000 : 4500);
    return () => clearTimeout(casovac);
  }, [naZavreni, druh]);

  const styl = {
    uspech: "border-uspech/40 bg-uspechTlumeny text-uspech",
    chyba: "border-chyba/40 bg-chybaTlumena text-chyba",
    informace: "border-akcent/40 bg-akcentTlumeny text-akcent",
  }[druh];

  return (
    <div
      role="status"
      className={`animate-nastup flex items-start gap-2.5 rounded-md border px-3.5 py-2.5 shadow-vyzdvih ${styl}`}
    >
      <span className="mt-0.5 shrink-0">
        {druh === "uspech" ? (
          <Ikona.Fajfka velikost={15} />
        ) : druh === "chyba" ? (
          <Ikona.Vystraha velikost={15} />
        ) : (
          <Ikona.Info velikost={15} />
        )}
      </span>
      <p className="text-sm leading-snug">{zprava}</p>
      <button
        onClick={naZavreni}
        className="ml-auto shrink-0 opacity-60 hover:opacity-100"
        aria-label="Zavřít"
      >
        <Ikona.Krizek velikost={14} />
      </button>
    </div>
  );
}

export function useOznameni() {
  const [oznameni, nastavOznameni] = useState<
    { id: number; druh: DruhOznameni; zprava: string }[]
  >([]);

  const pridej = (druh: DruhOznameni, zprava: string) =>
    nastavOznameni((s) => [...s, { id: Date.now() + Math.random(), druh, zprava }]);

  const odeber = (id: number) =>
    nastavOznameni((s) => s.filter((o) => o.id !== id));

  const vykresli = (
    <div className="fixed bottom-5 right-5 z-50 flex w-[min(26rem,calc(100vw-2.5rem))] flex-col gap-2">
      {oznameni.map((o) => (
        <Oznameni
          key={o.id}
          druh={o.druh}
          zprava={o.zprava}
          naZavreni={() => odeber(o.id)}
        />
      ))}
    </div>
  );

  return { pridej, vykresli };
}

export function formatujDobu(sekundy: number): string {
  const s = Math.max(0, Math.round(sekundy));
  if (s < 60) return `${s} s`;
  const minuty = Math.floor(s / 60);
  if (minuty < 60) return s % 60 && minuty < 10 ? `${minuty} min ${s % 60} s` : `${minuty} min`;
  const hodiny = Math.floor(minuty / 60);
  return minuty % 60 ? `${hodiny} h ${minuty % 60} min` : `${hodiny} h`;
}

export function textZbyvajiciDoby(zbyva_s: number | null): string {
  if (zbyva_s === null) return "odhaduji zbývající čas…";
  if (zbyva_s < 5) return "téměř hotovo";
  return `zbývá přibližně ${formatujDobu(zbyva_s)}`;
}

export function RadekDoby({
  uplynulo_s,
  zbyva_s,
}: {
  uplynulo_s: number;
  zbyva_s: number | null;
}) {
  return (
    <p className="text-2xs text-textTlumeny tabular-nums">
      {textZbyvajiciDoby(zbyva_s)} · uplynulo {formatujDobu(uplynulo_s)}
    </p>
  );
}

export function UkazatelPostupu({ postup }: { postup: Postup }) {
  const podil = postup.celkem ? Math.min(1, postup.hotovo / postup.celkem) : 0;
  return (
    <div className="space-y-1.5" aria-live="polite">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-text">
          {postup.pocet_fazi > 1 && postup.faze_poradi > 0 && (
            <span className="text-textSlaby">
              Krok {postup.faze_poradi} z {postup.pocet_fazi}:{" "}
            </span>
          )}
          {postup.faze || "Připravuji…"}
        </span>
        {postup.celkem > 0 && (
          <span className="font-mono text-2xs tabular-nums text-textTlumeny whitespace-nowrap">
            {formatujCislo(postup.hotovo)} / {formatujCislo(postup.celkem)}
          </span>
        )}
      </div>
      <div className="ukazatel h-1.5">
        {postup.celkem > 0 ? (
          <div className="ukazatel-vypln" style={{ width: `${Math.max(podil * 100, 1)}%` }} />
        ) : (
          <div className="ukazatel-vypln prubeh-neurcity w-full" />
        )}
      </div>
      <RadekDoby uplynulo_s={postup.uplynulo_s} zbyva_s={postup.zbyva_s} />
    </div>
  );
}

export function formatujCas(iso: string | null): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("cs-CZ", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatujCislo(hodnota: number): string {
  return hodnota.toLocaleString("cs-CZ");
}

export function formatujProcenta(hodnota: number, desetinnych = 1): string {
  return `${(hodnota * 100).toFixed(desetinnych)} %`;
}

export function VolbaJazyka({
  id,
  popisek,
  hodnota,
  jazyky,
  naZmenu,
}: {
  id: string;
  popisek: string;
  hodnota: string;
  jazyky: { kod: string; nazev: string }[];
  naZmenu: (kod: string) => void;
}) {
  return (
    <div className="flex-1">
      <label className="stitek-pole" htmlFor={id}>
        {popisek}
      </label>
      <select
        id={id}
        className="pole"
        value={hodnota}
        onChange={(e) => naZmenu(e.target.value)}
      >
        {jazyky.length === 0 && <option value={hodnota}>{hodnota}</option>}
        {jazyky.map((j) => (
          <option key={j.kod} value={j.kod}>
            {j.nazev}
          </option>
        ))}
      </select>
    </div>
  );
}

export function sklonuj(pocet: number, jeden: string, dva: string, pet: string): string {
  const n = Math.abs(pocet);
  return `${formatujCislo(pocet)} ${n === 1 ? jeden : n >= 2 && n <= 4 ? dva : pet}`;
}
