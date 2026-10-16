# Implementační report MND 0.1.0

Vývoj byl zahájen 16. 10. 2026 na pokyn „Programuj“. Jde o vývojovou verzi,
**nikoli ověřené produkční vydání nebo dokončenou cloudovou paritu C#**.
Kód je v jediném určeném pracovním kořeni, s vlastní větví `master_HA`.
Reference C# a ČEZ nebyly upraveny. ORLEN/EDC nejsou součástí runtime.

## Skutečně provedené kontroly

- Python 3.12.14 ve Windows: **100 testů úspěšně**, včetně doménových a
  protokolových regresí a syntetických XLSX/PDF/ZIP/Git fixtures (16. 10. 2026).
- Node 24.19.0: DOM komponenty přes happy-dom, registry vazby generátoru,
  zachování cizích views, řízené release API a rozměry/alfa brand PNG:
  **21 testů úspěšně**.
- Ruff, kompilace Pythonu a kontrola syntaxe JavaScriptu.
- Celkové pokrytí Python runtime v této místní sadě je **50 % včetně větví**.
  Zahrnuje i dosud nespouštěné HA adaptéry s nulovým pokrytím; samotná sada
  doménových testů není důkazem správné funkce těchto adaptérů v HA.
- Vizuální kontrola souborů ikon v 256 px a kontrolního listu ve 32/64 px
  na světlém i tmavém pozadí. PNG exporty vznikají z vlastního SVG.
- Veřejný průzkum Moje MND bez loginu: HTML, konfigurace a veřejné JS/CSS.
  Zdrojová evidence je v `docs/AUTENTIZACE.md` a `docs/VZHLED_MND.md`.

Náhled se syntetickými daty vytvoří `python scripts/create_preview.py` do
ignorovaného `output/preview/`. Používá skutečnou komponentu, účetní projekci
a generátor; žádné provozní údaje ani oprávnění k zápisu. Místní server při
vývoji poslouchá pouze na `127.0.0.1:8766`. Náhled není emulace HA lifecycle.

## Neprovedené ověření a zbývající práce

1. Skutečné lifecycle, oprávnění HTTP/WS, služby, Recorder, přejmenování
   entity a frontend v HA **2026.3.1 / plugin 0.13.317** a v aktuální stable.
   Resolver při kontrole našel **2026.10.1 / plugin 0.13.372 / Python 3.14**.
   Místně je Python 3.12 ve Windows, není dostupné Linux prostředí ani WSL
   distribuce. Připravená CI matice zatím nebyla spuštěna. Kontrola zdrojového
   API HA není náhradou skutečného běhu.
2. HACS a Hassfest. Pracovní manifest obsahuje plánovanou GitHub adresu;
   repozitář zatím neexistuje. Workflow je připravené, nikoli úspěšné.
3. Nový oprávněný živý test přihlášení a odpovědí účtu MND v HA. Nečetla jsem
   staré přístupy a neprováděla nový zákaznický login. MFA, skutečné limity,
   výměna smlouvy a celý cloudový tok zůstávají neověřené.
4. Automatické převzetí plných smluvních cen z portálu: surový detail a
   smluvní doklady se uchovávají; jednotky, platnost, DPH a plnost složek se
   zatím zadávají nebo importují z doloženého C# v1. Nejsou hádány z textu.
   Platební zpráva MND se přebírá z v1; její živá mapa není doložena.
5. Vizuální QA v HA na mobilu/desktopu a ověření dialogu brand obrázků.
   CUA nevrátil dostupný prohlížeč. DOM testy nejsou screenshotové ověření.
6. Po úspěšných kontrolách vytvořit neměnný tag, instalační ZIP z tohoto
   tagu a draft. V tomto projektu zatím není release tag, instalační ZIP,
   veřejný remote, draft ani instalace do živého HA.

Přidání do Overview používá kontrolu celé konfigurace těsně před jedním
zápisem a následné čtení. Nativní HA save nemá CAS, proto nelze garantovat
ochranu proti cizímu zápisu přesně během samotného save. Kolize stávajících
MND views se odmítá, místní kompozice se nepřebírá ani automaticky nepřepisuje.
JSON fragment je platný YAML; komentáře a pravidla jsou v dokumentaci a
samostatných metadatech generátoru, storage Lovelace neuchovává YAML komentáře.

## Matice funkcí

