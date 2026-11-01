import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Fragment, useCallback, useState } from "react";
import { api, type StavSystemu } from "./api";
import { PoskytovatelKontroly, useKontrolaModelu } from "./KontrolaModelu";
import { useNacti } from "./hooky";
import { UkazatelNacitani } from "./UkazatelNacitani";

import Prehled from "./obrazovky/Prehled";
import Katalog from "./obrazovky/Katalog";
import Deduplikace from "./obrazovky/Deduplikace";
import KontrolaPolozky from "./obrazovky/KontrolaPolozky";
import Slucovani from "./obrazovky/Slucovani";
import Preklad from "./obrazovky/Preklad";
import Glosar from "./obrazovky/Glosar";
import Vizualizace from "./obrazovky/Vizualizace";
import MaximoIntegrace from "./obrazovky/MaximoIntegrace";
import Prubeh from "./obrazovky/Prubeh";

const NAVIGACE: { cesta: string; nazev: string; skupina: string }[] = [
  { cesta: "/prehled", nazev: "Přehled", skupina: "uvod" },

  { cesta: "/katalog", nazev: "Katalog", skupina: "data" },
  { cesta: "/glosar", nazev: "Glosář", skupina: "data" },

  { cesta: "/deduplikace", nazev: "Deduplikace", skupina: "konsolidace" },
  { cesta: "/slucovani", nazev: "Slučování", skupina: "konsolidace" },
  { cesta: "/kontrola-polozky", nazev: "Nová položka", skupina: "konsolidace" },

  { cesta: "/preklad", nazev: "Překlad", skupina: "preklad" },
  { cesta: "/prubeh", nazev: "Průběh zpracování", skupina: "preklad" },

  { cesta: "/vizualizace", nazev: "Vizualizace", skupina: "analyza" },
  { cesta: "/maximo", nazev: "Maximo", skupina: "analyza" },
];

export default function App() {
  const stav = useNacti(() => api.system.stav(), []);
  const [podnet, nastavPodnet] = useState(0);
  const poZmeneModelu = useCallback(() => {
    stav.obnov();
    nastavPodnet((n) => n + 1);
  }, [stav]);

  return (
    <PoskytovatelKontroly>
      <div className="min-h-screen">
        <header className="border-b border-obrys bg-plocha px-3 py-2">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <nav className="flex flex-wrap items-center gap-1">
              {NAVIGACE.map((polozka, poradi) => (
                <Fragment key={polozka.cesta}>
                  {poradi > 0
                    && polozka.skupina !== NAVIGACE[poradi - 1].skupina && (
                      <span
                        aria-hidden
                        className="mx-1 h-4 w-px bg-obrys2 shrink-0"
                      />
                    )}
                  <NavLink
                    to={polozka.cesta}
                    className={({ isActive }) =>
                      `odkaz-navigace ${isActive ? "odkaz-navigace-aktivni" : ""}`
                    }
                  >
                    {polozka.nazev}
                  </NavLink>
                </Fragment>
              ))}
            </nav>

            <div className="ml-auto flex flex-wrap items-center gap-2">
              <UkazatelNacitani podnet={podnet} />
              <VolbaModelu stav={stav.data} onZmena={poZmeneModelu} />
              {stav.data && <UkazatelModelu stav={stav.data} />}
            </div>
          </div>
        </header>

        <main className="px-3 py-4">
          <Routes>
            <Route path="/" element={<Navigate to="/prehled" replace />} />
            <Route path="/prehled" element={<Prehled />} />
            <Route path="/katalog" element={<Katalog />} />
            <Route path="/glosar" element={<Glosar />} />
            <Route path="/deduplikace" element={<Deduplikace />} />
            <Route path="/kontrola-polozky" element={<KontrolaPolozky />} />
            <Route path="/slucovani" element={<Slucovani />} />
            <Route path="/preklad" element={<Preklad />} />
            <Route path="/vizualizace" element={<Vizualizace />} />
            <Route path="/prubeh" element={<Prubeh />} />
            <Route path="/maximo" element={<MaximoIntegrace />} />
            <Route path="*" element={<Navigate to="/prehled" replace />} />
          </Routes>
        </main>
      </div>
    </PoskytovatelKontroly>
  );
}

function VolbaModelu({
  stav,
  onZmena,
}: {
  stav: StavSystemu | null;
  onZmena: () => void;
}) {
  const [probiha, nastavProbiha] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);

  const zmen = useCallback(
    async (model: string) => {
      nastavProbiha(true);
      nastavChybu(null);
      try {
        await api.system.zmenModel(model);
        onZmena();
      } catch (e) {
        nastavChybu(e instanceof Error ? e.message : String(e));
      } finally {
        nastavProbiha(false);
      }
    },
    [onZmena],
  );

  if (!stav) return null;

  if (!stav.ollama_dostupna) {
    return (
      <span className="odznak-chyba" title="Služba Ollama neběží.">
        model nelze zvolit
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1">
      <label className="sr-only" htmlFor="volba-modelu">
        Jazykový model
      </label>
      <select
        id="volba-modelu"
        className="pole w-auto"
        value={stav.aktivni_model}
        disabled={probiha}
        onChange={(e) => void zmen(e.target.value)}
        title={
          `Jazykový model použitý pro překlad. Výchozí: ${stav.vychozi_model}.` +
          (stav.model_prepnut_uzivatelem ? " Nyní je zvolen jiný." : "")
        }
      >
        {!stav.dostupne_modely.includes(stav.aktivni_model) && (
          <option value={stav.aktivni_model}>
            {stav.aktivni_model} (není nainstalován)
          </option>
        )}
        {stav.dostupne_modely.map((m) => (
          <option key={m} value={m}>
            {m}
            {m === stav.vychozi_model ? " - výchozí" : ""}
          </option>
        ))}
      </select>
      {probiha && <span className="text-2xs text-textSlaby">přepínám…</span>}
      {chyba && (
        <span className="odznak-chyba" title={chyba}>
          nelze přepnout
        </span>
      )}
    </span>
  );
}

function UkazatelModelu({ stav }: { stav: StavSystemu }) {
  const { vysledek, probiha, spust } = useKontrolaModelu();

  if (!stav.ollama_dostupna) {
    return (
      <span
        className="odznak-chyba"
        title="Služba Ollama neběží - překlad nebude funkční."
      >
        Ollama neběží
      </span>
    );
  }

  const overeno = vysledek?.celkovy_stav;
  const trida =
    overeno === "v_poradku"
      ? "odznak-uspech"
      : overeno === "varovani"
        ? "odznak-vystraha"
        : overeno === "chyba"
          ? "odznak-chyba"
          : "odznak-neutralni";

  return (
    <button
      className={trida}
      onClick={() => void spust()}
      disabled={probiha}
      title={
        probiha
          ? "Probíhá ověření…"
          : overeno
            ? `Ověřeno: ${vysledek?.pocet_v_poradku}/${vysledek?.pocet_kontrol} kontrol v pořádku. Kliknutím ověřit znovu.`
            : `Model ${stav.aktivni_model} je dostupný. Kliknutím ověříte, že skutečně pracuje správně.`
      }
    >
      {probiha
        ? "ověřuji…"
        : overeno === "v_poradku"
          ? "model ověřen"
          : overeno === "varovani"
            ? "model - výhrady"
            : overeno === "chyba"
              ? "model - chyba"
              : "ověřit model"}
    </button>
  );
}
