import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Ikona, Panel } from "./komponenty";

interface Kontrola {
  nazev: string;
  stav: "v_poradku" | "varovani" | "chyba";
  zprava: string;
  podrobnost: string;
  doba_s: number;
  hodnota: string;
}

interface VysledekKontroly {
  celkovy_stav: "v_poradku" | "varovani" | "chyba";
  doba_celkem_s: number;
  pocet_kontrol: number;
  pocet_v_poradku: number;
  kontroly: Kontrola[];
}

const POPIS_STAVU = {
  v_poradku: {
    text: "Modely pracují správně",
    trida: "odznak-uspech",
    barva: "text-uspech",
    okraj: "border-l-uspech",
  },
  varovani: {
    text: "Zjištěny výhrady",
    trida: "odznak-vystraha",
    barva: "text-vystraha",
    okraj: "border-l-vystraha",
  },
  chyba: {
    text: "Zjištěna chyba",
    trida: "odznak-chyba",
    barva: "text-chyba",
    okraj: "border-l-chyba",
  },
} as const;

interface StavKontroly {
  vysledek: VysledekKontroly | null;
  probiha: boolean;
  chyba: string | null;
  spust: () => Promise<void>;
}

const KontextKontroly = createContext<StavKontroly | null>(null);

export function PoskytovatelKontroly({ children }: { children: ReactNode }) {
  const [vysledek, nastavVysledek] = useState<VysledekKontroly | null>(null);
  const [probiha, nastavProbiha] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);

  const spust = useCallback(async () => {
    nastavProbiha(true);
    nastavChybu(null);
    try {
      const odpoved = await fetch("/api/system/kontrola-modelu", {
        method: "POST",
      });
      if (!odpoved.ok) throw new Error(`Server odpověděl chybou ${odpoved.status}.`);
      nastavVysledek((await odpoved.json()) as VysledekKontroly);
    } catch (duvod) {
      nastavChybu(
        duvod instanceof Error ? duvod.message : "Kontrolu se nepodařilo provést.",
      );
    } finally {
      nastavProbiha(false);
    }
  }, []);

  const hodnota = useMemo<StavKontroly>(
    () => ({ vysledek, probiha, chyba, spust }),
    [vysledek, probiha, chyba, spust],
  );

  return (
    <KontextKontroly.Provider value={hodnota}>{children}</KontextKontroly.Provider>
  );
}

export function useKontrolaModelu(): StavKontroly {
  const kontext = useContext(KontextKontroly);
  if (!kontext) {
    throw new Error(
      "useKontrolaModelu lze použít pouze uvnitř PoskytovatelKontroly.",
    );
  }
  return kontext;
}