„Unit OK“ znamená synteticky provedený test příslušné logiky. „HA čeká“
nebo „live čeká“ se nesmí vydávat za funkční ověření celé funkce.
Uváděné cesty modulů jsou relativní k `custom_components/mnd_tariff_accounting/`.

| ID | Implementace | Konkrétní test / skutečný výsledek |
| --- | --- | --- |
| M01 | `portal.py`, `config_flow.py`, API logout/forget | `test_portal`: login, odmítnutí, HTML, redirect, backoff OK; config/reauth a live čekají |
| M02 | více entry/míst, registry, `technical_details` | `frontend.test.js`: více účtů a opožděná odpověď OK; lifecycle a živý detail čekají |
| M03 | `projection.py`, oddělené zálohy/hodnocení/platební zpráva | projekce a import unit OK; zpráva platby z v1, živá mapa platebního stavu čeká |
| M04 | `accounting.py`, verzované role tarifů, import/editor | `test_alternative_not_charged`, změna sazby a DPH OK; automatická interpretace portálových smluvních cen čeká |
| M05 | soukromé SHA originály, autentizovaný download, portálové doklady | `test_zip_roundtrip_with_original` OK; skutečný HA download a živé smluvní PDF čekají |
| M06 | profil/platby na vyžádání, chráněný panel | DOM test vyžádání a escapování profilu OK; live profil/platby čekají |
| M07 | export obou dnů včetně, metadata a přijetí XLSX | `test_export_payload_and_document_validation` OK; skutečný export účtu čeká |
| M08 | `history.py`, kurzor, 366 dní / 10 až 100 úseků / 15 min | plán a import unit OK; celý HA běh/pokrytí čeká, bez důkazu počátku vždy unverified |
| M09 | `core/xlsx.py`, upload a náhled | testy workbook identity, oba kalendáře, česká čísla OK; HA upload čeká |
| M10 | `core/metering.py`, doklady/bod/revize/segment | statusy, konflikt, reset, priority unit OK |
| M11 | `editing.py`, formulář a akce, import ručního Actual | testy editoru a projekce OK; HA služba čeká |
| M12 | nativní registry/events/Recorder, kalibrace | reset, návaznost a DST profil unit OK; registry/Recorder v HA čekají |
| M13 | priorita MND a pracovní odvozený senzorový bod | rebase 1000→1030 a oprava 1002→1032 unit OK; živá návaznost čeká |
| M14 | denní i přesné časové účetnictví, paušály, zálohy, saldo | `test_domain.AccountingTests`, `test_temporal` OK; skutečné podklady účtu čekají |
| M15 | číselné části R/U/E, nativní SVG graf | `test_three_graph_parts_are_numeric_not_css`, missing part OK; živý graf čeká |
| M16 | neměnné snapshoty, faktura i dokončené měření, sezonní profil | `test_comparison`, `test_snapshot_import_order...`, prognózy OK; živé srovnání čeká |
| M17 | v1 schema/raw, vlastní schema 1, CSV/JSON/ZIP | `test_extended.ImportTests`, backup a idempotence OK; migrace budoucích schémat odmítnutím |
| M18 | debounce, stav úloh, Repairs, safe close/restart | transakce/cancellation unit OK; celý HA unload/úloha/Repairs čekají |
| M19 | faktury, revize, vratka, párový převod kreditu | oprava přeplatku na nedoplatek se starou vratkou, vyšší vypořádání a matching unit OK |
| M20 | panel, CS/EN popisky, MND styl, generátor a šest views | DOM, navigace a brand testy OK; HA UI, mobily a uložený Overview čekají |

## Matice testovacích scénářů zadání

