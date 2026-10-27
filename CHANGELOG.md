# Changelog

## Nevydáno / Unreleased

### Čeština

- Opravena dostupnost instalace HACS: ověřená alpha.1 byla zveřejněna jako
  prerelease s původním ZIPem. Doplněn výběr beta verze místo commitu větve;
  anonymní stažení vrací HTTP 200 a odpovídá ověřenému SHA-256.
- README obsahuje stejná oficiální tlačítka My Home Assistant jako ČEZ:
  přidání integrace MND a otevření repozitáře v HACS, včetně pořadí instalace
  a konfigurace. Existující alpha tag ani instalátor se nemění.

### English

- Fixed HACS installer availability by publishing the verified alpha.1 as
  a prerelease with its original ZIP. Documented beta-version selection
  instead of a branch commit; anonymous download returns HTTP 200 and
  matches the verified SHA-256.
- Added the same official My Home Assistant buttons used by ČEZ: configure
  the MND integration and open its HACS repository, with installation and
  restart prerequisites. The existing alpha tag and installer are unchanged.

## 0.1.0-beta.4 — vlastní odhad podle spotřeby

### Čeština

- Vlastní výhled používá doložený stav plynoměru, místní sezónní historii,
  doložené ceny a zálohy MND. Průběžně reaguje na nová měření; dodavatelská
  prognóza a potvrzená faktura zůstávají samostatně označené.
- Výpočet přednostně používá přesnou kotvu a měřený roční profil. Pokud
  chybí, může použít orientační denní návaznost MND, doplnit sezónu z intervalů
  fyzických odečtů a převod z poslední faktury. Předpoklady jsou viditelné;
  chybějící hodiny a nedoložené platby se nevydávají za nulu.
- Editor umožňuje výslovně potvrdit vazbu historického a aktuálního zdroje
  téhož plynoměru. Změna zdroje, segmentu či faktoru potvrzení zneplatní.
- Nové entity vlastního odhadu nezmění význam původních dodavatelských entit.
  Graf odlišuje oba výhledy; spojnice ukazují pouze krajní body.

**Po aktualizaci:** restartujte Home Assistant a obnovte prohlížeč. Na kartě
Vyúčtování zkontrolujte kvalitu a případné chybějící podklady vlastního odhadu.
Podrobný postup je v dokumentu Vlastní odhad podle měření.

### English

- Added a separately identified consumption-based estimate using an evidenced
  meter baseline, observed seasonal history, prices and MND payments.
- Missing exact timestamps and seasonal data can use explicitly labelled
  approximations from MND readings and the latest verified invoice. Missing
  hours or financial evidence do not become zero. Optional confirmation
  binds distinct history and live sources to their registry IDs and factor.
- New entities do not change the meaning or history of supplier entities.

## 0.1.0-beta.3 — vlastní evidence je volitelná

### Čeština

- Přehled a dodavatelské účetnictví už nehlásí chybějící období nepoužívané
  vlastní evidence. Načtené období a zaplacené zálohy MND se dál zobrazují.
- Editor jasně vysvětluje volitelnou vlastní evidenci ručních plateb, cen
  a faktur. Zachovává prokliky na její období i sledované zálohy MND.
- Nedostupný průtok má samostatnou nápovědu s odkazem na zdroj měření.
  Neznámá hodnota se nadále nenahrazuje nulou.
- Generátor a přibalená šablona používají kompozici 5 se stejnou navigací.
  Účetní data, nastavení, importy a doklady se aktualizací nemění.

**Po aktualizaci:** restartujte Home Assistant a obnovte prohlížeč.
Pro používání přehledu MND není nutné vyplňovat vlastní evidenci ani
znovu opisovat zaplacené zálohy.

### English

- The overview and supplier accounting no longer report the unused optional
  ledger period as missing configuration. Imported MND periods and paid
  advances remain available.
- The editor explains optional own records and retains links to their period
  and supplier advances. Unavailable flow has separate measurement help.
- Generator and bundled template use composition 5 with unchanged navigation.
  No accounting data, settings, imports or documents are migrated or copied.

## 0.1.0-beta.2 — přehledný editor a odkazy na nastavení

### Čeština

- Editor nově rozděluje úlohy do skupin Měření a kotel, Platby a zálohy,
  Ceny a vyúčtování. Formuláře začínají sbalené, mají stručný popis a při
  rozbalení jiné úlohy zachovávají rozepsané hodnoty.
