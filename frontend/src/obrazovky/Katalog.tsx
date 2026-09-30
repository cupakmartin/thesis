import { useEffect, useState } from "react";
import { api, type Polozka } from "../api";
import { useNacti, useOdlozeno } from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Nacitani,
  OdznakJazyka,
  OdznakStavu,
  Panel,
  PrazdnyStav,
  Strankovac,
  ZahlaviObrazovky,
  formatujCas,
  formatujCislo,
} from "../komponenty";

const NA_STRANKU = 25;

export default function Katalog() {
  const [hledani, nastavHledani] = useState("");
  const [skupina, nastavSkupinu] = useState("");
  const [trida, nastavTridu] = useState("");
  const [jazyk, nastavJazyk] = useState("");
  const [stavKonsolidace, nastavStavKonsolidace] = useState("");
  const [razeni, nastavRazeni] = useState("poradi");
  const [sestupne, nastavSestupne] = useState(false);
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [vybrana, nastavVybranou] = useState<string | null>(null);

  const hledaniOdlozene = useOdlozeno(hledani, 300);

  useEffect(() => {
    nastavOdsazeni(0);
  }, [hledaniOdlozene, skupina, trida, jazyk, stavKonsolidace, razeni, sestupne]);

  const filtry = useNacti(() => api.polozky.filtry(), []);
  const seznam = useNacti(
    () =>
      api.polozky.seznam({
        hledany_text: hledaniOdlozene,
        komoditni_skupina: skupina,
        iso_trida: trida,
        jazyk,
        stav_konsolidace: stavKonsolidace,
        razeni,
        sestupne,
        limit: NA_STRANKU,
        odsazeni,
      }),
    [hledaniOdlozene, skupina, trida, jazyk, stavKonsolidace, razeni, sestupne, odsazeni],
  );

  const jeFiltrovano =
    hledani || skupina || trida || jazyk || stavKonsolidace;

  const vycistiFiltry = () => {
    nastavHledani("");
    nastavSkupinu("");
    nastavTridu("");
    nastavJazyk("");
    nastavStavKonsolidace("");
  };

  const prepniRazeni = (sloupec: string) => {
    if (razeni === sloupec) nastavSestupne(!sestupne);
    else {
      nastavRazeni(sloupec);
      nastavSestupne(false);
    }
  };

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Katalog položek"
      />

      <Panel bezOdsazeni>
        <div className="flex flex-wrap items-end gap-2.5 p-3.5 border-b border-obrys">
          <div className="flex-1 min-w-[220px]">
            <label className="stitek-pole" htmlFor="hledani">
              Hledat
            </label>
            <input
              id="hledani"
              className="pole"
              placeholder="Popis, číslo položky, výrobce nebo typ…"
              value={hledani}
              onChange={(e) => nastavHledani(e.target.value)}
            />
          </div>

          <VyberFiltru
            popisek="Komoditní skupina"
            hodnota={skupina}
            naZmenu={nastavSkupinu}
            moznosti={filtry.data?.komoditni_skupiny ?? []}
          />
          <VyberFiltru
            popisek="Třída ISO 14224"
            hodnota={trida}
            naZmenu={nastavTridu}
            moznosti={filtry.data?.iso_tridy ?? []}
          />
          <VyberFiltru
            popisek="Jazyk"
            hodnota={jazyk}
            naZmenu={nastavJazyk}
            moznosti={filtry.data?.jazyky ?? []}
          />
          <VyberFiltru
            popisek="Konsolidace"
            hodnota={stavKonsolidace}
            naZmenu={nastavStavKonsolidace}
            moznosti={["aktivni", "slouceno"]}
          />

          {jeFiltrovano && (
            <button className="tlacitko-tichy" onClick={vycistiFiltry}>
              <Ikona.Krizek velikost={14} /> Zrušit filtry
            </button>
          )}
        </div>

        {seznam.nacita && !seznam.data ? (
          <Nacitani />
        ) : seznam.chyba ? (
          <ChybovyStav zprava={seznam.chyba} naObnoveni={seznam.obnov} />
        ) : seznam.data && seznam.data.celkem === 0 ? (
          <PrazdnyStav
            nadpis="Žádná položka neodpovídá zadání"
            popis="Zkuste upravit hledaný výraz nebo zrušit některý z filtrů."
            akce={
              jeFiltrovano ? (
                <button className="tlacitko-vedlejsi" onClick={vycistiFiltry}>
                  Zrušit filtry
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="tabulka">
                <thead>
                  <tr>
                    <ZahlaviSloupce
                      nazev="Číslo"
                      sloupec="itemnum"
                      aktivni={razeni}
                      sestupne={sestupne}
                      naKliknuti={prepniRazeni}
                    />
                    <ZahlaviSloupce
                      nazev="Popis"
                      sloupec="description"
                      aktivni={razeni}
                      sestupne={sestupne}
                      naKliknuti={prepniRazeni}
                    />
                    <th>Jazyk</th>
                    <ZahlaviSloupce
                      nazev="Komoditní skupina"
                      sloupec="commodity_group"
                      aktivni={razeni}
                      sestupne={sestupne}
                      naKliknuti={prepniRazeni}
                    />
                    <ZahlaviSloupce
                      nazev="ISO"
                      sloupec="iso_class"
                      aktivni={razeni}
                      sestupne={sestupne}
                      naKliknuti={prepniRazeni}
                    />
                    <ZahlaviSloupce
                      nazev="Výrobce"
                      sloupec="manufacturer"
                      aktivni={razeni}
                      sestupne={sestupne}
                      naKliknuti={prepniRazeni}
                    />
                    <th>Stav</th>
                  </tr>
                </thead>
                <tbody>
                  {seznam.data?.polozky.map((p, i) => (
                    <tr
                      key={p.itemnum}
                      className="cursor-pointer animate-nastup"
                      style={{ animationDelay: `${Math.min(i, 12) * 14}ms` }}
                      onClick={() => nastavVybranou(p.itemnum)}
                    >
                      <td>
                        <Kod>{p.itemnum}</Kod>
                      </td>
                      <td className="max-w-[38ch]">
                        <span className="text-text">{p.description}</span>
                        {p.stav_konsolidace === "slouceno" && p.slouceno_do && (
                          <span className="block text-2xs text-textSlaby mt-0.5">
                            sloučeno do {p.slouceno_do}
                          </span>
                        )}
                      </td>
                      <td>
                        <OdznakJazyka kod={p.lang_code} />
                      </td>
                      <td className="text-textTlumeny">{p.commodity_group}</td>
                      <td>
                        <Kod>{p.iso_class}</Kod>
                      </td>
                      <td className="text-textTlumeny">{p.manufacturer}</td>
                      <td>
                        <OdznakStavu stav={p.status ?? ""} />
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

      {vybrana && (
        <PanelDetailu itemnum={vybrana} naZavreni={() => nastavVybranou(null)} />
      )}
    </>
  );
}

function VyberFiltru({
  popisek,
  hodnota,
  naZmenu,
  moznosti,
}: {
  popisek: string;
  hodnota: string;
  naZmenu: (h: string) => void;
  moznosti: string[];
}) {
  return (
    <div>
      <label className="stitek-pole">{popisek}</label>
      <select
        className="pole w-auto min-w-[9rem]"
        value={hodnota}
        onChange={(e) => naZmenu(e.target.value)}
      >
        <option value="">vše</option>
        {moznosti.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  );
}

function ZahlaviSloupce({
  nazev,
  sloupec,
  aktivni,
  sestupne,
  naKliknuti,
}: {
  nazev: string;
  sloupec: string;
  aktivni: string;
  sestupne: boolean;
  naKliknuti: (s: string) => void;
}) {
  const jeAktivni = aktivni === sloupec;
  return (
    <th>
      <button
        className={`flex items-center gap-1 hover:text-text transition-colors ${
          jeAktivni ? "text-akcent" : ""
        }`}
        onClick={() => naKliknuti(sloupec)}
      >
        {nazev}
        <span className="text-[9px] leading-none">
          {jeAktivni ? (sestupne ? "▼" : "▲") : "↕"}
        </span>
      </button>
    </th>
  );
}

function PanelDetailu({
  itemnum,
  naZavreni,
}: {
  itemnum: string;
  naZavreni: () => void;
}) {
  const detail = useNacti(() => api.polozky.detail(itemnum), [itemnum]);
  const [xml, nastavXml] = useState<string | null>(null);

  useEffect(() => {
    const naKlavesu = (e: KeyboardEvent) => {
      if (e.key === "Escape") naZavreni();
    };
    window.addEventListener("keydown", naKlavesu);
    return () => window.removeEventListener("keydown", naKlavesu);
  }, [naZavreni]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="absolute inset-0 bg-black/35 animate-rozsvit"
        onClick={naZavreni}
      />
      <aside className="relative w-[min(34rem,100vw)] h-full overflow-y-auto bg-plocha border-l border-obrys shadow-vyzdvih animate-nastup">
        <header className="sticky top-0 flex items-center justify-between gap-3 px-5 h-[57px] bg-plocha border-b border-obrys">
          <div className="min-w-0">
            <p className="nadpis-sekce">Detail položky</p>
            <p className="font-mono text-sm text-text">{itemnum}</p>
          </div>
          <button className="tlacitko-tichy px-2" onClick={naZavreni} aria-label="Zavřít">
            <Ikona.Krizek />
          </button>
        </header>

        <div className="p-5">
          {detail.nacita ? (
            <Nacitani />
          ) : detail.chyba ? (
            <ChybovyStav zprava={detail.chyba} />
          ) : detail.data ? (
            <div className="space-y-5">
              <div>
                <p className="nadpis-sekce mb-1">Popis</p>
                <p className="text-text leading-relaxed">
                  {detail.data.description}
                </p>
                {detail.data.long_description && (
                  <p className="mt-2 text-sm text-textTlumeny leading-relaxed">
                    {detail.data.long_description}
                  </p>
                )}
              </div>

              {detail.data.zarazeni_iso && (
                <div className="panel p-3.5 bg-plocha2">
                  <p className="nadpis-sekce mb-1.5">Zařazení dle ISO 14224</p>
                  <p className="flex items-center gap-2">
                    <span className="odznak-akcent">
                      {detail.data.zarazeni_iso.kod}
                    </span>
                    <span className="text-sm text-text">
                      {detail.data.zarazeni_iso.nazev_cs}
                    </span>
                  </p>
                  <p className="mt-1.5 text-xs text-textTlumeny">
                    {detail.data.zarazeni_iso.zduvodneni} Jistota{" "}
                    <span className="font-mono">
                      {(detail.data.zarazeni_iso.jistota * 100).toFixed(0)} %
                    </span>
                    .
                  </p>
                </div>
              )}

              <dl className="grid grid-cols-2 gap-x-5 gap-y-3 text-sm">
                <Pole popisek="Komoditní skupina" hodnota={detail.data.commodity_group} />
                <Pole popisek="Stav" hodnota={detail.data.status} />
                <Pole popisek="Výrobce" hodnota={detail.data.manufacturer} />
                <Pole popisek="Typové označení" hodnota={detail.data.model_num} mono />
                <Pole popisek="Dodavatel" hodnota={detail.data.vendor} />
                <Pole popisek="Ref. číslo výrobce" hodnota={detail.data.external_ref_id} mono />
                <Pole popisek="Objednací jednotka" hodnota={detail.data.order_unit} />
                <Pole popisek="Jazyk záznamu" hodnota={detail.data.lang_code} />
                <Pole
                  popisek="Poslední změna"
                  hodnota={formatujCas(detail.data.change_date)}
                />
                <Pole popisek="Změnil" hodnota={detail.data.change_by} />
              </dl>

              {detail.data.stav_konsolidace === "slouceno" && (
                <div className="panel p-3.5 border-uspech/40 bg-uspechTlumeny">
                  <p className="text-sm text-uspech">
                    Tento záznam byl označen jako duplicita a sloučen do položky{" "}
                    <span className="font-mono font-semibold">
                      {detail.data.slouceno_do}
                    </span>
                    .
                  </p>
                </div>
              )}

              <div>
                <button
                  className="tlacitko-vedlejsi w-full"
                  onClick={async () => nastavXml(await api.polozky.xml(itemnum))}
                >
                  <Ikona.Stahnout velikost={14} /> Zobrazit jako MXITEM (XML)
                </button>
                {xml && (
                  <pre className="mt-3 max-h-72 overflow-auto rounded-xs border border-obrys bg-plocha2 p-3 font-mono text-[0.7rem] leading-relaxed text-textTlumeny">
                    {xml}
                  </pre>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function Pole({
  popisek,
  hodnota,
  mono,
}: {
  popisek: string;
  hodnota: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="nadpis-sekce">{popisek}</dt>
      <dd className={`mt-0.5 text-text ${mono ? "font-mono text-[0.8125rem]" : ""}`}>
        {hodnota || "—"}
      </dd>
    </div>
  );
}
