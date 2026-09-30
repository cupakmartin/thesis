export const ZAKLAD = "/api";

export class ChybaApi extends Error {
  constructor(
    public readonly stav: number,
    zprava: string,
  ) {
    super(zprava);
    this.name = "ChybaApi";
  }
}

async function zavolej<T>(cesta: string, moznosti: RequestInit = {}): Promise<T> {
  let odpoved: Response;
  try {
    odpoved = await fetch(`${ZAKLAD}${cesta}`, {
      headers: { "Content-Type": "application/json", ...(moznosti.headers ?? {}) },
      ...moznosti,
    });
  } catch {
    throw new ChybaApi(
      0,
      "Server neodpovídá. Ověřte, že aplikace běží (spustit.py).",
    );
  }

  if (!odpoved.ok) {
    let podrobnost = `Server odpověděl chybou ${odpoved.status}.`;
    try {
      const telo = await odpoved.json();
      if (telo?.detail) {
        podrobnost =
          typeof telo.detail === "string"
            ? telo.detail
            : JSON.stringify(telo.detail);
      }
    } catch {
      /* tělo odpovědi nebylo ve formátu JSON */
    }
    throw new ChybaApi(odpoved.status, podrobnost);
  }

  if (odpoved.status === 204) return undefined as T;
  return (await odpoved.json()) as T;
}

const ziskej = <T>(cesta: string) => zavolej<T>(cesta);
const posli = <T>(cesta: string, telo?: unknown) =>
  zavolej<T>(cesta, { method: "POST", body: telo ? JSON.stringify(telo) : undefined });
const uprav = <T>(cesta: string, telo: unknown) =>
  zavolej<T>(cesta, { method: "PUT", body: JSON.stringify(telo) });
const smaz = <T>(cesta: string) => zavolej<T>(cesta, { method: "DELETE" });

function parametry(hodnoty: Record<string, unknown>): string {
  const vysledek = new URLSearchParams();
  for (const [klic, hodnota] of Object.entries(hodnoty)) {
    if (hodnota === undefined || hodnota === null || hodnota === "") continue;
    vysledek.set(klic, String(hodnota));
  }
  const text = vysledek.toString();
  return text ? `?${text}` : "";
}

export interface Strankovani<T> {
  polozky: T[];
  celkem: number;
  limit: number;
  odsazeni: number;
}

export interface Potvrzeni {
  uspech: boolean;
  zprava: string;
  podrobnosti: Record<string, unknown>;
}

export interface StavSystemu {
  katalog_nacten: boolean;
  pocet_polozek: number;
  index_pripraven: boolean;
  glosar_nacten: boolean;
  pocet_terminu: number;
  ollama_dostupna: boolean;
  dostupne_modely: string[];
  aktivni_model: string;
  vychozi_model: string;
  model_prepnut_uzivatelem: boolean;
  model_embeddingu: string;
  offline_rezim: boolean;
}

export interface StavVolbyModelu {
  aktivni: string;
  vychozi: string;
  dostupne: string[];
  doporucene: string[];
  ollama_dostupna: boolean;
  prepnuto_uzivatelem: boolean;
  nainstalovan: boolean;
}

export interface Polozka {
  itemnum: string;
  description: string;
  long_description: string | null;
  itemtype: string | null;
  commodity_group: string | null;
  order_unit: string | null;
  issue_unit: string | null;
  status: string | null;
  rotating: number;
  manufacturer: string | null;
  model_num: string | null;
  vendor: string | null;
  external_ref_id: string | null;
  iso_class: string | null;
  lang_code: string | null;
  change_date: string | null;
  change_by: string | null;
  stav_konsolidace: string;
  slouceno_do: string | null;
  zarazeni_iso?: ZarazeniIso | null;
}

export interface ZarazeniIso {
  kod: string;
  nazev_cs: string;
  nazev_en?: string;
  jistota: number;
  zpusob?: string;
  zduvodneni: string;
}

export interface Dvojice {
  id: number;
  klastr_id: number;
  itemnum_a: string;
  itemnum_b: string;
  podobnost_semanticka: number;
  podobnost_lexikalni: number;
  skore_atributu: number;
  skore: number;
  vysvetleni: string | null;
}

