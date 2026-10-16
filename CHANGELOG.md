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
