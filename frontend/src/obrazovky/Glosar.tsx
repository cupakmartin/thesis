import { useEffect, useState } from "react";
import { api, type TerminGlosare } from "../api";
import {useNacti, useOdlozeno} from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Nacitani,
  Panel,
  PrazdnyStav,
  Strankovac,
  ZahlaviObrazovky,
  formatujCislo,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 25;

const PRAZDNY: Partial<TerminGlosare> = {
  termin_en: "",
  termin_cs: "",
  kategorie: "",
  definice: "",
  nespravne: "",
};

export default function Glosar() {
  const { pridej, vykresli } = useOznameni();

  const [hledani, nastavHledani] = useState("");
  const [kategorie, nastavKategorii] = useState("");
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [upravovany, nastavUpravovany] = useState<Partial<TerminGlosare> | null>(null);

  const hledaniOdlozene = useOdlozeno(hledani, 300);
  useEffect(() => nastavOdsazeni(0), [hledaniOdlozene, kategorie]);

  const kategorieSeznam = useNacti(() => api.glosar.kategorie(), []);
  const seznam = useNacti(
    () =>
      api.glosar.seznam({
        hledany_text: hledaniOdlozene,
        kategorie,
        limit: NA_STRANKU,
        odsazeni,
      }),
    [hledaniOdlozene, kategorie, odsazeni],
  );

  const uloz = async () => {
    if (!upravovany?.termin_en?.trim() || !upravovany?.termin_cs?.trim()) {
      pridej("chyba", "Vyplňte anglický i český tvar termínu.");
      return;
    }
    try {
      const telo = { ...upravovany } as Partial<TerminGlosare> & {
        kdo: string;
      };
      const odpoved = upravovany.id
        ? await api.glosar.upravit(upravovany.id, telo)
        : await api.glosar.pridat(telo);
      pridej("uspech", odpoved.zprava);
      nastavUpravovany(null);
      seznam.obnov();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Termín se nepodařilo uložit.",
      );
    }
  };

  const smaz = async (id: string) => {
    if (!window.confirm("Opravdu odstranit tento termín z glosáře?")) return;
    try {
      const odpoved = await api.glosar.smazat(id);
      pridej("uspech", odpoved.zprava);
      seznam.obnov();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Termín se nepodařilo odstranit.",
      );
    }
  };

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Firemní glosář"
        akce={
          <button
            className="tlacitko-hlavni"
            onClick={() => nastavUpravovany({ ...PRAZDNY })}
          >
            Přidat termín
          </button>
        }
      />

      <Panel bezOdsazeni>
        <div className="flex flex-wrap items-end gap-2.5 p-3.5 border-b border-obrys">
          <div className="flex-1 min-w-[220px]">
            <label className="stitek-pole" htmlFor="hledani-glosar">
              Hledat
            </label>
            <input
              id="hledani-glosar"
              className="pole"
              placeholder="Termín česky, anglicky nebo v definici…"
              value={hledani}
              onChange={(e) => nastavHledani(e.target.value)}
            />
          </div>
          <div>
            <label className="stitek-pole">Kategorie</label>
            <select
              className="pole w-auto min-w-[12rem]"
              value={kategorie}
              onChange={(e) => nastavKategorii(e.target.value)}
            >
              <option value="">vše</option>
              {kategorieSeznam.data?.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          {seznam.data && (
            <p className="ml-auto text-sm text-textTlumeny pb-1.5">
              {formatujCislo(seznam.data.celkem)} termínů
            </p>
          )}
        </div>

        {seznam.nacita && !seznam.data ? (
          <Nacitani />
        ) : seznam.chyba ? (
          <ChybovyStav zprava={seznam.chyba} naObnoveni={seznam.obnov} />
        ) : seznam.data && seznam.data.celkem === 0 ? (
          <PrazdnyStav nadpis="Žádný termín neodpovídá zadání" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="tabulka">
                <thead>
                  <tr>
                    <th>Anglicky</th>
                    <th>Česky</th>
                    <th>Kategorie</th>
                    <th>Poznámka</th>
                    <th className="w-24" />
                  </tr>
                </thead>
                <tbody>
                  {seznam.data?.polozky.map((t) => (
                    <tr key={t.id}>
                      <td className="text-text font-medium">{t.termin_en}</td>
                      <td className="text-text">{t.termin_cs}</td>
                      <td>
                        <span className="odznak-neutralni">{t.kategorie}</span>
                      </td>
                      <td className="max-w-[36ch]">
                        {t.definice && (
                          <span className="block text-xs text-textTlumeny">
                            {t.definice}
                          </span>
                        )}
                        {t.nespravne && (
                          <span className="block text-xs text-chyba mt-0.5">
                            nepoužívat: {t.nespravne}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="flex justify-end gap-1">
                          <button
                            className="tlacitko-tichy px-1.5 py-1 text-xs"
                            onClick={() => nastavUpravovany({ ...t })}
                          >
                            Upravit
                          </button>
                          <button
                            className="tlacitko-tichy px-1.5 py-1 text-xs hover:text-chyba"
                            onClick={() => void smaz(t.id)}
                            aria-label={`Odstranit ${t.termin_en}`}
                          >
                            <Ikona.Krizek velikost={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {seznam.data && (
              <Strankovac
                celkem={seznam.data.celkem}
                limit={NA_STRANKU}
                odsazeni={odsazeni}
                naZmenu={nastavOdsazeni}
              />
            )}
          </>
        )}
      </Panel>

      {upravovany && (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40 animate-rozsvit"
            onClick={() => nastavUpravovany(null)}
          />
          <div className="relative w-full max-w-lg panel shadow-vyzdvih animate-nastup">
            <header className="panel-hlavicka">
              <h2 className="text-sm font-semibold">
                {upravovany.id ? "Úprava termínu" : "Nový termín"}
              </h2>
              <button
                className="tlacitko-tichy px-2"
                onClick={() => nastavUpravovany(null)}
                aria-label="Zavřít"
              >
                <Ikona.Krizek />
              </button>
            </header>
            <div className="p-4 space-y-3.5">
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="stitek-pole">Anglicky *</label>
                  <input
                    className="pole"
                    value={upravovany.termin_en ?? ""}
                    onChange={(e) =>
                      nastavUpravovany({ ...upravovany, termin_en: e.target.value })
                    }
                    autoFocus
                  />
                </div>
                <div>
                  <label className="stitek-pole">Česky *</label>
                  <input
                    className="pole"
                    value={upravovany.termin_cs ?? ""}
                    onChange={(e) =>
                      nastavUpravovany({ ...upravovany, termin_cs: e.target.value })
                    }
                  />
                </div>
              </div>
              <div>
                <label className="stitek-pole">Kategorie</label>
                <input
                  className="pole"
                  list="seznam-kategorii"
                  value={upravovany.kategorie ?? ""}
                  onChange={(e) =>
                    nastavUpravovany({ ...upravovany, kategorie: e.target.value })
                  }
                />
                <datalist id="seznam-kategorii">
                  {kategorieSeznam.data?.map((k) => (
                    <option key={k} value={k} />
                  ))}
                </datalist>
                <p className="mt-1 text-xs text-textSlaby">
                  Kategorie označující komponentu se používá i k rozlišení druhu
                  dílu při deduplikaci.
                </p>
              </div>
              <div>
                <label className="stitek-pole">Definice</label>
                <textarea
                  className="pole min-h-[70px] resize-y"
                  value={upravovany.definice ?? ""}
                  onChange={(e) =>
                    nastavUpravovany({ ...upravovany, definice: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="stitek-pole">Nesprávná varianta překladu</label>
                <input
                  className="pole"
                  placeholder="například: sada těsnění"
                  value={upravovany.nespravne ?? ""}
                  onChange={(e) =>
                    nastavUpravovany({ ...upravovany, nespravne: e.target.value })
                  }
                />
                <p className="mt-1 text-xs text-textSlaby">
                  Uvedená varianta bude modelu výslovně zakázána a kontrola
                  kvality ji označí za chybu.
                </p>
              </div>
            </div>
            <footer className="flex justify-end gap-2 px-4 py-3 border-t border-obrys">
              <button
                className="tlacitko-vedlejsi"
                onClick={() => nastavUpravovany(null)}
              >
                Zrušit
              </button>
              <button className="tlacitko-hlavni" onClick={() => void uloz()}>
                Uložit
              </button>
            </footer>
          </div>
        </div>
      )}

      {vykresli}
    </>
  );
}