export interface Rozhodnuti {
  id: number;
  klastr_id: number;
  vysledek: string;
  zastupce: string | null;
  upraveny_popis: string | null;
  poznamka: string | null;
  rozhodl: string;
  rozhodnuto: string;
  vzato_zpet: number;
}

export interface Klastr {
  id: number;
  beh_id: number;
  poradi: number;
  velikost: number;
  prumerna_podobnost: number;
  minimalni_podobnost: number;
  navrzeny_zastupce: string | null;
  stav: string;
  cleny: Polozka[];
  dvojice: Dvojice[];
  rozhodnuti: Rozhodnuti[];
}

export interface Beh {
  id: number;
  zalozeno: string;
  dokonceno: string | null;
  stav: string;
  metoda: string;
  nastaveni_json: string;
  pocet_polozek: number;
  pocet_klastru: number;
  pocet_duplicit: number;
  doba_s: number;
  spustil: string | null;
  chyba: string | null;
}

export interface Kandidat {
  itemnum: string;
  popis: string;
  komoditni_skupina?: string;
  vyrobce?: string;
  podobnost_semanticka: number;
  podobnost_lexikalni: number;
  skore_atributu?: number;
  skore: number;
  je_duplicita: boolean;
  rozpor_atributu: boolean;
  vysvetleni: string[];
}

export interface VysledekKontroly {
  pocet_kandidatu: number;
  nalezena_duplicita: boolean;
  kandidati: Kandidat[];
  zarazeni_iso: ZarazeniIso | null;
}

export interface NalezenyTermin {
  id: string;
  termin_en: string;
  termin_cs: string;
  definice: string;
  nespravne: string;
  kategorie: string;
  zdroj: string;
  zpusob: string;
  skore: number;
}

export interface KontrolaTerminu {
  termin_zdroj: string;
  termin_cil: string;
  ocekavan: boolean;
  dodrzen: boolean;
  nespravna_varianta: string;
  nespravna_varianta_pouzita: boolean;
}

export interface Validace {
  mira_dodrzeni_glosare: number;
  pocet_ocekavanych: number;
  pocet_dodrzenych: number;
  pocet_nespravnych_variant: number;
  identifikatory_zachovany: boolean;
  chybejici_identifikatory: string[];
  varovani: string[];
  je_v_poradku: boolean;
  souhrn: string;
  kontroly: KontrolaTerminu[];
}

export interface VysledekPrekladu {
  zdrojovy_text: string;
  preklad: string;
  zdrojovy_jazyk: string;
  cilovy_jazyk: string;
  pouzity_glosar: boolean;
  model: string;
  doba_s: number;
  doba_vyhledani_s: number;
  doba_generovani_s: number;
  systemova_instrukce: string;
  nalezene_terminy: NalezenyTermin[];
  validace: Validace;
}

export interface TerminGlosare {
  id: string;
  termin_en: string;
  termin_cs: string;
  kategorie: string;
  definice: string;
  nespravne: string;
  zdroj: string;
}


export interface UdalostMIF {
  id: number;
  prijato: string;
  typ_udalosti: string;
  itemnum: string | null;
  obsah_json: string;
  zpracovano: number;
  vysledek_json: string | null;
  chyba: string | null;
}

export interface Prehled {
  katalog: {
    pocet_polozek: number;
    pocet_slouceno: number;
    podle_komoditni_skupiny: { nazev: string; pocet: number }[];
    podle_iso_tridy: { nazev: string; pocet: number }[];
    podle_jazyka: { nazev: string; pocet: number }[];
  };
  posledni_beh: Beh | null;
  slucovani: {
    ke_kontrole: number;
    schvaleno: number;
    zamitnuto: number;
    odlozeno: number;
    sloucenych_zaznamu: number;
  };
  preklady: {
    pocet_prekladu: number;
    podle_glosare: Record<string, { pocet: number; prumerne_dodrzeni: number }>;
  };
}

export interface NastaveniDeduplikace {
  metoda: string;
  prah_rozhodnuti: number;
  prah_kandidatu: number;
  pocet_sousedu: number;
  uplatnit_atributy: boolean;
  omezit_na_tridu_iso: boolean;
  prisne_shlukovani: boolean;
}

