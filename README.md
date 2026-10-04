# Bakalářská práce

Tento repozitář obsahuje aplikaci k mé bakalářské práci **Využití AI na sjednocení katalogů a překlad do cizích jazyků**.

**Autor:** Martin Cupák  
**Vedoucí práce:** doc. Ing. Oldřich Trenz, Ph.D.  
**Škola:** Mendelova univerzita v Brně, Provozně ekonomická fakulta

## Co aplikace umí

V katalogu se může stejný díl objevit několikrát: pod jiným názvem, v jiném jazyce nebo s odlišným kódem. Aplikace hledá takové položky pomocí významové podobnosti textu a lexikálního porovnání. Návrhy na sloučení lze posoudit, schválit a následně také zrušit.

Katalog lze na obrazovce *Katalog* vygenerovat jako testovací, nebo importovat z vlastního souboru CSV s libovolnými sloupci. Při importu se určí, který sloupec nese ID, popis, jazyk a případně skupinu; ostatní sloupce se převezmou beze změny. Aktivní je vždy jeden katalog.

Druhou částí je překlad technických textů mezi angličtinou, češtinou, němčinou, italštinou, španělštinou, francouzštinou, čínštinou a japonštinou — od jednotlivých slov po celé pracovní postupy včetně obsahu PDF. Před překladem aplikace vyhledá související termíny ve firemním glosáři a předá je jazykovému modelu jako kontext. Tento postup, označovaný jako Retrieval-Augmented Generation (RAG), má omezit situace, kdy model přeloží stejný odborný termín pokaždé jinak. Termín se do glosáře zadává alespoň ve dvou jazycích, ostatní doplní jazykový model a označí je jako neověřené.

Na obrazovce *Průběh zpracování* je možné prohlédnout jednotlivé kroky překladu, nalezené termíny, sestavený prompt i původní odpověď modelu.

## Spuštění

Níže uvedené příkazy jsou pro Windows. Spouštějte je z kořenového adresáře repozitáře.

Potřebujete:

- Python 3.11 nebo novější,
- nainstalovanou a spuštěnou [Ollamu](https://ollama.com), verze 0.3 nebo novější,
- připojení k internetu pro instalaci závislostí a první stažení modelů.

Node.js je potřeba pouze při úpravách uživatelského rozhraní. Sestavené rozhraní je součástí repozitáře.

### 1. Instalace závislostí a jazykového modelu

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull translategemma:12b
```

### 2. Příprava dat

```powershell
.venv\Scripts\python.exe backend\skripty\generuj_dataset.py
.venv\Scripts\python.exe backend\skripty\generuj_glosar.py
```

První skript vytvoří katalog 5 000 položek a referenční data pro vyhodnocení duplicit (*ground truth*). Druhý připraví glosář včetně terminologie ISO 14224. Oba výstupy jsou součástí repozitáře, takže tento krok není nutný; katalog lze navíc vygenerovat nebo importovat přímo v aplikaci.

### 3. Spuštění aplikace

```powershell
.venv\Scripts\python.exe spustit.py
```

Rozhraní je dostupné na [http://127.0.0.1:8000](http://127.0.0.1:8000), dokumentace REST API na [http://127.0.0.1:8000/api/dokumentace](http://127.0.0.1:8000/api/dokumentace).

Při prvním spuštění se stáhne model LaBSE pro tvorbu vektorových reprezentací textu, přibližně 1,8 GB, a zpracuje se katalog. První start proto trvá déle. Vypočtené reprezentace se ukládají do diskové cache pro další spuštění.

Připravenost dat, modelů a sestaveného rozhraní lze ověřit příkazem:

```powershell
.venv\Scripts\python.exe overit_pripravenost.py
```

Součástí kontroly je i funkční zkouška jazykového a embedding modelu.

## Lokální provoz a volba modelu

Jazykový model běží přes Ollamu, embedding model je uložen v adresáři projektu. Po instalaci závislostí a stažení potřebných modelů lze aplikaci používat bez internetu. Při lokálním provozu se katalog ani překládané texty neposílají do externí služby.

Aplikace nevyžaduje placené API ani předplatné. Nároky na vlastní hardware a dobu zpracování ale zůstávají.

Výchozí jazykový model je `translategemma:12b`, model Gemma 3 doladěný pro překlad mezi 55 jazyky. Samostatná slova překládá správně v 50 z 51 případů (`gemma2:9b` 39, `mistral:7b` 25) a s glosářem dodrží 92 % závazných termínů. Potřebuje přibližně 10 GB paměti; na slabším počítači lze použít `translategemma:4b`. Jiný model lze stáhnout například takto:

```powershell
ollama pull qwen2.5:7b
```

Model se vybírá v horní liště aplikace, která nabízí modely dostupné v místní instalaci Ollama. Volba se ukládá do databáze i se jménem uživatele a časem a zůstává zachována po restartu.

Výchozí model lze změnit proměnnou prostředí `MRO_MODEL_LLM`. Položka *výchozí* v rozhraní vrátí výběr na tuto nakonfigurovanou hodnotu.

## Orientace v repozitáři

```text
thesis/
├── backend/
│   ├── app/
│   │   ├── jadro/        zpracování dat nezávislé na webové vrstvě
│   │   ├── sluzby/       aplikační logika a práce s databází
│   │   ├── api/          REST API
│   │   ├── data/         taxonomie ISO 14224, glosář a šablony komponent
│   │   ├── config.py     konfigurace a laditelné parametry
│   │   └── db.py         schéma SQLite
│   ├── skripty/          příprava katalogu a glosáře
│   └── testy/            jednotkové a integrační testy
├── frontend/
│   ├── src/              zdrojové soubory uživatelského rozhraní
│   └── dist/             sestavené rozhraní, součást repozitáře
├── data/vstup/           katalog, glosář a ground truth
└── modely/               stažený embedding model, není verzován
```

Moduly v `backend/app/jadro/` lze používat i samostatně, bez webového rozhraní.

Backend používá FastAPI, Uvicorn a SQLite. Významové porovnání zajišťuje `sentence-transformers` s modelem LaBSE (768 dimenzí) a indexem HNSW v `faiss-cpu`; lexikální porovnání používá `rapidfuzz`. Překlad běží přes Ollamu, s využitím `langchain-core`.

Rozhraní je napsané v Reactu a TypeScriptu, sestavuje se pomocí Vite a používá Tailwind CSS a Recharts. Pro projekce vektorů pomocí PCA a t-SNE slouží `scikit-learn`, pro vytěžení textu z PDF `pypdf`.

## Vývoj a testování

Testovací sadu spustíte z kořene repozitáře:

```powershell
.venv\Scripts\python.exe -m pytest
```

Testy pokrývají moduly jádra a REST API včetně schválení sloučení položek a jeho zrušení. Jazykový model je v testech nahrazen deterministickým poskytovatelem, takže sada nevyžaduje spuštěnou Ollamu ani připojení k internetu. Neověřuje tím ovšem kvalitu odpovědí skutečného jazykového modelu.

Pro úpravy rozhraní potřebujete Node.js 20 nebo novější:

```powershell
cd frontend
npm install
npm run dev
```

Po dokončení úprav vytvořte sestavení:

```powershell
npm run build
```

Výstup se uloží do `frontend/dist/`, odkud jej používá aplikace.

## Licence

Projekt vznikl jako součást bakalářské práce na Mendelově univerzitě v Brně. Použité knihovny, modely a písmo IBM Plex podléhají vlastním licenčním podmínkám.

Licence těchto závislostí sama o sobě neurčuje podmínky použití zdrojového kódu tohoto projektu.
