import { useState } from "react";
import { api } from "../api";
import {useNacti} from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Nacitani,
  Panel,
  PrazdnyStav,
  Skore,
  Strankovac,
  ZahlaviObrazovky,
  formatujCas,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 15;

export default function MaximoIntegrace() {
  const { pridej, vykresli } = useOznameni();

  const [itemnum, nastavItemnum] = useState("30001");
  const [popis, nastavPopis] = useState("Ball bearing 6204 2RS");
  const [skupina, nastavSkupinu] = useState("BEARINGS");
  const [typUdalosti, nastavTypUdalosti] = useState("MXITEM_UPDATED");
  const [odpoved, nastavOdpoved] = useState<Record<string, unknown> | null>(null);
  const [pracuje, nastavPracuje] = useState(false);
  const [odsazeni, nastavOdsazeni] = useState(0);

  const struktura = useNacti(() => api.mif.objektovaStruktura(), []);
  const udalosti = useNacti(
    () => api.mif.udalosti({ limit: NA_STRANKU, odsazeni }),
    [odsazeni, odpoved],
  );

  const odesli = async () => {
    nastavPracuje(true);
    try {
      const vysledek = await api.mif.odeslatUdalost({
        typ_udalosti: typUdalosti,
        obsah: {
          ITEMNUM: itemnum,
          DESCRIPTION: popis,
          COMMODITYGROUP: skupina,
        }
      });
      nastavOdpoved(vysledek);
      pridej("uspech", "Událost byla zpracována.");
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Událost se nepodařilo zpracovat.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  const kandidati =
    (odpoved?.kandidati as
      | {
          itemnum: string;
          popis: string;
          skore: number;
          je_duplicita: boolean;
          rozpor_atributu: boolean;
          vysvetleni: string[];
        }[]
      | undefined) ?? [];

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Integrace na IBM Maximo"
      />

      <div className="panel mb-4 border-l-[3px] border-l-akcent p-3.5 flex items-start gap-2.5">
        <span className="text-akcent mt-0.5 shrink-0">
          <Ikona.Info velikost={17} />
        </span>
        <p className="text-sm text-textTlumeny leading-relaxed">
          <span className="text-text font-medium">Rozsah simulace.</span> Ověřuje
          se datový formát objektové struktury, tok událostí a tvar rozhraní.
          Chování skutečné instance Maximo Application Suite, její autentizace
          ani transakční zpracování ověřeny nejsou - licence je mimo rozpočet
          práce. Kód je však napsán tak, aby jej bylo možné napojit na reálnou
          instanci pouhou změnou konfigurace.
        </p>
      </div>

      <div className="grid xl:grid-cols-[minmax(0,24rem)_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel nadpis="Odeslat událost" popis="Simuluje uložení záznamu v Maximu">
            <div className="space-y-3.5">
              <div>
                <label className="stitek-pole">Typ události</label>
                <select
                  className="pole"
                  value={typUdalosti}
                  onChange={(e) => nastavTypUdalosti(e.target.value)}
                >
                  <option value="MXITEM_UPDATED">MXITEM_UPDATED</option>
                  <option value="MXITEM_CREATED">MXITEM_CREATED</option>
                </select>
              </div>
              <div>
                <label className="stitek-pole">ITEMNUM</label>
                <input
                  className="pole-mono"
                  value={itemnum}
                  onChange={(e) => nastavItemnum(e.target.value)}
                />
              </div>
              <div>
                <label className="stitek-pole">DESCRIPTION</label>
                <textarea
                  className="pole min-h-[74px] resize-y"
                  value={popis}
                  onChange={(e) => nastavPopis(e.target.value)}
                />
              </div>
              <div>
                <label className="stitek-pole">COMMODITYGROUP</label>
                <input
                  className="pole-mono"
                  value={skupina}
                  onChange={(e) => nastavSkupinu(e.target.value.toUpperCase())}
                />
              </div>
              <button
                className="tlacitko-hlavni w-full"
                onClick={() => void odesli()}
                disabled={pracuje || !popis.trim()}
              >
                {pracuje ? "Zpracovávám…" : "Odeslat událost"}
              </button>
            </div>
          </Panel>

          <Panel nadpis="Objektová struktura MXITEM">
            {struktura.data ? (
              <div className="space-y-2.5 text-sm">
                <div>
                  <p className="nadpis-sekce">Hlavní objekt</p>
                  <p className="font-mono text-text">
                    {String(struktura.data.hlavni_objekt)}
                  </p>
                </div>
                <div>
                  <p className="nadpis-sekce">Jmenný prostor</p>
                  <p className="font-mono text-[0.75rem] text-textTlumeny break-all">
                    {String(struktura.data.jmenny_prostor)}
                  </p>
                </div>
                <div>
                  <p className="nadpis-sekce mb-1.5">Pole struktury</p>
                  <div className="flex flex-wrap gap-1">
                    {(struktura.data.pole as string[]).map((p) => (
                      <span key={p} className="odznak-neutralni font-mono">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <Nacitani text="Načítám…" />
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          {odpoved && (
            <Panel nadpis="Odpověď na událost">
              <div
                className={`rounded-xs border-l-[3px] px-3.5 py-3 mb-3.5 ${
                  odpoved.upozorneni
                    ? "border-l-vystraha bg-vystrahaTlumena/35"
                    : "border-l-uspech bg-uspechTlumeny/35"
                }`}
              >
                <p className="text-sm text-text">
                  {odpoved.upozorneni
                    ? `Systém vrátil upozornění - nalezeno ${String(odpoved.pocet_kandidatu)} podobných položek.`
                    : "Systém nenalezl žádnou podobnou položku."}
                </p>
              </div>

              {kandidati.length > 0 && (
                <div className="space-y-2">
                  {kandidati.slice(0, 6).map((k) => (
                    <div
                      key={k.itemnum}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xs border border-obrys bg-plocha2 px-3 py-2"
                    >
                      <Kod>{k.itemnum}</Kod>
                      <span className="flex-1 min-w-[14rem] text-sm text-text">
                        {k.popis}
                      </span>
                      {k.je_duplicita ? (
                        <span className="odznak-vystraha">duplicita</span>
                      ) : (
                        <span className="odznak-neutralni">odlišný díl</span>
                      )}
                      <Skore hodnota={k.skore} sirka={56} />
                      {k.vysvetleni.length > 0 && (
                        <p className="w-full text-xs text-vystraha">
                          {k.vysvetleni.join(" · ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          <Panel nadpis="Historie přijatých událostí" bezOdsazeni>
            {udalosti.nacita && !udalosti.data ? (
              <Nacitani />
            ) : udalosti.chyba ? (
              <ChybovyStav zprava={udalosti.chyba} naObnoveni={udalosti.obnov} />
            ) : udalosti.data && udalosti.data.celkem === 0 ? (
              <PrazdnyStav
                nadpis="Zatím nedorazila žádná událost"
                popis="Odešlete testovací událost pomocí formuláře vlevo."
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="tabulka">
                    <thead>
                      <tr>
                        <th>Přijato</th>
                        <th>Typ</th>
                        <th>ITEMNUM</th>
                        <th>Výsledek</th>
                      </tr>
                    </thead>
                    <tbody>
                      {udalosti.data?.polozky.map((u) => {
                        let pocet: number | null = null;
                        try {
                          pocet = u.vysledek_json
                            ? (JSON.parse(u.vysledek_json).pocet_kandidatu as number)
                            : null;
                        } catch {
                          pocet = null;
                        }
                        return (
                          <tr key={u.id}>
                            <td className="whitespace-nowrap font-mono text-[0.8125rem] text-textTlumeny">
                              {formatujCas(u.prijato)}
                            </td>
                            <td>
                              <span className="odznak-neutralni font-mono">
                                {u.typ_udalosti}
                              </span>
                            </td>
                            <td>
                              <Kod>{u.itemnum ?? "-"}</Kod>
                            </td>
                            <td className="text-sm">
                              {u.chyba ? (
                                <span className="text-chyba">{u.chyba}</span>
                              ) : pocet !== null ? (
                                <span className="text-textTlumeny">
                                  {pocet === 0
                                    ? "bez nálezu"
                                    : `${pocet} kandidátů`}
                                </span>
                              ) : (
                                <span className="text-textSlaby">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {udalosti.data && (
                  <Strankovac
                    celkem={udalosti.data.celkem}
                    limit={NA_STRANKU}
                    odsazeni={odsazeni}
                    naZmenu={nastavOdsazeni}
                  />
                )}
              </>
            )}
          </Panel>
        </div>
      </div>

      {vykresli}
    </>
  );
}