| ID | Provedený důkaz | Co zbývá |
| --- | --- | --- |
| T01 | řízený klient: login, chybná hesla, HTML, redirect, numeric/date Retry-After | skutečná relace, vypršení a interaktivní MFA |
| T02 | DOM: více účtů, odmítnutí staré odpovědi po přepnutí | více skutečných entry/míst v HA |
| T03 | skutečné syntetické OOXML ZIP, posunuté záhlaví, kopie názvu a 1900/1904 | zákaznické varianty exportu |
| T04 | nesouhlas názvu/hlavičky/Parametrů/výběru odmítnut | HA upload |
| T05 | vzorec, HTML a nebezpečná cesta odmítnuty; limity implementovány | širší adversariální/fuzz a paměťové ověření |
| T06 | opakovaný import, dva statusy/jeden bod | HA import stejných originálů |
| T07 | konflikt/reset/pokles, žádná záporná spotřeba | skutečná výměna měřidla |
| T08 | neúplné řádky a potvrzení pokrytí implementovány bez falešné úplnosti | celý backfill a cancellation v HA |
| T09 | úlohové zámky, restart running→paused, atomický kurzor | HA start/restart/unload/obnova |
| T10 | manuální i senzorová projekce a ruční roční profil | nastavení a nativní události v HA |
| T11 | syntetické příklady priority, rebaze a opravy MND | HA historický senzor |
| T12 | den bez vymyšleného času; přesné intradenní body samostatně | UX nejistoty v HA |
| T13 | neplatné jednotky nevymažou fakturu; registry přejmenování implementováno | skutečný registry update/remove |
| T14 | mezilehlý reset, nová kalibrace po resetu, mezera a nula | dlouhá skutečná historie zdroje |
| T15 | převody/mezery/jednotky a doložený faktor pro srovnání | fakturační koeficient skutečného účtu |
| T16 | alternativa neúčtuje, sazba/DPH jednou, chybějící mezistav odmítnut | skutečné produktové dokumenty |
| T17 | 23/25h denní profil, 23h paušál, přesné půlhaléře | širší časová matice v HA |
| T18 | předpis/úhrada odděleně, vyšší částka i oprava stejné částky s jiným datem | HA formuláře a služby |
| T19 | unmatched import není skutečná spárovaná úhrada | živé transakční identity a ruční potvrzení v HA |
| T20 | opravený doklad dědí vratku, změna směru dluhu, párový převod | uložený workflow v HA |
| T21 | null/0 a neúplná cena/saldo odlišeny | pohled HA entit |
| T22 | 100 + 1200 − 1000, neuhrazený předpis a vratka | živá faktura |
| T23 | číselné R/U/E a žádná data z CSS | živá odpověď grafu |
| T24 | chybějící část zůstává null, překryvy odděleně | skutečné hraniční periody portálu |
| T25 | starý snapshot zachován, shodné dokončené měření/faktura, nesoulad odmítnut | živé vyhodnocení pozdější skutečnosti |
| T26 | léto samo nedá zimní prognózu; bez cen není přesná finanční prognóza | roční historie skutečného místa |
| T27 | budoucí Store schema a chyba save nepublikují prázdný stav | skutečný HA Store, Recorder retention a disková chyba |
| T28 | dva souběžné commity a cancellation během save neztratí revizi | reálný pád procesu HA a přepočet během importu |
| T29 | starší v1, přesné Decimal, raw provenience, Actual a backup | kompletní volitelné pole po poli proti skutečnému exportu |
| T30 | připravené skutečné lifecycle testy bez fake HA modulu | oba Linux HA běhy dosud neprovedeny |
| T31 | registry placeholdery včetně přejmenovaných názvů; graf bez ApexCharts | skutečný HA registry a chybějící entity |
| T32 | kolize, cizí views, změna po náhledu, ztracená odpověď; jeden save | skutečné úložiště Overview; nativní HA nemá CAS |
| T33 | YAML/strategy pouze export, kolize odmítá přepis | místně upravená MND kompozice v HA |
| T34 | DOM, dark atribut a nuly; brand vizuálně v 32/64 px | screenshoty mobil/desktop/tooltipy v HA |
| T35 | všech šest views používá stejnou kartu a společnou šablonu | nová instalace i upgrade v HA |
| T36 | serverové admin kontroly a diagnostická whitelist implementovány | skutečné neoprávněné HTTP/WS pokusy v HA |
| T37 | skutečné dočasné Git tagy, reprodukovatelný ZIP, neshodný commit a immutable API | release tohoto projektu po CI |
| T38 | ignore pravidla, pouze syntetické fixtures, připravená kontrola indexu/runtime stromu | finální tagged instalační ZIP po CI |

## Způsob dokončení

Nejbližší ověřovací krok je spuštění připraveného CI v Linuxu nad konkrétním
commitem. Veřejné odeslání zdrojů musí být vědomé; není provedeno potichu.
Poté se opraví nalezené skutečné HA problémy, provede oprávněný test MND a
vizuální QA, teprve potom tag/build/draft. Úspěch syntetických testů tento
postup nenahrazuje. Provozní HA nebyl změněn.