export default function KontrolaModelu() {
  const { vysledek, probiha, chyba, spust } = useKontrolaModelu();
  const [rozbaleno, nastavRozbaleno] = useState(true);

  const stav = vysledek ? POPIS_STAVU[vysledek.celkovy_stav] : null;

  return (
    <Panel
      nadpis="Ověření funkce modelů"
      popis="Skutečná zkouška obou modelů na známém vstupu"
      akce={
        <button
          className="tlacitko-hlavni"
          onClick={() => void spust()}
          disabled={probiha}
        >
          {probiha ? (
            <>
              <span className="inline-block h-3 w-3 rounded-full border-2 border-akcentText/40 border-t-akcentText animate-spin" />
              Ověřuji…
            </>
          ) : (
            <>
              <Ikona.Obnovit velikost={14} /> Spustit ověření
            </>
          )}
        </button>
      }
    >
      {probiha && !vysledek && (
        <div className="py-6">
          <div className="ukazatel h-2 max-w-sm mx-auto">
            <div className="ukazatel-vypln prubeh-neurcity w-full" />
          </div>
          <p className="mt-3 text-center text-sm text-textTlumeny">
            Probíhá zkušební překlad. První volání po spuštění počítače trvá
            déle, protože se model načítá do paměti grafické karty.
          </p>
        </div>
      )}

      {chyba && (
        <div className="flex items-start gap-2.5 rounded-xs border border-chyba/40 bg-chybaTlumena px-3.5 py-3">
          <span className="text-chyba mt-0.5">
            <Ikona.Vystraha velikost={16} />
          </span>
          <p className="text-sm text-text">{chyba}</p>
        </div>
      )}

      {!probiha && !vysledek && !chyba && (
        <p className="text-sm text-textTlumeny leading-relaxed">
          Ukazatel v záhlaví pouze zjišťuje, zda služba Ollama odpovídá.
          Neprokazuje však, že modely pracují správně. Toto ověření provede
          skutečný zkušební překlad a porovnání položek a zkontroluje, zda
          výsledek odpovídá očekávání.
          <br />
          <span className="text-textSlaby">
            Doporučuji spustit před předvedením.
          </span>
        </p>
      )}

      {vysledek && stav && (
        <div className="space-y-3">
          <div
            className={`rounded-xs border-l-[3px] ${stav.okraj} bg-plocha2 px-3.5 py-3`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className={`flex items-center gap-2 font-medium ${stav.barva}`}>
                {vysledek.celkovy_stav === "v_poradku" ? (
                  <Ikona.Fajfka velikost={17} />
                ) : (
                  <Ikona.Vystraha velikost={17} />
                )}
                {stav.text}
              </p>
              <p className="font-mono text-xs tabular-nums text-textTlumeny">
                {vysledek.pocet_v_poradku}/{vysledek.pocet_kontrol} kontrol ·{" "}
                {vysledek.doba_celkem_s.toFixed(1)} s
              </p>
            </div>
          </div>

          <button
            className="text-xs text-akcent hover:underline"
            onClick={() => nastavRozbaleno(!rozbaleno)}
          >
            {rozbaleno ? "Skrýt podrobnosti" : "Zobrazit podrobnosti"}
          </button>

          {rozbaleno && (
            <ul className="space-y-1.5">
              {vysledek.kontroly.map((k) => (
                <RadekKontroly key={k.nazev} kontrola={k} />
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}

function RadekKontroly({ kontrola }: { kontrola: Kontrola }) {
  const [rozbaleno, nastavRozbaleno] = useState(false);
  const maPodrobnost = Boolean(kontrola.podrobnost);

  const znak =
    kontrola.stav === "v_poradku" ? (
      <span className="text-uspech">
        <Ikona.Fajfka velikost={14} />
      </span>
    ) : kontrola.stav === "varovani" ? (
      <span className="text-vystraha">
        <Ikona.Vystraha velikost={14} />
      </span>
    ) : (
      <span className="text-chyba">
        <Ikona.Krizek velikost={14} />
      </span>
    );

  return (
    <li className="rounded-xs border border-obrys bg-plocha2">
      <button
        className="flex w-full items-start gap-2.5 px-3 py-2 text-left"
        onClick={() => maPodrobnost && nastavRozbaleno(!rozbaleno)}
        disabled={!maPodrobnost}
      >
        <span className="mt-0.5 shrink-0">{znak}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm text-text">{kontrola.nazev}</span>
          <span className="block text-xs text-textTlumeny mt-0.5">
            {kontrola.zprava}
          </span>
        </span>
        <span className="shrink-0 text-right">
          {kontrola.hodnota && (
            <span className="block font-mono text-xs tabular-nums text-text">
              {kontrola.hodnota}
            </span>
          )}
          <span className="block font-mono text-2xs tabular-nums text-textSlaby">
            {kontrola.doba_s.toFixed(2)} s
          </span>
        </span>
      </button>

      {rozbaleno && maPodrobnost && (
        <p className="whitespace-pre-line border-t border-obrys px-3 py-2 text-xs leading-relaxed text-textTlumeny">
          {kontrola.podrobnost}
        </p>
      )}
    </li>
  );
}
