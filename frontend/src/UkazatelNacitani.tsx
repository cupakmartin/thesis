import { useEffect, useRef, useState } from "react";
import { api, type StavNacitani } from "./api";

const RYCHLE_MS = 800;
const POMALU_MS = 5000;
const OPAKOVANI_NACTENI_MS = 15000;

function Tocitko() {
  return (
    <span
      className="inline-block h-3 w-3 shrink-0 rounded-full border-2 border-current border-t-transparent animate-spin"
      aria-hidden="true"
    />
  );
}

export function UkazatelNacitani({ podnet }: { podnet: number }) {
  const [stav, nastavStav] = useState<StavNacitani | null>(null);
  const pripravenyModel = useRef<string | null>(null);
  const posledniNacteni = useRef(0);

  useEffect(() => {
    let zruseno = false;
    let casovac: ReturnType<typeof setTimeout>;

    const zjisti = async () => {
      let novy: StavNacitani | null = null;
      try {
        novy = await api.system.nacitani();
        const ted = Date.now();
        const nenacteno =
          novy.llm.stav === "nenacten" || novy.embedding.stav === "nenacten";
        if (nenacteno && ted - posledniNacteni.current > OPAKOVANI_NACTENI_MS) {
          posledniNacteni.current = ted;
          novy = await api.system.nactiModely();
        }
      } catch {
        novy = null;
      }
      if (zruseno) return;
      if (novy?.llm.stav === "pripraven") pripravenyModel.current = novy.llm.model;
      nastavStav(novy);
      const nacita =
        novy?.llm.stav === "nacita" || novy?.embedding.stav === "nacita";
      casovac = setTimeout(() => void zjisti(), nacita ? RYCHLE_MS : POMALU_MS);
    };

    void zjisti();
    return () => {
      zruseno = true;
      clearTimeout(casovac);
    };
  }, [podnet]);

  if (!stav) return null;

  const polozky: { klic: string; text: string; titulek: string }[] = [];
  if (stav.llm.stav === "nacita") {
    const predchozi = pripravenyModel.current;
    polozky.push({
      klic: "llm",
      text:
        predchozi && predchozi !== stav.llm.model
          ? `Přepínám na ${stav.llm.model}…`
          : `Načítám ${stav.llm.model}…`,
      titulek:
        "Jazykový model se načítá do paměti. První překlad počká, až bude načten.",
    });
  }
  if (stav.embedding.stav === "nacita") {
    polozky.push({
      klic: "embedding",
      text: "Načítám vektorový model…",
      titulek: `Model ${stav.embedding.model} pro deduplikaci a vyhledávání v glosáři.`,
    });
  }

  if (stav.llm.chyba && stav.llm.stav !== "nacita") {
    return (
      <span className="odznak-chyba" title={stav.llm.chyba}>
        {stav.llm.model} se nepodařilo načíst
      </span>
    );
  }

  if (polozky.length === 0) return null;

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5" role="status">
      {polozky.map((p) => (
        <span
          key={p.klic}
          className="odznak-akcent inline-flex items-center gap-1.5"
          title={p.titulek}
        >
          <Tocitko />
          {p.text}
        </span>
      ))}
    </span>
  );
}