- Nápověda rozlišuje neznámé údaje místní knihy od již sledovaných záloh MND.
  Chybějící místní období neznamená ztrátu dodavatelských plateb; zálohy
  není nutné znovu ručně opisovat ani dvojitě započítávat.
- Přímé odkazy otevřou nastavení období, výběr zdroje průtoku nebo historii
  záloh MND pro správné odběrné místo. Otevření odkazu nic neukládá.
- Generátor a přibalená šablona mají shodné prokliky. Složení hlavního
  přehledu, podstránek, finančních grafů a navigace zůstává zachované.
- README viditelně uvádí licenci MIT, shodnou s ČEZ Dynamic Tariff i s textem
  již přibaleným do instalátoru. Podmínky licence se nemění.

**Po aktualizaci:** restartujte Home Assistant a obnovte prohlížeč. V Editoru
rozbalte pouze požadovanou úlohu. U neznámých údajů otevřete nápovědu
**Neznámé údaje a nastavení**; odkazy vás dovedou ke konkrétnímu poli.
Zápisy nadále potvrzujte tlačítkem příslušného formuláře.

### English

- Group the editor into collapsible tasks, retaining unsaved inputs when
  collapsing or opening another task. Preserve the open task after refresh.
- Explain local-ledger unknowns separately from monitored MND payments.
  Add read-only navigation to period settings, flow source and MND advances.
- Synchronize generated and bundled dashboard configuration links without
  changing the overview, detail views or accounting calculations.
- Make the existing MIT license, identical to the ČEZ reference, visible
  in README. Restart Home Assistant and refresh the browser after updating.

## 0.1.0-beta.1 — první beta, měření kotle a přehlednější dashboard

### Čeština

- První beta přebírá ověřené měření kotle a přehled z alpha.5. Oproti této
  alfě se funkční kód nemění; nová verze má vlastní tag a instalační balíček.
- V administraci každého odběrného místa lze zapnout měření elektrického
  příkonu a vybrat volitelný elektroměr kotle. Náhled ukáže dostupnost zdrojů;
  elektrická energie zůstává oddělená od plynu a vyúčtování MND.
- Hlavní přehled obsahuje tři bloky: právě teď, spotřebu a vyúčtování.
  Podrobnosti Spotřeba doplňují provozní historii a známou elektrickou
  spotřebu za dnešek a měsíc s časem a skutečným pokrytím.
- Živé hodnoty se obnovují bez ztráty fokusu a rozepsaných formulářů.
  Chybějící a zastaralá data se nevydávají za nulovou spotřebu.
- Generátor i přibalená šablona používají kompozici 4. Hlavní pohled,
  podstránky, navigace i finanční přehledy zůstávají zachované.
- Úvod v HACS je pouze český a používá stejné členění jako ČEZ: odznaky,
  logo, novinky, informace o integraci, požadavky a instalaci.

**Po aktualizaci:** restartujte Home Assistant a obnovte prohlížeč. Měření
kotle zapněte v konfiguraci zařízení MND v části **Elektrická spotřeba
plynového kotle** a vyberte zdroje. Již uložený dashboard se sám nepřepíše;
novou podobu převezměte z náhledu generátoru po záloze Overview.
Beta je určená k testování. Zásuvku ani termostat tato funkce neovládá.

### English

- First beta packages the verified alpha.5 runtime without functional changes.
- Includes optional boiler electricity monitoring, compact overview, native
  history and explicitly partial energy summaries; electricity stays separate
  from gas accounting. Generator and bundled dashboard share layout 4.
- HACS documentation and generated release notes are Czech-only as requested.
- Restart Home Assistant and refresh the browser after installing. Configure
  boiler sensors per supply point; preview and back up dashboard changes.
  Beta status does not imply stable status or completed mobile visual QA.

## 0.1.0-alpha.5 — měření kotle a jednoduchý přehled

### Čeština

- Volitelné čtecí měření elektrického příkonu a energie kotle v administraci
  každého místa; výběr zdrojů, převody W/kW a Wh/kWh, náhled a zachování
  vazby při přejmenování entity. Elektřina se nezapočítává do plynu ani MND.
- Zjednodušen hlavní přehled na aktuální odběr, dnešní/měsíční spotřebu
  a výhled vyúčtování s jedním sedmidenním grafem. Detail Spotřeba obsahuje
  provozní historii a měsíční sloupce, účetnictví zachovává finanční přehledy.
