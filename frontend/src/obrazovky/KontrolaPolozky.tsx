import { useCallback, useEffect, useState } from "react";
import { api, type VysledekKontroly } from "../api";
import { useNacti, useOdlozeno } from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Panel,
  PrazdnyStav,
  Skore,
  ZahlaviObrazovky,
} from "../komponenty";

const PRIKLADY = [
  {
    popis: "Bearing ball 6204 2RS",
    vysvetleni: "anglický zápis českého záznamu — mezijazyčná duplicita",
  },
  {
    popis: "Ložisko kuličkové 6205 2RS",
    vysvetleni: "jiný rozměr — nesmí být vyhodnoceno jako duplicita",
  },
  {
    popis: "Vent. kul. DN50 PN16 nerez",
    vysvetleni: "zkrácený zápis existující položky",
  },
  {
    popis: "Zpětný ventil DN50 PN16",
    vysvetleni: "jiný druh armatury téže světlosti",
  },
];

export default function KontrolaPolozky() {
  const [popis, nastavPopis] = useState("");
  const [skupina, nastavSkupinu] = useState("");
  const [vysledek, nastavVysledek] = useState<VysledekKontroly | null>(null);
  const [nacita, nastavNacita] = useState(false);
  const [chyba, nastavChybu] = useState<string | null>(null);
  const [automaticky, nastavAutomaticky] = useState(true);
  const katalog = useNacti(() => api.katalog.stav(), []);
  const filtry = useNacti(() => api.polozky.filtry(), []);
  const sloupecSkupiny = katalog.data?.sloupce?.find((s) => s.role === "skupina");
  const hodnotySkupiny = filtry.data?.komoditni_skupiny ?? [];
  const prikladSkupiny = hodnotySkupiny[0] ?? "";
  const velkymiPismeny =
    hodnotySkupiny.length > 0 && hodnotySkupiny.every((h) => h === h.toUpperCase());

  const popisOdlozeny = useOdlozeno(popis, 550);

  const zkontroluj = useCallback(
    async (text: string, komoditniSkupina: string) => {
      if (text.trim().length < 3) {
        nastavVysledek(null);
        return;
      }
      nastavNacita(true);
      nastavChybu(null);
      try {
        nastavVysledek(
          await api.deduplikace.kontrolaPolozky({
            popis: text,
            komoditni_skupina: komoditniSkupina,
            pocet_kandidatu: 8,
          }),
        );
      } catch (duvod) {
        nastavChybu(
          duvod instanceof Error ? duvod.message : "Kontrolu se nepodařilo provést.",
        );
        nastavVysledek(null);
      } finally {
        nastavNacita(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (automaticky) void zkontroluj(popisOdlozeny, skupina);
  }, [popisOdlozeny, skupina, automaticky]);

  const duplicity = vysledek?.kandidati.filter((k) => k.je_duplicita) ?? [];
  const zamitnute = vysledek?.kandidati.filter((k) => !k.je_duplicita) ?? [];

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Kontrola nové položky"
      />

      <div className="grid xl:grid-cols-[minmax(0,26rem)_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel nadpis="Zakládaný záznam">
            <div className="space-y-3.5">
              <div>
                <label className="stitek-pole" htmlFor="popis-polozky">
                  Popis položky
                </label>
                <textarea
                  id="popis-polozky"
                  className="pole min-h-[92px] resize-y leading-relaxed"
                  placeholder="například: Ložisko kuličkové 6204 2RS"
                  value={popis}
                  onChange={(e) => nastavPopis(e.target.value)}
                  autoFocus
                />
                <p className="mt-1.5 text-xs text-textSlaby">
                  Kontrola proběhne automaticky po zadání alespoň tří znaků.
                </p>
              </div>

              {sloupecSkupiny && (
                <div>
                  <label className="stitek-pole" htmlFor="skupina-polozky">
                    {sloupecSkupiny.nazev} (nepovinné)
                  </label>
                  <input
                    id="skupina-polozky"
                    className="pole"
                    list="hodnoty-skupiny"
                    placeholder={prikladSkupiny ? `například: ${prikladSkupiny}` : undefined}
                    value={skupina}
                    onChange={(e) =>
                      nastavSkupinu(velkymiPismeny ? e.target.value.toUpperCase() : e.target.value)
                    }
                  />
                  <datalist id="hodnoty-skupiny">
                    {hodnotySkupiny.map((h) => (
                      <option key={h} value={h} />
                    ))}
                  </datalist>
                </div>
              )}

              <div className="flex items-center justify-between gap-3 pt-1">
                <label className="flex items-center gap-2 text-sm text-textTlumeny cursor-pointer">
                  <input
                    type="checkbox"
                    className="accent-akcent"
                    checked={automaticky}
                    onChange={(e) => nastavAutomaticky(e.target.checked)}
                  />
                  Kontrolovat průběžně
                </label>
                <button
                  className="tlacitko-hlavni"
                  onClick={() => void zkontroluj(popis, skupina)}
                  disabled={popis.trim().length < 3}
                >
                  {nacita ? "Kontroluji…" : "Zkontrolovat"}
                </button>
              </div>
            </div>
          </Panel>

          <Panel nadpis="Vyzkoušejte" popis="Připravené případy pro ověření chování">
            <div className="space-y-2">
              {PRIKLADY.map((p) => (
                <button
                  key={p.popis}
                  className="w-full text-left rounded-xs border border-obrys bg-plocha2 px-3 py-2 transition-colors hover:border-akcent hover:bg-akcentTlumeny group"
                  onClick={() => nastavPopis(p.popis)}
                >
                  <span className="block font-mono text-[0.8125rem] text-text group-hover:text-akcent">
                    {p.popis}
                  </span>
                  <span className="block text-xs text-textTlumeny mt-0.5">
                    {p.vysvetleni}
                  </span>
                </button>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          {chyba ? (
            <Panel>
              <ChybovyStav
                zprava={chyba}
                naObnoveni={() => void zkontroluj(popis, skupina)}
              />
            </Panel>
          ) : !vysledek ? (
            <Panel>
              <PrazdnyStav
                nadpis="Zadejte popis položky"
                popis="Po zadání popisu se zde zobrazí položky katalogu, které mohou označovat tentýž díl, spolu s odůvodněním rozhodnutí."
              />
            </Panel>
          ) : (
            <>
              <div
                className={`panel p-4 border-l-[3px] ${
                  vysledek.nalezena_duplicita
                    ? "border-l-vystraha bg-vystrahaTlumena/35"
                    : "border-l-uspech bg-uspechTlumeny/35"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={
                      vysledek.nalezena_duplicita ? "text-vystraha" : "text-uspech"
                    }
                  >
                    {vysledek.nalezena_duplicita ? (
                      <Ikona.Vystraha velikost={20} />
                    ) : (
                      <Ikona.Fajfka velikost={20} />
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium text-text">
                      {vysledek.nalezena_duplicita
                        ? `Nalezena možná duplicita — ${duplicity.length}× v katalogu`
                        : "Duplicita nebyla nalezena"}
                    </p>
                    <p className="text-sm text-textTlumeny mt-0.5">
                      {vysledek.nalezena_duplicita
                        ? "Před založením záznamu ověřte, zda nejde o tentýž fyzický díl."
                        : "Podobné položky byly nalezeny, žádná z nich však neoznačuje tentýž díl."}
                    </p>
                    {vysledek.zarazeni_iso && (
                      <p className="mt-2 flex items-center gap-2 text-sm">
                        <span className="nadpis-sekce">ISO 14224</span>
                        <span className="odznak-akcent">
                          {vysledek.zarazeni_iso.kod}
                        </span>
                        <span className="text-textTlumeny">
                          {vysledek.zarazeni_iso.nazev_cs}
                        </span>
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {duplicity.length > 0 && (
                <Panel
                  nadpis="Vyhodnoceno jako tentýž díl"
                  popis="Tyto záznamy pravděpodobně označují díl, který zakládáte"
                  bezOdsazeni
                >
                  <div className="divide-y divide-obrys">
                    {duplicity.map((k) => (
                      <Kandidat key={k.itemnum} kandidat={k} zvyrazneno />
                    ))}
                  </div>
                </Panel>
              )}

              {zamitnute.length > 0 && (
                <Panel
                  nadpis="Podobné, ale odlišné položky"
                  popis="Systém u nich nalezl rozpor, který duplicitu vylučuje"
                  bezOdsazeni
                >
                  <div className="divide-y divide-obrys">
                    {zamitnute.map((k) => (
                      <Kandidat key={k.itemnum} kandidat={k} />
                    ))}
                  </div>
                </Panel>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

function Kandidat({
  kandidat,
  zvyrazneno,
}: {
  kandidat: VysledekKontroly["kandidati"][number];
  zvyrazneno?: boolean;
}) {
  return (
    <div
      className={`p-3.5 animate-nastup ${zvyrazneno ? "bg-vystrahaTlumena/25" : ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Kod>{kandidat.itemnum}</Kod>
            {kandidat.je_duplicita ? (
              <span className="odznak-vystraha">možná duplicita</span>
            ) : kandidat.rozpor_atributu ? (
              <span className="odznak-neutralni">odlišný díl</span>
            ) : (
              <span className="odznak-neutralni">pod prahem</span>
            )}
          </div>
          <p className="mt-1 text-text">{kandidat.popis}</p>

          {kandidat.vysvetleni.length > 0 && (
            <p className="mt-1.5 flex items-start gap-1.5 text-xs text-vystraha">
              <span className="mt-px shrink-0">
                <Ikona.Info velikost={13} />
              </span>
              <span>{kandidat.vysvetleni.join(" · ")}</span>
            </p>
          )}
        </div>

        <dl className="shrink-0 space-y-1 text-2xs">
          <SlozkaSkore popisek="celkem" hodnota={kandidat.skore} zvyrazneno />
          <SlozkaSkore popisek="význam" hodnota={kandidat.podobnost_semanticka} />
          <SlozkaSkore popisek="text" hodnota={kandidat.podobnost_lexikalni} />
        </dl>
      </div>
    </div>
  );
}

function SlozkaSkore({
  popisek,
  hodnota,
  zvyrazneno,
}: {
  popisek: string;
  hodnota: number;
  zvyrazneno?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 justify-end">
      <dt
        className={`uppercase tracking-wider ${
          zvyrazneno ? "text-textTlumeny font-semibold" : "text-textSlaby"
        }`}
      >
        {popisek}
      </dt>
      <dd>
        <Skore hodnota={hodnota} sirka={zvyrazneno ? 72 : 52} />
      </dd>
    </div>
  );
}