export const api = {
  system: {
    stav: () => ziskej<StavSystemu>("/system/stav"),
    prehled: () => ziskej<Prehled>("/system/prehled"),
    volbaModelu: () => ziskej<StavVolbyModelu>("/system/model"),
    zmenModel: (model: string | null) =>
      uprav<StavVolbyModelu>("/system/model", { model }),
  },

  polozky: {
    seznam: (f: Record<string, unknown>) =>
      ziskej<Strankovani<Polozka>>(`/polozky${parametry(f)}`),
    detail: (itemnum: string) => ziskej<Polozka>(`/polozky/${itemnum}`),
    filtry: () =>
      ziskej<Record<string, string[]>>("/polozky/filtry"),
    importuj: () => posli<Potvrzeni>("/polozky/import", {}),
    xml: (itemnum: string) =>
      fetch(`${ZAKLAD}/polozky/${itemnum}/xml`).then((o) => o.text()),
  },

  deduplikace: {
    spustit: (n: NastaveniDeduplikace) =>
      posli<Potvrzeni>("/deduplikace/spustit", n),
    behy: () => ziskej<Beh[]>("/deduplikace/behy"),
    smazatBehy: () => smaz<Potvrzeni>("/deduplikace/behy"),
    klastry: (behId: number, f: Record<string, unknown>) =>
      ziskej<Strankovani<Klastr>>(
        `/deduplikace/behy/${behId}/klastry${parametry(f)}`,
      ),
    klastr: (id: number) => ziskej<Klastr>(`/deduplikace/klastry/${id}`),
    kontrolaPolozky: (telo: {
      popis: string;
      komoditni_skupina?: string;
      itemnum?: string;
      pocet_kandidatu?: number;
    }) => posli<VysledekKontroly>("/deduplikace/kontrola-polozky", telo),
  },

  slucovani: {
    rozhodnout: (
      klastrId: number,
      telo: {
        vysledek: string;
        zastupce?: string | null;
        upraveny_popis?: string | null;
        poznamka?: string | null;
      },
    ) => posli<Potvrzeni>(`/slucovani/klastry/${klastrId}/rozhodnout`, telo),
    vyjmout: (klastrId: number, itemnum: string, poznamka?: string) =>
      posli<Potvrzeni>(`/slucovani/klastry/${klastrId}/vyjmout`, {
        itemnum,
        poznamka: poznamka ?? "",
      }),
    zrusit: (klastrId: number) =>
      posli<Potvrzeni>(
        `/slucovani/klastry/${klastrId}/zrusit`,
      ),
    statistiky: (behId?: number) =>
      ziskej<Record<string, unknown>>(
        `/slucovani/statistiky${parametry({ beh_id: behId })}`,
      ),
    export: () => posli<Potvrzeni>("/slucovani/export"),
  },

  preklad: {
    prelozit: (telo: {
      text: string;
      zdrojovy_jazyk: string;
      cilovy_jazyk: string;
      pouzit_glosar: boolean;
      model?: string | null;
      temperature?: number | null;
      itemnum?: string | null;
    }) => posli<VysledekPrekladu>("/preklad", telo),
    historie: (f: Record<string, unknown>) =>
      ziskej<Strankovani<Record<string, unknown>>>(
        `/preklad/historie${parametry(f)}`,
      ),
  },

  glosar: {
    seznam: (f: Record<string, unknown>) =>
      ziskej<Strankovani<TerminGlosare>>(`/glosar${parametry(f)}`),
    kategorie: () => ziskej<string[]>("/glosar/kategorie"),
    pridat: (telo: Partial<TerminGlosare>) =>
      posli<Potvrzeni>("/glosar", telo),
    upravit: (id: string, telo: Partial<TerminGlosare>) =>
      uprav<Potvrzeni>(`/glosar/${id}`, telo),
    smazat: (id: string) => smaz<Potvrzeni>(`/glosar/${id}`),
  },

  mif: {
    objektovaStruktura: () =>
      ziskej<Record<string, unknown>>("/mif/objektova-struktura"),
    odeslatUdalost: (telo: {
      typ_udalosti: string;
      obsah: Record<string, unknown>;
    }) => posli<Record<string, unknown>>("/mif/udalost", telo),
    udalosti: (f: Record<string, unknown>) =>
      ziskej<Strankovani<UdalostMIF>>(`/mif/udalosti${parametry(f)}`),
  },

};
