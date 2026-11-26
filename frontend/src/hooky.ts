import { useCallback, useEffect, useRef, useState } from "react";
import { ChybaApi, api, type Jazyk, type Postup } from "./api";

export interface StavNacitani<T> {
  data: T | null;
  nacita: boolean;
  chyba: string | null;
  obnov: () => void;
}

export function useNacti<T>(
  nacti: () => Promise<T>,
  zavislosti: unknown[] = [],
): StavNacitani<T> {
  const [data, nastavData] = useState<T | null>(null);
  const [nacita, nastavNacita] = useState(true);
  const [chyba, nastavChybu] = useState<string | null>(null);
  const [pocitadlo, nastavPocitadlo] = useState(0);
  const poradiPozadavku = useRef(0);

  useEffect(() => {
    const mojePoradi = ++poradiPozadavku.current;
    let aktualni = true;
    nastavNacita(true);
    nastavChybu(null);

    nacti()
      .then((vysledek) => {
        if (!aktualni || mojePoradi !== poradiPozadavku.current) return;
        nastavData(vysledek);
      })
      .catch((duvod: unknown) => {
        if (!aktualni || mojePoradi !== poradiPozadavku.current) return;
        nastavChybu(
          duvod instanceof ChybaApi
            ? duvod.message
            : "Při načítání dat došlo k neočekávané chybě.",
        );
      })
      .finally(() => {
        if (!aktualni || mojePoradi !== poradiPozadavku.current) return;
        nastavNacita(false);
      });

    return () => {
      aktualni = false;
    };
  }, [...zavislosti, pocitadlo]);

  const obnov = useCallback(() => nastavPocitadlo((p) => p + 1), []);
  return { data, nacita, chyba, obnov };
}

export function useOdlozeno<T>(hodnota: T, prodleva = 300): T {
  const [odlozena, nastavOdlozenou] = useState(hodnota);

  useEffect(() => {
    const casovac = setTimeout(() => nastavOdlozenou(hodnota), prodleva);
    return () => clearTimeout(casovac);
  }, [hodnota, prodleva]);

  return odlozena;
}

const INTERVAL_DOTAZU_NA_POSTUP_MS = 1000;
const MIN_PODIL_PRO_ODHAD = 0.02;
const MIN_DOBA_PRO_ODHAD_MS = 1500;

export function useSledovaniPostupu(
  ziskej: () => Promise<Postup>,
  aktivni: boolean,
): Postup | null {
  const [postup, nastavPostup] = useState<Postup | null>(null);
  const funkce = useRef(ziskej);
  funkce.current = ziskej;

  useEffect(() => {
    if (!aktivni) return;
    let zruseno = false;
    const nacti = () => {
      funkce.current()
        .then((snimek) => {
          if (!zruseno) nastavPostup(snimek);
        })
        .catch(() => undefined);
    };
    nacti();
    const casovac = window.setInterval(nacti, INTERVAL_DOTAZU_NA_POSTUP_MS);
    return () => {
      zruseno = true;
      window.clearInterval(casovac);
    };
  }, [aktivni]);

  return postup;
}

export function useOdhadZbyvajiciDoby(
  hotovo: number,
  celkem: number,
  aktivni: boolean,
): { uplynulo_s: number; zbyva_s: number | null } {
  const zacatek = useRef<number | null>(null);
  const [ted, nastavTed] = useState(() => Date.now());

  useEffect(() => {
    if (!aktivni) {
      zacatek.current = null;
      return;
    }
    zacatek.current = Date.now();
    nastavTed(Date.now());
    const casovac = window.setInterval(() => nastavTed(Date.now()), 1000);
    return () => window.clearInterval(casovac);
  }, [aktivni]);

  if (!aktivni || zacatek.current === null) return { uplynulo_s: 0, zbyva_s: null };
  const uplynulo = Math.max(0, ted - zacatek.current);
  const mereni =
    celkem > 0 && hotovo > 0 && hotovo / celkem >= MIN_PODIL_PRO_ODHAD && uplynulo >= MIN_DOBA_PRO_ODHAD_MS;
  return {
    uplynulo_s: uplynulo / 1000,
    zbyva_s: mereni ? ((uplynulo / hotovo) * (celkem - hotovo)) / 1000 : null,
  };
}

export function useJazyky(): Jazyk[] {
  const jazyky = useNacti(() => api.system.jazyky(), []);
  return jazyky.data ?? [];
}
