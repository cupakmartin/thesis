import { useEffect, useState } from "react";
import { api, type Klastr, type NastaveniDeduplikace } from "../api";
import { useNacti, useSledovaniPostupu } from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Nacitani,
  OdznakJazyka,
  OdznakStavu,
  Panel,
  PrazdnyStav,
  Skore,
  Strankovac,
  UkazatelPostupu,
  ZahlaviObrazovky,
  formatujCas,
  formatujCislo,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 10;

const VYCHOZI: NastaveniDeduplikace = {
  metoda: "hybridni",
  prah_rozhodnuti: 0.72,
  prah_kandidatu: 0.55,
  pocet_sousedu: 16,
  uplatnit_atributy: true,
  omezit_na_tridu_iso: false,
  prisne_shlukovani: true,
};

export default function Deduplikace() {
  const { pridej, vykresli } = useOznameni();
  const [nastaveni, nastavNastaveni] = useState<NastaveniDeduplikace>(VYCHOZI);
  const [pracuje, nastavPracuje] = useState(false);
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [potvrzeni, nastavPotvrzeni] = useState(false);
  const [rozbaleny, nastavRozbaleny] = useState<number | null>(null);

  const [sledovat, nastavSledovat] = useState(false);
  const postup = useSledovaniPostupu(api.deduplikace.prubeh, pracuje || sledovat);

  const behy = useNacti(() => api.deduplikace.behy(), []);

  useEffect(() => {
    api.deduplikace
      .prubeh()
      .then((snimek) => {
        if (snimek.stav === "bezi") nastavSledovat(true);
      })
      .catch(() => undefined);
  }, []);

  const obnovBehy = behy.obnov;
  useEffect(() => {
    if (sledovat && !pracuje && postup && postup.stav !== "bezi") {
      nastavSledovat(false);
      obnovBehy();
    }
  }, [sledovat, pracuje, postup, obnovBehy]);
  const aktualniBeh = behy.data?.find((b) => b.stav === "dokonceno") ?? null;

  const klastry = useNacti(
    () =>
      aktualniBeh
        ? api.deduplikace.klastry(aktualniBeh.id, {
            limit: NA_STRANKU,
            odsazeni,
          })
        : Promise.resolve(null),
    [aktualniBeh?.id, odsazeni],
  );

  const spust = () => {
    if (aktualniBeh) {
      nastavPotvrzeni(true);
      return;
    }
    void spustNyni();
  };

  const uprav = <K extends keyof NastaveniDeduplikace>(
    klic: K,
    hodnota: NastaveniDeduplikace[K],
  ) => nastavNastaveni((s) => ({ ...s, [klic]: hodnota }));

  const spustNyni = async () => {
    nastavPotvrzeni(false);
    nastavPracuje(true);
    try {
      const odpoved = await api.deduplikace.spustit(nastaveni);
      pridej("uspech", odpoved.zprava);
      nastavOdsazeni(0);
      behy.obnov();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Deduplikaci se nepodařilo spustit.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  return (
    <>
      <ZahlaviObrazovky nadpis="Deduplikace katalogu" />

      {potvrzeni && (
        <div className="panel p-4 mb-4 border-vystraha">
          <p className="text-sm mb-1">
            Nový běh nahradí výsledky předchozího.
          </p>
          <p className="text-sm text-textTlumeny mb-3">
            Stávající běh obsahuje{" "}
            {formatujCislo(aktualniBeh?.pocet_klastru ?? 0)} skupin. Ty budou
            odstraněny včetně dosud nevyřízených návrhů ve frontě ke schválení.
            Rozhodnutí, která jste již potvrdil, se rovněž ztratí.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="tlacitko-hlavni"
              onClick={() => void spustNyni()}
              disabled={pracuje}
            >
              Nahradit a spustit
            </button>
            <button
              className="tlacitko-vedlejsi"
              onClick={() => nastavPotvrzeni(false)}
            >
              Zrušit
            </button>
          </div>
        </div>
      )}

      <div className="grid xl:grid-cols-[minmax(0,23rem)_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel
            nadpis="Nastavení běhu"
            akce={
              <button
                className="tlacitko-tichy text-xs"
                onClick={() => nastavNastaveni(VYCHOZI)}
              >
                Výchozí
              </button>
            }
          >
            <div className="space-y-4">
              <div>
                <label className="stitek-pole">Metoda</label>
                <select
                  className="pole"
                  value={nastaveni.metoda}
                  onChange={(e) => uprav("metoda", e.target.value)}
                >
                  <option value="hybridni">hybridní - vážené skóre</option>
                  <option value="pravidlova">pravidlová - rozhodovací pravidlo</option>
                  <option value="semanticka">sémantická - pouze kosinová podobnost</option>
                  <option value="lexikalni">lexikální - pouze porovnání řetězců</option>
                </select>
                <p className="mt-1.5 text-xs text-textSlaby">
                  {POPIS_METODY[nastaveni.metoda]}
                </p>
              </div>

              <Posuvnik
                popisek="Práh rozhodnutí"
                hodnota={nastaveni.prah_rozhodnuti}
                naZmenu={(h) => uprav("prah_rozhodnuti", h)}
                min={0.4}
                max={0.95}
                napoveda="Vyšší hodnota zvyšuje přesnost, snižuje úplnost."
              />
              <Posuvnik
                popisek="Práh záchytu kandidátů"
                hodnota={nastaveni.prah_kandidatu}
                naZmenu={(h) => uprav("prah_kandidatu", h)}
                min={0.3}
                max={0.9}
                napoveda="Dolní mez pro vstup dvojice do druhé fáze."
              />

              <div>
                <label className="stitek-pole">
                  Počet nejbližších sousedů - {nastaveni.pocet_sousedu}
                </label>
                <input
                  type="range"
                  className="w-full accent-akcent"
                  min={4}
                  max={50}
                  step={1}
                  value={nastaveni.pocet_sousedu}
                  onChange={(e) => uprav("pocet_sousedu", Number(e.target.value))}
                />
                <p className="mt-1 text-xs text-textSlaby">
                  Vyšší hodnota nachází více mezijazyčných duplicit za cenu nižší
                  přesnosti. Měřeno: 8 sousedů → 61 % překladových duplicit,
                  50 sousedů → 80 %.
                </p>
              </div>

              <div className="space-y-2 pt-1">
                <Prepinac
                  popisek="Atributová fáze"
                  napoveda="Rozpor v číslech dílů, rozměrech či jmenovitých hodnotách vylučuje duplicitu."
                  hodnota={nastaveni.uplatnit_atributy}
                  naZmenu={(h) => uprav("uplatnit_atributy", h)}
                />
                <Prepinac
                  popisek="Úplné propojení klastru"
                  napoveda="Zabraňuje řetězení, kdy jediná chybná vazba spojí dvě jinak správné skupiny."
                  hodnota={nastaveni.prisne_shlukovani}
                  naZmenu={(h) => uprav("prisne_shlukovani", h)}
                />
                <Prepinac
                  popisek="Omezit na shodnou třídu ISO 14224"
                  napoveda="Kapitola 2.2.4 - položky různých tříd zařízení nelze sloučit."
                  hodnota={nastaveni.omezit_na_tridu_iso}
                  naZmenu={(h) => uprav("omezit_na_tridu_iso", h)}
                />
              </div>

              <button
                className="tlacitko-hlavni w-full"
                onClick={() => void spust()}
                disabled={pracuje || sledovat}
              >
                {pracuje || sledovat ? (
                  "Zpracovávám…"
                ) : (
                  <>
                    <Ikona.Spustit velikost={14} /> Spustit deduplikaci
                  </>
                )}
              </button>
              {(pracuje || sledovat) &&
                (postup?.stav === "bezi" ? (
                  <UkazatelPostupu postup={postup} />
                ) : (
                  <div className="ukazatel h-1.5">
                    <div className="ukazatel-vypln prubeh-neurcity w-full" />
                  </div>
                ))}
            </div>
          </Panel>

          <Panel nadpis="Historie běhů" bezOdsazeni>
            {behy.data && behy.data.length > 0 ? (
              <ul className="divide-y divide-obrys max-h-72 overflow-y-auto">
                {behy.data.map((b) => (
                  <li key={b.id} className="px-4 py-2.5 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[0.8125rem] text-text">
                        #{b.id}
                      </span>
                      <span className="text-2xs text-textSlaby">
                        {formatujCas(b.dokonceno ?? b.zalozeno)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-textTlumeny">
                      {b.metoda} · {formatujCislo(b.pocet_klastru)} skupin ·{" "}
                      {b.doba_s.toFixed(2)} s
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-sm text-textTlumeny">
                Zatím neproběhl žádný běh.
              </p>
            )}
          </Panel>
        </div>

        <Panel
          nadpis="Nalezené skupiny duplicit"
          popis={
            aktualniBeh
              ? `Běh #${aktualniBeh.id} · ${formatujCislo(aktualniBeh.pocet_klastru)} skupin · ${formatujCislo(aktualniBeh.pocet_duplicit)} nadbytečných záznamů`
              : undefined
          }
          bezOdsazeni
        >
          {!aktualniBeh ? (
            <PrazdnyStav
              nadpis="Deduplikace dosud neproběhla"
              popis="Nastavte parametry a spusťte první běh."
            />
          ) : klastry.nacita && !klastry.data ? (
            <Nacitani />
          ) : klastry.chyba ? (
            <ChybovyStav zprava={klastry.chyba} naObnoveni={klastry.obnov} />
          ) : klastry.data && klastry.data.celkem === 0 ? (
            <PrazdnyStav
              nadpis="Nebyly nalezeny žádné duplicity"
              popis="Při zvoleném nastavení systém neoznačil žádnou dvojici za tentýž díl. Zkuste snížit práh rozhodnutí."
            />
          ) : (
            <>
              <div className="divide-y divide-obrys">
                {klastry.data?.polozky.map((k) => (
                  <KartaKlastru
                    key={k.id}
                    klastr={k}
                    rozbaleno={rozbaleny === k.id}
                    naPrepnuti={() =>
                      nastavRozbaleny(rozbaleny === k.id ? null : k.id)
                    }
                  />
                ))}
              </div>
              {klastry.data && (
                <Strankovac
                  celkem={klastry.data.celkem}
                  limit={NA_STRANKU}
                  odsazeni={odsazeni}
                  naZmenu={nastavOdsazeni}
                />
              )}
            </>
          )}
        </Panel>
      </div>

      {vykresli}
    </>
  );
}

const POPIS_METODY: Record<string, string> = {
  hybridni:
    "Vážený součet významové podobnosti, textové podobnosti a shody atributů.",
  pravidlova:
    "Požadovaná míra podobnosti se odvíjí od počtu potvrzených atributů.",
  semanticka:
    "Postup dle kapitoly 3.4.1. Měřením doložena přesnost 0,001 - slouží ke srovnání.",
  lexikalni:
    "Tradiční porovnávání řetězců dle kapitoly 2.3.1. Slouží jako referenční základna.",
};

function Posuvnik({
  popisek,
  hodnota,
  naZmenu,
  min,
  max,
  napoveda,
}: {
  popisek: string;
  hodnota: number;
  naZmenu: (h: number) => void;
  min: number;
  max: number;
  napoveda: string;
}) {
  return (
    <div>
      <label className="stitek-pole">
        {popisek} -{" "}
        <span className="font-mono text-text">{hodnota.toFixed(2)}</span>
      </label>
      <input
        type="range"
        className="w-full accent-akcent"
        min={min}
        max={max}
        step={0.01}
        value={hodnota}
        onChange={(e) => naZmenu(Number(e.target.value))}
      />
      <p className="mt-1 text-xs text-textSlaby">{napoveda}</p>
    </div>
  );
}

function Prepinac({
  popisek,
  napoveda,
  hodnota,
  naZmenu,
}: {
  popisek: string;
  napoveda: string;
  hodnota: boolean;
  naZmenu: (h: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2.5 cursor-pointer group">
      <input
        type="checkbox"
        className="mt-0.5 accent-akcent"
        checked={hodnota}
        onChange={(e) => naZmenu(e.target.checked)}
      />
      <span className="min-w-0">
        <span className="block text-sm text-text">{popisek}</span>
        <span className="block text-xs text-textSlaby">{napoveda}</span>
      </span>
    </label>
  );
}

export function KartaKlastru({
  klastr,
  rozbaleno,
  naPrepnuti,
}: {
  klastr: Klastr;
  rozbaleno: boolean;
  naPrepnuti: () => void;
}) {
  return (
    <article className="animate-nastup">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-plocha2"
        onClick={naPrepnuti}
      >
        <span className="odznak-neutralni shrink-0">{klastr.velikost} záznamy</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-text">
            {klastr.cleny[0]?.description}
          </span>
          <span className="block truncate text-xs text-textSlaby mt-0.5">
            {klastr.cleny
              .slice(1)
              .map((c) => c.description)
              .join("  ·  ")}
          </span>
        </span>
        <span className="shrink-0 hidden sm:block">
          <Skore hodnota={klastr.prumerna_podobnost} popisek="průměrná podobnost" />
        </span>
        <OdznakStavu stav={klastr.stav} />
        <span
          className={`shrink-0 text-textSlaby transition-transform ${rozbaleno ? "rotate-90" : ""}`}
        >
          <Ikona.Sipka velikost={15} />
        </span>
      </button>

      {rozbaleno && (
        <div className="px-4 pb-4 space-y-3 animate-nastup">
          <div className="overflow-x-auto rounded-xs border border-obrys">
            <table className="tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Popis</th>
                  <th>Jazyk</th>
                  <th>Výrobce</th>
                  <th>Stav</th>
                </tr>
              </thead>
              <tbody>
                {klastr.cleny.map((c) => (
                  <tr key={c.itemnum}>
                    <td>
                      <Kod>{c.itemnum}</Kod>
                      {c.itemnum === klastr.navrzeny_zastupce && (
                        <span className="odznak-akcent ml-2">referenční</span>
                      )}
                    </td>
                    <td className="text-text">{c.description}</td>
                    <td>
                      <OdznakJazyka kod={c.lang_code} />
                    </td>
                    <td className="text-textTlumeny">{c.manufacturer}</td>
                    <td>
                      <OdznakStavu stav={c.status ?? ""} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <p className="nadpis-sekce mb-2">Vyhodnocené dvojice</p>
            <div className="space-y-1.5">
              {klastr.dvojice.map((d) => (
                <div
                  key={d.id}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xs bg-plocha2 px-3 py-2 text-xs"
                >
                  <span className="font-mono text-textTlumeny">
                    {d.itemnum_a} ↔ {d.itemnum_b}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="text-textSlaby uppercase tracking-wider">
                      celkem
                    </span>
                    <Skore hodnota={d.skore} sirka={56} />
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="text-textSlaby uppercase tracking-wider">
                      význam
                    </span>
                    <Skore hodnota={d.podobnost_semanticka} sirka={44} />
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="text-textSlaby uppercase tracking-wider">
                      text
                    </span>
                    <Skore hodnota={d.podobnost_lexikalni} sirka={44} />
                  </span>
                </div>
              ))}
            </div>
          </div>

          {klastr.minimalni_podobnost < 0.6 && (
            <p className="flex items-start gap-1.5 text-xs text-vystraha">
              <span className="mt-px">
                <Ikona.Info velikost={13} />
              </span>
              Nejslabší vazba ve skupině má skóre{" "}
              {klastr.minimalni_podobnost.toFixed(3)}. Ověřte, zda skupina
              nespojuje odlišné díly.
            </p>
          )}
        </div>
      )}
    </article>
  );
}
