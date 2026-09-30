import { useState } from "react";
import { api, type Klastr } from "../api";
import {useNacti} from "../hooky";
import {
  ChybovyStav,
  Ikona,
  Kod,
  Metrika,
  Nacitani,
  OdznakJazyka,
  OdznakStavu,
  Panel,
  PrazdnyStav,
  Skore,
  Strankovac,
  ZahlaviObrazovky,
  formatujCas,
  formatujCislo,
  useOznameni,
} from "../komponenty";

const NA_STRANKU = 8;

export default function Slucovani() {
  const { pridej, vykresli } = useOznameni();
  const [stavFiltru, nastavStavFiltru] = useState("ke_kontrole");
  const [odsazeni, nastavOdsazeni] = useState(0);
  const [mazani, nastavMazani] = useState(false);

  const behy = useNacti(() => api.deduplikace.behy(), []);
  const beh = behy.data?.find((b) => b.stav === "dokonceno") ?? null;
  const statistiky = useNacti(
    () => (beh ? api.slucovani.statistiky(beh.id) : Promise.resolve(null)),
    [beh?.id],
  );
  const klastry = useNacti(
    () =>
      beh
        ? api.deduplikace.klastry(beh.id, {
            stav: stavFiltru,
            limit: NA_STRANKU,
            odsazeni,
          })
        : Promise.resolve(null),
    [beh?.id, stavFiltru, odsazeni],
  );

  const obnovVse = () => {
    klastry.obnov();
    statistiky.obnov();
  };

  const vyprazdni = async () => {
    nastavMazani(false);
    try {
      const odpoved = await api.deduplikace.smazatBehy();
      pridej("uspech", odpoved.zprava);
      behy.obnov();
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Frontu se nepodařilo vyprázdnit.",
      );
    }
  };

  const exportuj = async () => {
    try {
      const odpoved = await api.slucovani.export();
      pridej("uspech", odpoved.zprava);
    } catch (duvod) {
      pridej(
        "chyba",
        duvod instanceof Error ? duvod.message : "Export se nezdařil.",
      );
    }
  };

  const s = (statistiky.data ?? {}) as Record<string, number>;

  return (
    <>
      <ZahlaviObrazovky
        nadpis="Slučování záznamů"
        akce={
          <>
            <button className="tlacitko-vedlejsi" onClick={() => void exportuj()}>
              <Ikona.Stahnout velikost={14} /> Exportovat sloučení
            </button>
            <button
              className="tlacitko-chyba"
              onClick={() => nastavMazani(true)}
              title="Odstraní všechny skupiny ze všech běhů"
            >
              Vyprázdnit frontu
            </button>
          </>
        }
      />

      {mazani && (
        <div className="panel p-4 mb-4 border-chyba">
          <p className="text-sm mb-1">Vyprázdnit frontu ke schválení?</p>
          <p className="text-sm text-textTlumeny mb-3">
            Odstraní se všechny běhy deduplikace včetně skupin a rozhodnutí,
            která jste o nich učinil. Položky katalogu se vrátí do stavu před
            konsolidací. Katalog ani glosář se nemění.
          </p>
          <div className="flex flex-wrap gap-2">
            <button className="tlacitko-chyba" onClick={() => void vyprazdni()}>
              Vyprázdnit
            </button>
            <button
              className="tlacitko-vedlejsi"
              onClick={() => nastavMazani(false)}
            >
              Zrušit
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <Metrika popisek="Ke kontrole" hodnota={formatujCislo(s.ke_kontrole ?? 0)} zvyrazneni="akcent" />
        <Metrika popisek="Schváleno" hodnota={formatujCislo(s.schvaleno ?? 0)} zvyrazneni="uspech" />
        <Metrika popisek="Zamítnuto" hodnota={formatujCislo(s.zamitnuto ?? 0)} />
        <Metrika
          popisek="Sloučených záznamů"
          hodnota={formatujCislo(s.sloucenych_zaznamu ?? 0)}
          zvyrazneni="uspech"
          napoveda="Záznamy označené za duplicitu a navázané na referenční položku."
        />
      </div>

      <Panel
        nadpis="Fronta ke schválení"
        akce={
          <select
            className="pole w-auto py-1 text-[0.8125rem]"
            value={stavFiltru}
            onChange={(e) => {
              nastavStavFiltru(e.target.value);
              nastavOdsazeni(0);
            }}
          >
            <option value="ke_kontrole">ke kontrole</option>
            <option value="schvaleno">schválené</option>
            <option value="zamitnuto">zamítnuté</option>
            <option value="odlozeno">odložené</option>
            <option value="">vše</option>
          </select>
        }
        bezOdsazeni
      >
        {!beh ? (
          <PrazdnyStav
            nadpis="Deduplikace dosud neproběhla"
            popis="Nejprve spusťte deduplikaci na obrazovce Deduplikace."
          />
        ) : klastry.nacita && !klastry.data ? (
          <Nacitani />
        ) : klastry.chyba ? (
          <ChybovyStav zprava={klastry.chyba} naObnoveni={klastry.obnov} />
        ) : klastry.data && klastry.data.celkem === 0 ? (
          <PrazdnyStav
            nadpis={
              stavFiltru === "ke_kontrole"
                ? "Vše je zkontrolováno"
                : "Žádné skupiny v tomto stavu"
            }
            popis={
              stavFiltru === "ke_kontrole"
                ? "Ve frontě nezůstal žádný nevyřízený návrh."
                : undefined
            }
          />
        ) : (
          <>
            <div className="divide-y divide-obrys">
              {klastry.data?.polozky.map((k) => (
                <KartaKeSchvaleni
                  key={k.id}
                  klastr={k}
                  naZmenu={obnovVse}
                  naOznameni={pridej}
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

      {vykresli}
    </>
  );
}

function KartaKeSchvaleni({
  klastr,
  naZmenu,
  naOznameni,
}: {
  klastr: Klastr;
  naZmenu: () => void;
  naOznameni: (druh: "uspech" | "chyba" | "informace", zprava: string) => void;
}) {
  const [zastupce, nastavZastupce] = useState(
    klastr.navrzeny_zastupce ?? klastr.cleny[0]?.itemnum ?? "",
  );
  const [upravenyPopis, nastavUpravenyPopis] = useState("");
  const [poznamka, nastavPoznamku] = useState("");
  const [pracuje, nastavPracuje] = useState(false);
  const [upravuje, nastavUpravuje] = useState(false);

  const platneRozhodnuti = klastr.rozhodnuti.find((r) => r.vzato_zpet === 0);
  const zvolenyZaznam = klastr.cleny.find((c) => c.itemnum === zastupce);

  const rozhodni = async (vysledek: string) => {
    nastavPracuje(true);
    try {
      const odpoved = await api.slucovani.rozhodnout(klastr.id, {
        vysledek,
        zastupce,
        upraveny_popis: upravenyPopis || null,
        poznamka: poznamka || null
      });
      naOznameni("uspech", odpoved.zprava);
      naZmenu();
    } catch (duvod) {
      naOznameni(
        "chyba",
        duvod instanceof Error ? duvod.message : "Rozhodnutí se nepodařilo uložit.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  const vyjmi = async (itemnum: string) => {
    nastavPracuje(true);
    try {
      const odpoved = await api.slucovani.vyjmout(klastr.id, itemnum);
      naOznameni("uspech", odpoved.zprava);
      naZmenu();
    } catch (duvod) {
      naOznameni(
        "chyba",
        duvod instanceof Error ? duvod.message : "Položku se nepodařilo vyjmout.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  const zrus = async () => {
    nastavPracuje(true);
    try {
      const odpoved = await api.slucovani.zrusit(klastr.id);
      naOznameni("uspech", odpoved.zprava);
      naZmenu();
    } catch (duvod) {
      naOznameni(
        "chyba",
        duvod instanceof Error ? duvod.message : "Zrušení se nezdařilo.",
      );
    } finally {
      nastavPracuje(false);
    }
  };

  return (
    <article className="p-4 animate-nastup">
      <header className="flex flex-wrap items-center gap-3 mb-3">
        <span className="odznak-neutralni">skupina #{klastr.id}</span>
        <span className="odznak-neutralni">{klastr.velikost} záznamy</span>
        <Skore hodnota={klastr.prumerna_podobnost} popisek="průměrná podobnost" />
        <OdznakStavu stav={klastr.stav} />
        {klastr.minimalni_podobnost < 0.6 && (
          <span className="odznak-vystraha" title="Nejslabší vazba ve skupině">
            slabá vazba {klastr.minimalni_podobnost.toFixed(2)}
          </span>
        )}
      </header>

      <div className="overflow-x-auto rounded-xs border border-obrys mb-3">
        <table className="tabulka">
          <thead>
            <tr>
              <th className="w-10">Ponechat</th>
              <th>Číslo</th>
              <th>Popis</th>
              <th>Jazyk</th>
              <th>Výrobce</th>
              <th>Stav</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {klastr.cleny.map((c) => {
              const jeZastupce = c.itemnum === zastupce;
              return (
                <tr
                  key={c.itemnum}
                  className={jeZastupce ? "bg-akcentTlumeny/60" : ""}
                >
                  <td>
                    <input
                      type="radio"
                      className="accent-akcent"
                      name={`zastupce-${klastr.id}`}
                      checked={jeZastupce}
                      disabled={Boolean(platneRozhodnuti)}
                      onChange={() => nastavZastupce(c.itemnum)}
                      aria-label={`Ponechat záznam ${c.itemnum}`}
                    />
                  </td>
                  <td>
                    <Kod>{c.itemnum}</Kod>
                    {c.itemnum === klastr.navrzeny_zastupce && (
                      <span className="odznak-akcent ml-2">návrh</span>
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
                  <td>
                    {!platneRozhodnuti && klastr.cleny.length > 1 && (
                      <button
                        className="tlacitko-chyba px-1.5 py-0.5 text-2xs"
                        onClick={() => void vyjmi(c.itemnum)}
                        disabled={pracuje}
                        title={`Položka ${c.itemnum} do této skupiny nepatří`}
                      >
                        nepatří sem
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {platneRozhodnuti ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xs border border-obrys bg-plocha2 px-3.5 py-2.5">
          <div className="text-sm">
            <p className="text-text">
              <OdznakStavu stav={platneRozhodnuti.vysledek} />{" "}
              <span className="ml-1.5 text-textTlumeny">
                rozhodl {platneRozhodnuti.rozhodl},{" "}
                {formatujCas(platneRozhodnuti.rozhodnuto)}
              </span>
            </p>
            {platneRozhodnuti.poznamka && (
              <p className="mt-1 text-xs text-textTlumeny italic">
                „{platneRozhodnuti.poznamka}"
              </p>
            )}
          </div>
          <button
            className="tlacitko-vedlejsi"
            onClick={() => void zrus()}
            disabled={pracuje}
          >
            <Ikona.Obnovit velikost={14} /> Vrátit zpět
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {upravuje && (
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="stitek-pole">
                  Upravený popis referenčního záznamu
                </label>
                <input
                  className="pole"
                  placeholder={zvolenyZaznam?.description ?? ""}
                  value={upravenyPopis}
                  onChange={(e) => nastavUpravenyPopis(e.target.value)}
                />
              </div>
              <div>
                <label className="stitek-pole">Poznámka k rozhodnutí</label>
                <input
                  className="pole"
                  placeholder="například: ověřeno u dodavatele"
                  value={poznamka}
                  onChange={(e) => nastavPoznamku(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              className="tlacitko-uspech"
              onClick={() => void rozhodni("schvaleno")}
              disabled={pracuje || !zastupce}
            >
              <Ikona.Fajfka velikost={14} /> Sloučit do {zastupce}
            </button>
            <button
              className="tlacitko-chyba"
              onClick={() => void rozhodni("zamitnuto")}
              disabled={pracuje}
            >
              <Ikona.Krizek velikost={14} /> Nejde o duplicitu
            </button>
            <button
              className="tlacitko-vedlejsi"
              onClick={() => void rozhodni("odlozeno")}
              disabled={pracuje}
            >
              Odložit
            </button>
            <button
              className="tlacitko-tichy ml-auto text-xs"
              onClick={() => nastavUpravuje(!upravuje)}
            >
              {upravuje ? "Skrýt" : "Upravit popis nebo poznámku"}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
