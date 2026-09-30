import { useCallback, useEffect, useRef, useState } from "react";
import { ChybaApi } from "./api";

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