- Živé hodnoty se obnovují z HA bez ztráty fokusu či rozepsaných formulářů.
  Nula, zastaralý report a chybějící údaje mají odlišný význam. Souhrny
  rozlišují známou část, pokrytí a čas poslední přijaté hodiny; změněn
  současně generátor i přibalená kompozice dashboardu na verzi 4.

### English

- Added optional read-only boiler electricity monitoring per supply point,
  with source selection, W/kW and Wh/kWh conversion, a configuration preview,
  and entity-registry rename support. Electricity stays outside gas billing.
- Simplified the overview to current usage, daily/monthly gas consumption,
  and the billing outlook with a single seven-day chart. Consumption details
  retain operating history and monthly bars; accounting retains financial data.
- Live HA values update without losing focus or unsaved form content. Zero,
  stale reports, and missing data remain distinct. Aggregates show partial
  coverage and actual observation boundaries. Updated both the dashboard
  generator and bundled composition to layout version 4.

## 0.1.0-alpha.4 — účetní období, náklady a měsíční měření

### Čeština

- Hlavní přehled používá skutečné účetní období z MND, včetně přechodu přes Nový rok. Souhrn odběru, nákladů, skutečných úhrad, plánu záloh a očekávaného výsledku funguje bez ručního přepisu finanční knihy.
- Společný graf rozlišuje známé náklady, celkový výhled, zaplacené zálohy a předpisy podle skutečných dat. Měsíční sloupce m³ rozlišují úplné, neúplné a chybějící měření. Novější HA sloupce nepřepisují souhrnnou spotřebu MND.
- Originální vyúčtování má přednost ve vlastním období; energie a stálé platby se neúčtují znovu. Nejednoznačné hranice nebo opravy nezískají odhadnutou skutečnost.
- Ověření ceny z aktuálního originálního ceníku MND kontroluje pásmo, DPH, součty a doloženou individuální cenu. Budoucí regulované ceny a poměr měsíční platby podle dnů jsou výslovné předpoklady; neznámý formát nepředstírá nulu.
- Historii lze připojit na původní pulsní senzor se zadaným objemem pulsu. Duplicitní odvozený senzor se nepřičítá. Poslední tři dny se obnovují po 10 minutách; soukromá záloha uchovává i ověřené cenové podklady.
- Stejnou kompozici 3 používají frontend, Generate dashboard i přibalená šablona se šesti pohledy. Administrace zůstává v konfiguraci zařízení.

### English

- The main overview follows the actual MND billing period across calendar years. Consumption, costs, actual payments, planned advances and the expected result are available without manually copying the financial ledger.
- A shared chart separates known costs, total forecast, paid advances and prescriptions by their actual dates. Monthly m³ bars distinguish complete, partial and missing measurements. HA bars do not replace MND total consumption.
- Original invoices take precedence within their covered intervals, without charging the same energy or fixed fees twice. Ambiguous boundaries or corrections remain unresolved.
- Current original MND tariff parsing checks the consumption band, VAT, column totals and documented personal price. Future regulated prices and calendar-day fixed-charge proration are explicit assumptions; unsupported formats remain unknown.
- Historical pulse counters support an explicit volume-per-pulse factor without double counting derived volume sensors. The latest three days refresh every 10 minutes; private backups preserve verified pricing evidence.
- Frontend, Generate dashboard and the bundled six-view template share composition 3. Administration remains in the device configuration.

## 0.1.0-alpha.3 — oprava stahování dokumentů MND

### Čeština

- Živé ověření alpha.2 potvrdilo načtení předpisů, vyúčtování a plateb i zachování odečtů; odhalilo ale HTTP 404 při stahování exportu.
- Opravena společná cesta stahování dokumentů na `/api/Documents/GetByGuid` podle veřejného klienta MND. Stejnou kontrolu používají exporty záloh, vyúčtování, odečtů, PDF faktur a smluvní dokumenty.
- Doplněna regrese přesné cesty a stahování bez přihlašovacího tokenu; kontrola názvu, binárního formátu a soukromého úložiště zůstává zachována.
- Nové požadavky na graf nákladů a záloh, loňské a topné/netopné srovnání jsou zaznamenané v zadání. Tato opravná verze je zatím neimplementuje.

### English

- Live alpha.2 validation confirmed advance, invoice and payment retrieval and preserved meter readings, but exposed HTTP 404 while downloading an export.
- Corrected the shared document download route to `/api/Documents/GetByGuid`, matching the public MND client. Advance, invoice and reading exports, invoice PDFs and contract documents use the same validated path.
- Added regression coverage for the exact route and token-free document download while preserving filename, binary format and private storage validation.
- Additional cost/advance charts, year-over-year and heating/non-heating comparisons have been recorded in the specification and are not implemented by this corrective release.

## 0.1.0-alpha.2 — přehled a konfigurace odběrného místa

### Čeština

- Jednoduchý čtecí přehled v horní liště Overview, bez duplicitního MND v bočním menu.
- Veškerá správa z konkrétního zařízení MND; odstraněn velký úvodní banner a formuláře z běžného dashboardu.
- Opraven společný generátor i přibalená šablona. Aktualizace starých MND karet zachová cizí karty, místní názvy a pořadí; před zápisem se stáhne záloha.
- Doplněny historie záloh, skutečně zaúčtované úhrady dokladů, přehled a detail vyúčtování, samostatné exporty a PDF faktury podle veřejného klienta MND.
- Platby používají doložené payPeriod=365; předpis není úhrada. Převzetí do knihy má potvrzené přiřazení k období, stabilní identity a audit oprav.
- Průtok ze samostatného senzoru s přesným převodem na m³/h, čerstvostí a zachováním vazby při přejmenování. Spotřeba navazuje na MND kotvu; srovnání vyžaduje shodné hranice a bázi.
- Přerušený průvodce lze po ověření účtu převzít; číselná chyba již nezanechá nekončící načítání a má opakování.
- Jde nadále o prerelease. Nové finanční endpointy/exporty a mobilní vzhled vyžadují živé ověření; plné automatické smluvní ceny nejsou dokončené. Podrobnosti v docs/ALPHA_2.md.

### English

- Simplified read-only Overview tab, preserving HA navigation and removing the duplicate MND sidebar entry.
- All administration starts from the selected MND device; removed the large hero and administrative forms from normal dashboard cards.
- Updated both generator and bundled template. Existing MND cards can be upgraded while preserving unrelated cards, local titles and view order, with a downloaded backup before saving.
- Added advance history, actual document allocations, invoice lists/details, separate exports and invoice PDF downloads based on the public MND client.
- Payment requests use documented payPeriod=365. Prescriptions remain separate from payments; ledger acceptance requires explicit period allocation and keeps auditable revisions.
- Added independently selected flow sensors, exact m³/h conversion, freshness checks and registry rename support. Meter/forecast comparisons require matching boundaries and energy basis.
- Authenticated users can resume an abandoned setup flow; numeric request failures provide recovery instead of endless loading.
- Still a prerelease: new financial endpoints/exports and mobile appearance require live validation. Complete automatic contract pricing remains unfinished. See docs/ALPHA_2.md.

## 0.1.0-alpha.1 — vývojová verze

### Čeština

- První Python implementace importů XLSX/C# v1, auditní evidence, měření,
  záloh, plateb a faktur; účetní engine rozlišuje neznámé údaje a nuly.
- Soukromá záloha s originály, historie prognóz, nativní HA konfigurace,
  panel a společný generátor/šablona hlavního view a pěti detailů.
- Cloudový klient podle veřejného JS MND; živý test účtu, úplné automatické
  smluvní ceny a živá mapa platebního stavu zatím nejsou dokončeny.
- Quality, HACS a Hassfest ověřeny, 100 Python a 21 Node testů úspěšně;
  16 skutečných HA testů na 2026.3.1 i 2026.10.1 v Linuxu.
- Vzhled odvozený od Moje MND, vlastní vektorová značka a světlé/tmavé téma.
- Účtování přesných časových hranic včetně DST a zachování vypořádání faktury
  při její pozdější opravě; historická prognóza se porovnává jen s doloženou skutečností.

### English

- Initial Python XLSX/C# v1 imports, audit records, metering, advances,
  payments and invoices; unknown inputs remain distinct from confirmed zeros.
- Private backups with originals, forecast snapshots, native HA configuration,
  panel and a shared dashboard generator/template with five detail subviews.
- Cloud client follows the public MND JavaScript contract. Live account
  validation, complete automatic contract pricing and live payment-status
  mapping are pending.
- Quality, HACS and Hassfest passed: 100 Python and 21 Node tests, plus
  16 real HA tests on each of 2026.3.1 and 2026.10.1 under Linux.
- Moje MND inspired interface, original vector mark and light/dark themes.
- Exact timestamp accounting including DST and invoice settlement continuity
  across corrections; forecast comparisons require documented actual values.
