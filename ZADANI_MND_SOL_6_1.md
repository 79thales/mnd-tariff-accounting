# MND Tariff & Accounting for Home Assistant — zadání pro Codex Sol 6.1

Datum přípravy: 15. 10. 2026. Stav: **zadání k budoucí implementaci; žádná integrace nebyla v rámci přípravy naprogramována ani nasazena**.

## 1. Cíl a závazné hranice

Vytvoř samostatnou integraci pro HACS s názvem **MND Tariff & Accounting for Home Assistant**. Zákazník plynu uvidí skutečnou spotřebu, stav měřidla, aktuální předpis záloh, skutečné úhrady, průběžné náklady, odhad výsledku zúčtovacího období a potvrzené vyúčtování včetně přeplatku/nedoplatku. Uživatelské uspořádání, účetní evidence, odolnost archivů, generátor dashboardu a pravidla Git navazují na ČEZ Dynamic Tariff & Accounting.

- Jediný kořen nového vývoje: `H:\01.programovani\MND Tariff & Accounting for Home Assistant\`.
- Existující Codex projekt: **MND Tariff & Accounting for Home Assistant**. Jeho adresář byl při přípravě ověřen; nezakládej jiný projekt v C: ani pod WebDownloaderem.
- Funkční reference MND: `H:\01.programovani\webdownloader\` — pouze čtení.
- Reference ČEZ: `H:\01.programovani\cez-dynamic-tariff\` — pouze čtení, včetně dosud necommitnutých změn. Nesmíš je zahodit, commitnout ani přenést cizí `.git`.
- Navržená stabilní doména: `mnd_tariff_accounting`; před prvním zveřejněním ověř kolizi. Vydanou doménu a unique ID bez migrace neměň.
- „Všechno z C# aplikace“ zde znamená kompletní **modul MND** podle matice níže. Funkce ORLEN a EDC se do plynové integrace nekopírují.
- Runtime integrace je Python v Home Assistantu, frontend podle potřeby JavaScript. Přenes chování a datové kontrakty; WPF, WebView2, .NET a Windows Credential Manager nejsou závislosti HA.
- Nepřidávej ovládání spotřebičů, změny tarifu/záloh u dodavatele, odesílání samoodečtů do MND ani provádění plateb. Požadované úpravy jsou místní účetní evidence v HA.
- Součástí dodávky je generátor **záložky v horní liště existujícího Overview `/lovelace`**, jeho detailních podstránek a přibalená šablona. Není tím míněn pouze nový dashboard v postranním menu.
- Komentáře, popisy akcí a vývojová dokumentace budou česky; UI a changelog česky a anglicky. V komunikaci o sobě piš v ženském rodě.

Součásti zadání: [pravidla Git](GIT_POLITIKY_CEZ.md), [evidence podkladů](PODKLADY_A_OVERENI.md), [logo](NAVRH_LOGA.md) a [spouštěcí prompt](PROMPT_PRO_SOL_6_1.md). Požadavky níže jsou cílové chování, nikoli tvrzení o již fungující HA integraci.

## 2. Podklady, které musíš před programováním přečíst

### WebDownloader

V kořeni reference čti `docs/MND.md`, `docs/MND_DATA_CONTRACT.md`, `docs/MND_VALIDATION.md`, `docs/mnd-data-v1.schema.json` a `ZADANI_MND_SOL_6_1.md`. Poté zkontroluj skutečné zdroje:

| Zdroj relativně k WebDownloaderu | Co přebrat a ověřit |
| --- | --- |
| `src/Mnd.Core/Models.cs` | Identity, odečty, doklady, kvalita, tarify, platby, JSON kontrakt v1 |
| `src/Mnd.Core/MndReadingWorkbookParser.cs` | XLSX, identity, čísla, data, odmítání nebezpečných a chybných vstupů |
| `src/Mnd.Core/MndHistoryEngine.cs` | Sloučení zdrojových řádků, logické body, konflikty a výměny měřidla |
| `src/Mnd.Core/MndHistoryPlanner.cs` | Postupné stahování minulosti a důkazy pokrytí |
| `src/Mnd.Core/MndAccountingEngine.cs` | Jednotky, ceny, DPH, přiřazení plateb a chybějící vstupy |
| `src/Mnd.Core/MndHomeAssistantClient.cs` | Validace zdrojového senzoru a kalibrace; REST klient nahradit nativním HA |
| `src/OrlenPriceDownloader/Services/Mnd/MndPortalService.cs` | Přihlášení, výběr místa, exporty, dokumenty, grafy a odhlášení |
| `src/OrlenPriceDownloader/Services/Mnd/Scripts/Snapshot.js` | Skutečně nalezené struktury portálu a číselné části grafu |
| `src/OrlenPriceDownloader/Services/Mnd/MndPortalModels.cs`, `MndSettingsStore.cs` | Perzistence, nastavení podle místa, snímky a důkazní data |
| `src/OrlenPriceDownloader/Views/MndView.xaml`, `MndView.xaml.cs`, `MndConsumptionChart.cs` | Úplný seznam uživatelských operací a prezentace |
| `tests/Mnd.Core.Tests/MndTests.cs`, `tools/Mnd.DesktopCheck`, `tools/Mnd.ImportCheck` | Přenos smyslu testů, odlišení syntetického a živého ověření |

### ČEZ

Čti zejména `docs/accounting.md`, `docs/accounting-reliability-design.md`, `docs/dashboard-generator.md`, `scripts/README.md`, `.github/workflows/`, `hacs.json`, `LICENSE` a relevantní moduly v `custom_components/cez_dynamic_tariff/`: účetní archiv, obnovu, služby, zálohy, vyúčtování, config flow, diagnostiku, `dashboard.py`, `dashboard_api.py`, `frontend.py`, `frontend/dashboard-generator.js`, editor záloh a `dashboard_template.json`.

Převzaté části musí být věcně adaptované na plyn. MND nemá z tohoto zadání HDO, VT/NT, dynamická pásma elektřiny ani sdílení EDC. Tyto závislosti do nové integrace nezaváděj. Zachovej licenci převzatého kódu.

## 3. Matice úplného převzetí MND

Každý řádek musí mít v implementačním reportu konkrétní modul, test a výsledek. Dočasná náhrada ani neověřený cloudový přístup se nevydávají za dokončenou paritu.

| ID | Funkce reference / požadavek | Cílová podoba v HA |
| --- | --- | --- |
| M01 | Přihlášení, opětovné přihlášení, odhlášení, zapomenutí přístupu | Config flow, reauth a lokální správa relace; odhlášení zachová účetní archiv |
| M02 | Seznam míst, volba, technické údaje, smlouva, distributor, plynoměr | Více účtů a míst, stabilní identity, zařízení pro každé místo |
| M03 | Aktuální a doporučená záloha, hodnocení a platební stav MND | Oddělené entity s původem a časem; banner není účetní kniha |
| M04 | Současný, následný a alternativní produkt/cena | Evidovat všechny; účtovat jen smluvně platný tarif |
| M05 | Smlouvy, dokumenty a jejich stažení | Soukromý archiv originálů, hash, bezpečné stažení v přihlášeném HA |
| M06 | Zákaznický profil a platební přehled | Dostupné odděleně na vyžádání; profil ani dokladový text nepatří do běžných atributů/diagnostiky |
| M07 | Export odečtů pro interval přes Export → Od/Do → Odeslat | Stejný datový výsledek přes ověřený transport, ukládání originálu a metadat |
| M08 | Pokus o veškerou dostupnou historii | Obnovitelná úloha po úsecích s pokrytím a průběhem |
| M09 | Ruční import XLSX, rozpoznání EIC v názvu | Import přímo z HA, kontrola identity všech dostupných zdrojů |
| M10 | Deduplikace, statusy, konflikty a reset/výměna plynoměru | Auditní model a měřicí úseky bez dvojí spotřeby |
| M11 | Ruční skutečný stav | Formulář a akce v HA, historie oprav, čas, měřidlo, m³, poznámka |
| M12 | Existující HA senzor a kalibrace | Nativní odběr stavů a historie bez tokenu k vlastnímu HA |
| M13 | Přednost odečtu MND | Závazná pravidla v kapitole 5, zpětné přepočty se stopou původu |
| M14 | Náklady, ceny, DPH, stálé platby, zálohy a saldo | Odolné účetnictví dle kapitol 6–7 |
| M15 | Historické sloupce portálu a jejich tři části | Číselná data dle původních období, samostatně skutečnost a odhady |
| M16 | Časové snapshoty prognóz | Archiv prognóz a porovnání s pozdějším měřením pro shodný interval |
| M17 | JSON/CSV export a datový kontrakt v1 | Import v1, vlastní verzované úložiště a kompatibilní/exportně popsaný výstup |
| M18 | Stav úloh, zrušení, omezení, zachování výsledků | Diagnostika, Repairs dle příčiny, bezpečný unload/restart a pokračování |
| M19 | Nově: skutečné vyúčtování, přeplatky/nedoplatky | Evidence faktur, úhrad, vratek, převodu kreditu a oprav bez dvojího zaúčtování |
| M20 | Nově: plnohodnotné HA UI a generátor horní lišty | Zařízení, entity, konfigurace, služby, grafy a atomické přidání pohledů |

## 4. Portál, přenos a úplná historie

### 4.1 První ověřovací etapa: proveditelnost autentizace

Výchozí adresy jsou `https://www.mnd.cz/` a `https://moje.mnd.cz/login`. C# používá interaktivní WebView2; to nedokazuje existenci veřejného API ani použitelné bezobslužné relace z Linuxu. Nejprve zdokumentuj skutečný přihlašovací tok, potřebné cookies/CSRF, obnovu relace, odhlášení, MFA/CAPTCHA a limity. Endpointy, autorizační schéma ani tvar odpovědi neodhaduj.

Preferuj ověřený asynchronní HTTP klient nezávislý na HA. Respektuj běžné přihlášení uživatele; neobcházej interaktivní výzvy. Pokud portál přímý přístup neumožní, popiš důkaz a konkrétní alternativu: uživatelskou autorizaci, oddělený doprovodný transport nebo import exportů. Browser runtime se nesmí potichu instalovat do HA Core. Importní režim je povinný a plnohodnotný, ale samotný import nesplňuje M01–M08 jako automatický cloudový provoz. U takového omezení musí zůstat rozsah výslovně nehotový.

Přihlašovací údaje uživatel zadává v chráněném formuláři. E-mail, heslo, cookies, tokeny a celé přihlášené stránky nesmějí do kódu, logů, diagnostiky, snapshotů, testovacích fixtures ani Gitu. Běžné úložiště HA neoznačuj za šifrovaný trezor. Předchozí jednorázový živý test C# je dokončená minulá autorizace, nikoli neomezené povolení dalších přihlášení. Nepřebírej tajemství z původního DOCX do nového projektu.

Síťové volání má ověřovat TLS, stav, typ/velikost odpovědi a skutečnou identitu místa. HTML přihlašovací stránka s HTTP 200 není XLSX ani úspěšná relace. Přesměrování a přenos autorizačních hlaviček dovol pouze podle doloženého přihlašovacího toku. Timeout a chyba jednoho místa nesmějí zamíchat data jiného účtu.

### 4.2 Export a import odečtů

Přenes UX intervalu Od/Do. U browser transportu jsou exportní hranice **oba dny včetně**, časy 00:00–23:59 a formát `DD/MM/RRRR`, nezávisle na kultuře serveru. Čekání na download se registruje před odesláním formuláře. Portál může nechat dialog otevřený; opakovaný export nesmí pracovat se starým dialogem. U HTTP transportu ověř odpovídající význam parametrů, ne pouze jejich název.

Soubor `Odečty_<EIC>.xlsx` i kopie s `(1)` obsahují vodítko k místu. Ověř shodu názvu, nadpisu listu, případného listu Parametry a vybraného místa. Chybějící identifikátor v názvu lze nahradit ověřenou vnitřní identitou s upozorněním; nesoulad musí odmítnout import. EIC/EAN a číslo měřidla jsou řetězce. Žádné reálné EIC nepředvyplňuj.

Čti sloupce Datum, Stav (m³), Číslo plynoměru, Způsob zjištění a Stav. Zachovej každý odlišný dokladový řádek a jeho původ. Podporuj posunuté záhlaví, česká desetinná čísla, Excelové datumové systémy 1900/1904 a prázdné řádky. Odmítni HTML, vzorce v očekávaných datových buňkách, externí XML entity, neplatné hodnoty, nebezpečné cesty a překročení limitu. Výchozí limit zdrojového i rozbaleného XLSX je 64 MiB podle reference; limity zpracování musí chránit paměť HA. Neprováděj obsah dokumentů.

Každý originál má SHA-256, původní název, interní bezpečnou cestu, místo, čas získání, požadovaný interval a výsledek validace. Identický opakovaný import nepřidá spotřebu. Jiné soubory stejného názvu se nepřepisují. Neplatný řádek se neztratí bez diagnostiky; import uvede počty přijatých, shodných a odmítnutých řádků a ovlivní kvalitu pokrytí.

### 4.3 Veškerá dostupná minulost

Stahuj zpětně po navazujících úsecích. Výchozí běh dle C#: 10 úseků po nejvýše 366 dnech, celkový limit 15 minut; rozsah lze rozšířit, nejvýše 100 úseků na jeden běh. Tyto limity jsou ochrana práce, nikoli tvrzení, že starší historie neexistuje. Nabídni pokračování od kurzoru a opětovnou kontrolu dříve načteného období kvůli opravám MND.

Rozlišuj požadované pokrytí, skutečně získané řádky a důkaz nejstaršího dostupného období. První řádek ani několik prázdných exportů samy nepotvrzují úplnost. Stav `confirmed` vyžaduje doloženou hranici a úspěšně pokryté úseky; jinak `unverified` nebo `partial`. Chyba, zrušení, limit či neplatný řádek nesmějí vést k zelenému hlášení „vše staženo“.

Úloha ukládá průběh a hotové segmenty atomicky. Druhé spuštění stejného účtu se připojí k existující úloze nebo srozumitelně odmítne duplicitu. Zrušení a unload bezpečně zastaví síťovou práci. Po restartu je nedokončený běh pozastavený a lze jej obnovit, bez ztráty hotových originálů a bez souběžné relace.

## 5. Měřicí model a závazná přednost MND

### 5.1 Zdroje

Uživatel pro každé místo volí **existující senzor spotřeby plynu**, nebo **ruční odečty v HA**. Volbu lze později změnit bez smazání historie. MND tvoří samostatnou autoritativní vrstvu v obou režimech. Obě lokální možnosti musí fungovat samostatně.

Senzor musí poskytovat kumulativní objem v m³ nebo přesně převoditelnou objemovou jednotku; okamžitý průtok není kumulativní stav. V první verzi vyžaduj m³, pokud jiný objemový převod není výslovně implementován a otestován. Energetický senzor kWh nepovažuj za stav fyzického plynoměru bez doloženého přepočtu a návaznosti. Senzor se čte nativně z HA, sleduje se jeho registry ID i po přejmenování entity a čte se dostupná historie/long-term statistics vhodným HA API.

Kalibrace váže místo, měřidlo, zdrojovou entitu, okamžik, fyzický stav a souběžný stav senzoru. Fyzický stav v dalším okamžiku = fyzický stav při kalibraci + validovaný přírůstek senzoru od kalibrace. Samotné odečtení dvou čísel nesmí přehlédnout reset, výměnu, mezeru nebo změnu jednotek. První kumulativní hodnota po připojení není nová spotřeba.

Ruční odečet obsahuje místo, měřidlo, hodnotu m³, skutečný čas zjištění, čas uložení a poznámku. Oprava vytvoří revizi; původní hodnota zůstává v auditu. Neplatný nebo budoucí čas se odmítá. Zadání místního odečtu nic neposílá dodavateli. Uživatel v manuálním režimu uvidí „stav k datu“, nikoli živé měření v době otevření dashboardu.

### 5.2 Pravidla priority

1. **Odečet MND má vždy přednost před místním senzorem nebo ručním odečtem pro shodné místo, měřidlo a odpovídající okamžik/hranici.** Nesmí jej přepsat lokální uživatel ani automatická kalibrace.
2. Přednost neznamená zamlčet novější měření. Starší MND odečet je základ, na nějž mohou navázat doložené novější přírůstky HA nebo novější ruční stav. Původ kombinovaného výsledku musí být vidět.
3. Záznam MND zjištěný odhadem zůstává označený jako odhad dodavatele. Status „Vyfakturovaný“ neznamená automaticky fyzické měření; method, status, source a quality jsou nezávislé údaje.
4. Později doručený nebo opravený záznam MND přepočte dotčené otevřené intervaly a jejich návaznost. Neprovede druhé přičtení téže spotřeby. Zachovej původní místní měření, korekci a důvod změny.
5. K rebazi senzoru musí být známý kompatibilní stav senzoru v čase kotvy. Chybí-li, nelze prostě přesunout dnešní offset do minulosti. Dotčený přírůstek je neúplný nebo výslovně odhadnutý.
6. XLSX má typicky pouze datum. Nevymýšlej přesný čas o půlnoci nebo na konci dne. MND stanoví autoritativní denní bod, ale srovnání s intradenním měřením a první navazující úsek nesou časovou nejistotu.
7. Dva statusy stejného dne, měřidla a hodnoty jsou dva doklady, ale jeden měřicí bod. Dvě různé hodnoty stejné hranice jsou konflikt. Rozhodující opravu přijmi jen s doloženou revizí/identitou od MND; nerozhoduj libovolně pořadím řádků nebo maximální hodnotou.
8. Při výměně plynoměru začíná nový segment. Nesmí vzniknout záporná spotřeba ani skok započtený jako odběr. Celé období lze sečíst jen z návazně doložených segmentů; chybějící předávací stav znamená mezeru.
9. Potvrzená faktura je samostatně autoritativní pro finanční výsledek svého uzavřeného období. Nový místní odečet ji nepřepisuje; případný rozpor se ukáže ve srovnání. Oprava faktury musí mít vlastní doklad a návaznost.
10. Zrušení/diskvalifikace lokálního záznamu neodstraňuje záznam MND. Chyba portálu zachová poslední validní data s jejich skutečným stářím.

### 5.3 Povinné syntetické příklady

- MND a ruční odečet mají stejnou doloženou hranici a stejné měřidlo: MND 1 000 m³, ruční 1 004 m³. Účetní kotva je 1 000; rozdíl a původ ručního zápisu zůstávají vidět.
- MND 1 000 m³ v čase T; senzor v T = 200 a nyní = 230. Při úplné návaznosti je aktuální kalibrovaný stav 1 030 m³. Nejde o nový potvrzený odečet MND.
- Oprava MND kotvy na 1 002 m³ při shodném T a doložené senzorové historii vede na 1 032 m³; nevytvoří další spotřebu 1 002 m³. Starší přepočet zůstane dohledatelný.
- Datum MND bez času a dvě lokální hodnoty téhož dne: nelze tvrdit přesný rozdíl spotřeby v konkrétní hodině.
- Pokles senzoru 230 → 0 bez doloženého resetu zneplatní návaznost; výsledek není záporný odběr. Po opravě/nové kalibraci pokračuj bez dvojího započtení.

## 6. Spotřeba, tarif a ocenění

### 6.1 Čas a jednotky

Účetní engine používá intervaly **[od, do)**; uživatelské „do včetně dne“ se převádí na následující místní půlnoc. Odlišuj konečné datum smlouvy, datum odečtu, fakturační interval a exportní filtr MND. Metadata grafu uchovej přesně podle portálu; mohou se překrývat a sama neurčují účetní hranice.

Časové pásmo vychází z `hass.config.time_zone`; lokální datum ukládej jako datum, skutečný okamžik v UTC s informací o původu. Počítej i dny s 23/25 hodinami, přestupný rok a fakturační období odlišné od kalendářního roku. Neobnovitelné nebo zamrzlé hodnoty nejsou nulová spotřeba. Nulový přírůstek může být správný, pokud zdroj doloženě hlásí stav; pouhé stáří `last_changed` nestačí k označení poruchy.

Objem = rozdíl platných hraničních stavů stejného segmentu. Energie MWh = objem m³ × doložený koeficient kWh/m³ ÷ 1 000. Koeficient má platnost a zdroj, ideálně z konkrétní faktury; pokud je součinem objemového koeficientu a spalného tepla, eviduj tento význam. Nemíchej provozní a přepočtené m³. Bez koeficientu lze zobrazit m³, ale nikoli přesnou energii ani úplné náklady. Orientační koeficient znamená výslovně odhad.

### 6.2 Cenové úseky

Eviduj smluvní současné a následné ceny, samostatně nabídky alternativního produktu. Ceny jsou časově verzované: obchodní Kč/MWh, distribuční a další variabilní složky Kč/MWh, stálé Kč/měsíc, zahrnutí DPH a sazba DPH platná v intervalu. Zdrojový text a jednotky zachovej; Kč/kWh převedené na Kč/MWh násob 1 000. Nezapočítej individuální cenu a grafickou cenu jako dvě složky. Slevu neuplatni podruhé na již zlevněnou částku.

Výpočet musí doložit všechny složky a nepoužívat automaticky současný ceník v minulosti. Samotná cena komodity není plná cena dodávky. Neznámá složka zůstává `null`; nula je výslovně doložená nulová sazba. Pro překryv nebo mezeru tarifů se nedělá libovolný výběr.

Při změně tarifu/DPH/koeficientu rozděl spotřebu podle skutečných dat na hranicích. Není-li rozdělení doloženo, nabídni transparentní odhad se zvolenou metodou a označením, nebo nech cenu neúplnou. Rovnoměrné rozdělení plynu podle dnů není reálný zimní profil a nesmí být výchozím „přesným“ výpočtem.

Plný kalendářní měsíc má plnou stálou platbu. Poměr v neúplném měsíci se počítá podle smluvně potvrzeného pravidla; poměr podle skutečných dnů je dostupná volba, nikoli automatická domněnka. Fixní část se započítává jednou, i při kombinaci faktury, historického kontrolního bodu a přírůstků.

Finanční výpočty používají `Decimal` a přesně popsané zaokrouhlení. Kompatibilita s C#: finální součet na dvě desetinná místa, poloviny od nuly. Pokud faktura zaokrouhluje jednotlivé položky jinak, eviduj pravidlo a rozdíl, neupravuj spotřebu kvůli shodě haléřů. Pro interní archiv a export používej reprezentaci bez ztráty desetinné přesnosti; v1 importer musí čísla načítat přímo jako decimal.

## 7. Zálohy, skutečné platby a vyúčtování

### 7.1 Evidence

Odděl předpis zálohy, skutečnou úhradu, doporučenou zálohu MND a vlastní doporučení aplikace. U předpisu je částka, splatnost a období platnosti; změna dnešní zálohy nepřepíše starší měsíce. Úhrada má vlastní ID, částku, datum, zdroj, stav ověření a přiřazení místu/období. Nepřiřazená částka zůstává nerozúčtovaná. Datum přijetí peněz samo nerozhoduje o zúčtovacím období.

V nastavení nabídni jeden přehled všech měsíců období, společnou částku jako pomůcku, jednotlivé předpisy, uhrazeno a potvrzení. Povolit částečné, opožděné, mimořádné i vyšší úhrady než předpis — legitimní přeplacení není chyba. Toto je věcná adaptace ČEZ, jehož omezení úhrady výší plánu se sem nepřenáší. Změna společného předpisu nikdy nevytváří úhradu. Uložení formuláře je atomické.

Ruční potvrzení je doložení uživatelem, nikoli bankovní potvrzení. Případnou funkci automatické evidence podle plánu z ČEZ přenes jako výchozí vypnutou možnost, se stavem `assumed_paid`. Předpokládané platby nepatří do potvrzeného součtu. Zapnutí zpětně nepotvrdí minulé měsíce; restart, opakovaný běh a pozdější import MND nevytvoří duplicitu. Ruční částečná úhrada se nepřepíše plnou plánovanou částkou.

Automaticky načtené platby MND páruj podle stabilních identifikátorů. Shodná částka a datum bez ID nejsou vždy stejná platba; neurčité párování nabídni k potvrzení. Při nahrazení předpokladu/ruční evidence potvrzeným dokladem se částka započte pouze jednou. Banner „vše uhrazeno“ nikdy nenahradí úplný seznam transakcí.

### 7.2 Faktury a účetní kniha

Faktura nese číslo/identitu, místo, měřidla, období, datum vystavení, typ/revizi, doložené m³ a energii, ceny/koeficienty, celkovou cenu, zálohy přijaté do vyúčtování, potvrzený přeplatek/nedoplatek, splatnost a případnou vratku/převod kreditu. Uchovej PDF a hash. Parsování PDF je návrh hodnot; nejednoznačné položky se musí zobrazit uživateli a potvrdit. Čitelné strukturované údaje MND mají doložený původ. Ruční opsání faktury je plně podporovaná cesta s označením původu.

C# zatím poskytuje dokumenty a dokladový platební text, nikoli univerzální automatický parser a kompletní párování faktur. Tuto požadovanou funkci je nutné nově implementovat a otestovat; nevydávej ji za hotovou převzatou schopnost.

Uchovávej odděleně:

- **Průběžný výpočet ke dni měření:** známé náklady, úplnost a odhadovost; může vycházet z místního měření po kotvě MND.
- **Předpokládaný výsledek celého období:** očekávané náklady a očekávané platby do jeho konce; vždy prognóza.
- **Potvrzené vyúčtování MND:** neměnný dokladový výsledek uzavřeného období, případně nahrazený doloženým opravným dokladem.
- **Zbývá uhradit / vrátit:** aktuální stav vypořádání faktury, který se po platbě/vratce mění, zatímco původní výsledek faktury zůstává.

Pro otevřené období při úplných podkladech platí saldo ve prospěch zákazníka = počáteční kredit + přiřazené skutečné platby + doložené kreditní korekce − přiřazené náklady − vyplacené vratky − doložené debetní korekce. Každá událost má jednu účetní roli; přenos kreditu mezi obdobími je propojený výdej/příjem, nikoli druhý nový vklad. Náklad faktury nahrazuje příslušný předběžný náklad, nepřičítá se k němu. Souhrn přijatých záloh na faktuře se nesčítá znovu s již zaúčtovanými platbami.

Kladné saldo = přebytek, záporné = deficit. Účetní senzor může mít podepsanou hodnotu; prezentace zvlášť uvede nezáporný přeplatek nebo nedoplatek a typ výsledku. Chybějící počáteční kredit není nula. Potvrzený výsledek faktury lze zobrazit i bez kompletní lokální platební historie, ale shoda s místní knihou pak není ověřená.

Pro prognózu používej zvlášť doložené dosavadní úhrady a předpokládané zbývající platby. Neodečítej dnes celý roční plán od dnešního nákladu a nenazývej to přeplatkem z vyúčtování. Doporučení nové zálohy vychází z odhadu zbývajících nákladů, kreditu a počtu zbývajících termínů; bez úplných podkladů zůstává neúplné. Do MND se automaticky neodesílá.

Syntetický účetní test: počáteční kredit 100 Kč + skutečné platby 1 200 Kč − náklady 1 000 Kč = přebytek 300 Kč. Další nezaplacený předpis 500 Kč aktuální saldo nezmění. Po doložené vratce 300 Kč je zbývající kredit 0 Kč, původní vyúčtování nadále uvádí přeplatek 300 Kč.

## 8. Grafy, historie a srovnání s aktuálním měřením

Reprodukuj význam grafu MND: **uskutečněná spotřeba podle odečtů**, **uskutečněná spotřeba odhadem** a **budoucí spotřeba odhadem**. Celkový sloupec v MWh může obsahovat všechny tři části; není automaticky potvrzenou spotřebou tohoto roku.

Čísla přebírej jen z doložených dat, číselných popisků nebo tooltipu správného období. Osa 0/10/20, procento CSS nebo výška sloupce nesmějí být zdrojem spotřeby. Při UI transportu ověř zánik předchozího tooltipu a identitu dalšího sloupce; jinak hrozí přiřazení hodnot jinému roku. Chybějící díl je `null`, ne nula. Odchylku součtu kvůli zaokrouhlení zobraz s tolerancí danou přesností zdroje, ne automatickým přepsáním jedné části.

Každé úspěšné získání dat ukládá časový snapshot. Nová prognóza nesmaže starou. Identické datové snapshoty lze úsporně sdílet, ale uchovej časy pozorování a změny. Historický graf nesmí sčítat překrývající se období portálu.

Pro srovnání vyber konkrétní uloženou prognózu a stejné místo, měřicí segmenty, období, jednotku a převodní koeficient. Teprve po dostupnosti reality daného intervalu spočítej absolutní rozdíl a procentní odchylku; při nulové referenci procento není definované. Roční prognózu bez časového profilu nelze porovnávat s neukončeným rokem jako přesnost prognózy. U aktuálního období lze ukázat vedle sebe průběžnou skutečnost a celoroční výhled s jasnými názvy.

Vlastní prognóza HA je další samostatná série. Pro plyn použij doloženou sezónnost z dostatečně pokrytých historických období; nedělej zimní prognózu prostým násobením letního dne. Chybí-li reprezentativní zima, koeficient nebo budoucí ceny, označ přesně omezení. Metodu, datum sestavení a vstupy uchovej. Budoucí cenu bez smluvního podkladu nevydávej za jistotu.

Denní/měsíční grafy a tooltipy musí spojovat série podle skutečného času, zachovávat platnou nulu a vynechat neznámý bod. V grafu odliš úplné a neúplné období, měření a odhad také popiskem či vzorem, nejen barvou.

## 9. Architektura a trvalá data

### 9.1 Oddělení odpovědností

Navrhni testovatelné vrstvy: transport MND; validace/importy; normalizovaná evidence; priorita odečtů a měřicí segmenty; cenové intervaly; účetní kniha a vyúčtování; prognózy; perzistence; HA koordinátory/entity; konfigurace/akce; dashboard. Výpočty musí fungovat na syntetických datech bez přihlášení a bez HA. Žádná síťová operace nepatří do property entity.

Jedna config entry spravuje jeden účet nebo oddělený importní profil, zařízení odpovídá jednomu místu. U více účtů nesmí být identita postavena na zobrazovacím jménu či e-mailu. Potřebná vazba je interní stabilní identita účtu + EIC/EAN + typ entity; metering segment má další identitu měřidla. Opakovaná konfigurace téhož účtu/místa nesmí vytvářet duplicitní zařízení ani statistiky.

Polling portálu sdílej přes koordinátor; místní měření může fungovat při výpadku portálu. Odděleně publikuj stav cloudových dat, lokálního měření a účetního výpočtu. Výpadek nepřemění zachovaná historická data na aktuální potvrzený stav.

### 9.2 Povinné doménové záznamy

| Záznam | Minimální obsah |
| --- | --- |
| Účet / místo | Stabilní identity, komodita, technické údaje a původ; kontaktní profil odděleně |
| Zdrojový artefakt | Typ, SHA-256, bezpečný interní název, zdroj, čas získání a validace |
| Dokladový odečet | Místo, měřidlo, datum/čas a jeho přesnost, kumulativní m³, metoda, status, revize, zdrojový řádek |
| Měřicí segment / kalibrace | Identita měřidla a zdroje, hranice, kotva, návaznost/reset, kvalita |
| Interval spotřeby | Hranice, m³/energie, známé a chybějící části, zdroj a použitá revize |
| Cenový/konverzní úsek | Platnost [od, do), sazby, jednotky, DPH, koeficient, role, původ a úplnost |
| Předpis / platba / účetní událost | Stabilní ID, částka a měna, splatnost/provedení, přiřazení, role, ověření, návazná oprava |
| Vyúčtování | Dokladová identita, interval, položky a výsledek, uhrazení/vrácení, revize a hash |
| Grafový snapshot / prognóza | Čas pozorování, období a tři části MND, případná vlastní metoda a kvalita |
| Pokrytí / běh úlohy | Požadovaný rozsah, segmenty, kurzor, stavy, chyby, důkaz nejstarší hranice |
| Audit | Původní/nová revize, čas, aktér či proces, důvod, vazba na dotčený výpočet |

Neukládej neomezenou historii do atributů stavové entity. Senzory mají stručné aktuální výsledky, počty a důvody omezení; paginované detaily a grafová data poskytuje autorizované rozhraní. Vyúčtování a osobní data nejsou veřejné statické soubory.

### 9.3 Archiv, migrace a obnova

Použij verzovaný soukromý HA Store pro každou entry; originály dokumentů ukládej odděleně do neveřejného umístění. Zápisy jsou atomické, souběh serializovaný a kurzor historie odpovídá uloženému snapshotu. Neúspěšný zápis se nesmí potvrdit jako úspěch v UI. Poškození nebo neznámá budoucí verze úložiště nesmějí vést k přepsání prázdným archivem; zachovej původní soubor, zastav zápisy a nabídni srozumitelnou obnovu.

Vlastní archiv uchová přijaté odečty, vyúčtování, platby, cenové revize, kalibrace, dostatečné měřicí podklady a prognózy i po zkrácení Recorderu. Pro účetní korekce nestačí pouze uložené dnešní číslo. Detailní měření agreguj s doloženým pokrytím a zachováním hranic/změn; při ztrátě rozlišení nepředstírej přesné denní rozdělení. Aktualizace, reauth a změna zálohy archiv nemažou.

Importuj `MndDataArchive` **schema v1** včetně `Readings`, `Coverage`, `Actual`, `Tariffs`, `Payments`, `Documents`, `PricingEvidence`, `Deposit`, `ConsumptionPeriods` a `ConsumptionSnapshots`. Respektuj PascalCase a řetězcové enumy zdrojového kontraktu. Chybějící volitelné pole není prázdný potvrzený výsledek. `Accounting` z C# uchovej jako zdrojový výsledek s proveniencí; HA přepočet má vlastní verzi a může hlásit rozdíl, nikoli jej potichu přepsat.

Windows cesty dokumentů v importu jsou metadata, nikoli cesta k automatickému otevření na HA. Soubory musí projít samostatným autorizovaným importem. Import musí být idempotentní a před potvrzením ukázat změny/konflikty. Verzi vlastního exportu, mapování v1, migrace a zpětnou kompatibilitu přesně dokumentuj. CSV bude mít uvedenou kulturu, jednotky a formát dat; textové buňky ošetři proti spuštění vzorců v tabulkových programech.

Zálohování má exportovat potřebný účetní archiv a doklady podle explicitního výběru, bez přístupových tajemství. Obnova musí ověřit integritu, místo a verzi. Odstranění config entry nesmí bez jasně zvolené samostatné destruktivní akce zničit účetní historii. Retenci a případné odstranění osobních dat popiš a otestuj.

### 9.4 Časování a chyby — navržené výchozí nastavení

Tato čísla jsou požadavkem návrhu, nikoli zjištěným limitem MND; uprav je pouze s doloženým důvodem:

- Souhrnná aktualizace MND po 6 hodinách, metadata smluv/cen nejvýše denně; dokumenty stahovat na vyžádání nebo při nově nalezeném ID. Velká historie je samostatná úloha, nikoli součást každého pollingu.
- Lokální stavy přijímej událostně; pro běžný přepočet sluč změny do nejvýše 30 sekund. Historický účetní dopočet nejvýše jednou za 5 minut a při významné změně kotvy/ceny/platby. Nové změny během běhu vyvolají jeden následný výpočet aktuální revize.
- Výchozí timeout HTTP 30 sekund; nejvýše 3 pokusy na přechodnou síťovou chybu, poté odstup. Při omezení respektuj `Retry-After`; další běhy mají exponenciální odstup a jitter, nikoli souběžné opakované přihlašování.
- Neplatné přihlašovací údaje nebo MFA přejdou do reauth; neprovádět automatický opakovaný pokus s týmž odmítnutým heslem. 401/403 rozliš podle skutečného významu odpovědi, ne vše označit jako síťový timeout.
- Jedna portálová relace/operace měnící aktivní místo na účet; stahování a aktualizace nesmějí přepínat místo pod sebou. Účetní zápisy mají zámek/revize; korekce nemůže být ztracena přepsáním starším výsledkem.
- Blokující parsování a Recorder dotazy běží přes vhodné HA executor API, ne v event loopu. Pro velké soubory nastav mez paměti, času i počtu záznamů.
- Unload odpojí posluchače, zruší časovače, bezpečně ukončí síťové úlohy a uloží kurzor. Restart nezopakuje účetní transakci ani neobnoví zrušený download bez kontroly stavu.
- Stejnou dlouhotrvající chybu loguj při přechodu stavu a zotavení; uživateli ukaž poslední úspěch, stáří a konkrétní reason codes. Neschovávej problém za nulovou hodnotu nebo neomezené tiché retry.

## 10. Konfigurace, entity a akce Home Assistantu

### 10.1 Uživatelský průchod

1. Přidat integraci: připojení MND nebo samostatný importní profil. Ověření přístupu bez zveřejnění tajemství.
2. Vybrat účet/místa a načíst jejich skutečné identity. Nevybraná místa se nemají náhodně míchat do součtů.
3. U každého plynového místa vybrat existující kumulativní senzor nebo ruční režim; nastavit návaznost měřidla a případnou kalibraci.
4. Zvolit zúčtovací období, počáteční bod/kredit, doložený převod a cenové úseky. U známých údajů navrhnout hodnoty z MND, ale nejasné významy neoznačovat za ověřené.
5. Na jedné stránce evidovat zálohy a platby, samostatně importovat/potvrdit vyúčtování. Běžné zadávání nevyžaduje psaní JSON ani YAML.
6. Importovat nebo dotáhnout historii, sledovat skutečný průběh a chybějící podklady.
7. Otevřít Generate dashboard, zkontrolovat náhled a přidat přehled do horní lišty.

Options flow rozdělit na připojení, místa/zdroje, odečty/kalibraci, období/ceny, zálohy/platby, vyúčtování/doklady, historii/export a dashboard. Reauth nemění entity ani archiv. Přepnutí zdroje vyžaduje validaci kompatibility, ne smazání původního měření.

### 10.2 Povinné výstupy pro každé místo

Názvy níže vyjadřují význam; entity ID se generují z registru a nejsou pevně předepsané. Každý výsledek nese čas, zdroj, kvalitu/úplnost a důvod nedostupnosti, kde je to významné.

| Skupina | Požadované veličiny |
| --- | --- |
| Měření | Poslední stav MND m³, datum a metoda; poslední místní stav m³; aktuální kalibrovaný stav; přírůstek po kotvě; aktivní plynoměr |
| Spotřeba | Spotřeba období m³ a při známém převodu kWh/MWh, začátek/konec, poslední měření, pokrytí a nejistota |
| Ceny | Aktivní tarif a platnost, obchodní a plná známá cena, stálé složky, stav úplnosti a původ |
| Zálohy | Aktuální předpis, doporučení MND, plán období, skutečně zaplaceno, předpokládané platby zvlášť, chybějící/po splatnosti |
| Účetnictví | Průběžné známé náklady, úplný průběžný výsledek pokud možný, odhad celého období, odhad salda, kvalita |
| Vyúčtování | Poslední potvrzené období, cena faktury, přeplatek/nedoplatek, zbývá uhradit/vrátit, rozdíl vůči místnímu výpočtu |
| Prognózy | Poslední MND výhled, skutečná/odhadovaná minulost/budoucnost, vlastní výhled a dostupné srovnání uložených verzí |
| Diagnostika | Stav připojení, poslední úspěch, průběh historie, konflikty, kalibrace vyžaduje kontrolu, archiv, zdroje a důvody omezení |
| Akce | Aktualizovat MND, dotáhnout historii, zrušit úlohu, přepočítat účetnictví, Generate dashboard |

Jednotky, `device_class` a `state_class` musí odpovídat skutečnému významu. Přepočitatelné saldo, prognóza a korekcemi klesající účetní stav nejsou monotónní čítač. Nekonfiguruj pro ně `total_increasing` jen kvůli grafu. Výstup pro Energy musí mít doloženou návaznost a korektní statistiky; původní senzor ani jeho statistiky nikdy nepřepisuj. Přidání do Energy je samostatná volba uživatele, ne vedlejší účinek generátoru.

Celé archivy, čísla smluv, kontakty a dokumenty nevystavuj v Recorder a běžných diagnostických senzorech. Metadata potřebná pro pochopení výsledku nesmějí naopak chybět. Zdrojový senzor zůstává uživateli zachovaný.

### 10.3 Akce a jejich smlouva

Připrav smysluplné služby/akce v doméně integrace pro aktualizaci, backfill, zrušení, import/export, uložení/opravný záznam ručního odečtu, kalibraci, úpravu předpisu, potvrzení/přiřazení platby, fakturu, přepočet a generátor. Názvy sjednoť v UI, `services.yaml` a dokumentaci. U každé uveď povinné místo/entry, vstupní jednotky a čas, změnu dat, výsledek, idempotenci, chyby a oprávnění. Více účtů/míst nikdy neřeš volbou „prvního“.

Upload/download je autentizovaný a omezený rozsahem oprávnění. Klient nesmí zadat libovolnou serverovou cestu ani URL pro stažení. Administrátorský zápis do dashboardu, profilem omezené finanční změny a čtení dokladů kontroluje server, nejen viditelnost tlačítka. Ověř chování běžného uživatele i správce a vše zdokumentuj; nespoléhej na utajení URL.

## 11. Generátor dashboardu do horní lišty

### 11.1 Spuštění a náhled

Stejně jako v ČEZ přidej tlačítko **Generate dashboard** na zařízení a do konfigurace. Otevře generátor se skutečnými registry entity ID, výběrem místa, názvu a cesty. Náhled musí ukázat chybějící entity a případnou frontend závislost. Instanci nelze odvozovat z osobního názvu senzoru vývojáře.

Hlavní akce je **Přidat do horní lišty** existujícího ručně spravovaného storage Overview `/lovelace`. Přidává jeden hlavní view pro vybrané místo a detailní `subview` s návratem. Nemá automaticky vytvářet dashboard v boční liště. Více míst musí mít jednoznačné cesty a volbu místa; souhrn přes měřidla se nevydává za jedno vyúčtování.

### 11.2 Výchozí složení

| Pohled | Obsah |
| --- | --- |
| Hlavní „MND“ | Místo a období, aktuální stav a stáří, potvrzený odečet MND, průběžná spotřeba/náklady, záloha a skutečné úhrady, předpokládaný přeplatek/nedoplatek, samostatně poslední faktura, stručný graf a varování kvality |
| Detail Spotřeba | Stav plynoměru a přírůstky, historie odečtů se zdroji/statusy, tři části grafu MND, měsíční/denní skutečnost s pokrytím, kalibrace a konflikty |
| Detail Účetnictví | Platné ceníky a koeficient, rozpad nákladů, průběžná skutečnost a odhad, zálohy/úhrady, faktury/vratky/kredit a rozdíly |
| Detail Prognózy | Volba snapshotu, zdroj MND/HA, shodné období a porovnání s pozdějším měřením, metoda a nejistoty |
| Editor | Ruční odečty, zálohy a platby, potvrzení dokladů a opravy s historií; složitý editor není hlavní přehled |
| Historie a doklady | Import/export, průběh stahování, mezery, bezpečné odkazy na dokumenty a diagnostika |

Rozvržení přizpůsob desktopu i mobilu. Použij HA téma, dobrý kontrast a jasné názvy, např. „Potvrzená spotřeba MND“, „Navazující měření HA“, „Odhad výsledku období“, „Vyúčtování MND“. Potvrzený přeplatek vizuálně neztotožni s očekávaným.

Pro složitější grafy můžeš převzít ApexCharts Card jako v ČEZ; závislost výslovně uveď a detekuj. Generátor ji sám neinstaluje. Bez ní musí zůstat dostupné základní hodnoty, tabulky a návod, nikoli prázdný účetní přehled. Vlastní editor může být přibalený a registrovaný jako JavaScript module s SHA-256 obsahu pro obnovení cache. Název custom elementu musí být jedinečný pro MND.

### 11.3 Bezpečné přidání a údržba

Zachovej všechny existující views, jejich pořadí, karty, téma a nastavení. Při kolizi cest nabídni odkaz na již existující pohled nebo novou cestu; nic automaticky nemaž a nevytvářej duplicitu. Před zápisem ověř aktuální revizi/hash celé konfigurace; při souběžné uživatelské změně zápis zastav a obnov náhled. Zápis nové sady views je atomický.

Při výpadku odpovědi po zápisu načti skutečný výsledek; nespouštěj druhé slepé přidání a neprováděj „úklid“ smazáním pohledu. YAML a automaticky generovaný Overview nepřebírej bez výslovné akce uživatele; nabídni export fragmentu `views` s přesným návodem připojení, nikoli nahrazení celého dashboardu.

Přebírej místní složení existujících MND views a skutečné entity; neměň uživatelská data generováním nové šablony. Aktualizace integrace sama nepřepíše už uložený dashboard. Cílená migrace karet má náhled změn a zachová obsah uživatele.

**Každá změna dashboardu musí ve stejné změně aktualizovat Generate dashboard i přibalenou šablonu**, včetně hlavního pohledu, detailů, navigace, tooltipů a komentářů. Export a zápis musí zachovat potřebné komentáře; pro JSON reprezentaci je udržuj na podporovaných místech a zvlášť ve zdrojové dokumentaci. Ověř uložený výsledek, ne jen odeslaný payload.

## 12. Git, licence, HACS a kompatibilita

Závazná podrobná politika je v [GIT_POLITIKY_CEZ.md](GIT_POLITIKY_CEZ.md). Převzít pravidla z ČEZ znamená i testy, obsah releasu, kontrolu tagu a ochranu zveřejněných instalačních souborů; nestačí založit Git.

Navržený slug repozitáře je `mnd-tariff-accounting`, cílová výchozí větev dle ČEZ `master_HA`. Název Codex projektu a adresář zůstávají dlouhé podle uživatele. V aktuální přípravě nebyl vytvořen Git ani vzdálený repozitář. Budoucí publikovatelná HACS distribuce má být veřejná jako ČEZ, zatímco WebDownloader zůstává soukromý. Dokumentace HACS výslovně uvádí, že [soukromé repozitáře nepodporuje](https://www.hacs.xyz/docs/faq/private_repositories/). Konkrétní vzdálený repozitář nyní neexistuje a jeho URL nepředstírej jako ověřený odkaz.

Cílová struktura je jedna integrace pod `custom_components/mnd_tariff_accounting/`, veškeré runtime soubory uvnitř, vedle ní dokumentace, testy, balicí skripty, `hacs.json` a CI. Finální ZIP `mnd_tariff_accounting.zip` má soubory integrace přímo v kořeni a vzniká pouze z tagovaného Git stromu. Vycházej z aktuálních [požadavků HACS na integraci](https://www.hacs.xyz/docs/publish/integration/).

Pro novou integraci navrhujeme minimální HA **2026.3.0**, zejména kvůli místnímu balení značky a současnému frontendu; tato kompatibilita zatím není ověřená. Před vydáním ji musí potvrdit skutečné lifecycle a frontend testy, nebo musí být minimum zdůvodněně upraveno současně v manifestu/HACS/dokumentaci. Minimum ČEZ se automaticky nepřenáší jako údaj o MND. Testuj zvolené minimum a vždy nejnovější stabilní HA zjištěný v okamžiku testu.

K 15. 10. 2026 oficiální [přehled vydání HA 2026.10](https://www.home-assistant.io/blog/2026/10/07/release-202610/) uvádí stabilní 2026.10.1. Toto číslo je datovaná reference, nikoli trvalý pin „latest“. CI musí zjistit aktuální stable a odpovídající `pytest-homeassistant-custom-component`; chybějící kompatibilní plugin má explicitně selhat, bez tichého přechodu na beta/starší HA. Testy neznamenají povolení aktualizace živé instalace.

Ověř konfigurační flow, služby, typy entit a `DataUpdateCoordinator` podle aktuální [dokumentace koordinovaného načítání HA](https://developers.home-assistant.io/docs/integration_fetching_data/) a [senzorů](https://developers.home-assistant.io/docs/core/entity/sensor/). Balíček má obsahovat lokální brand assets dle [dokumentace brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/). Připravovaný návrh v `brand-concept/` ještě není hotová sada distribučních ikon.

## 13. Ochrana zákaznických dat

Tajné údaje, celé XLSX/PDF zákazníka, jeho EIC/adresy/čísla smluv, skutečné finanční historie, živé session dumpy, osobní screenshoty a zálohy nepatří do veřejného Gitu, CI artefaktů ani instalačního ZIP. Testy a dashboard šablona používají syntetická data. Chceš-li používat skutečný export při lokálním ověření, pracuj s ním mimo sledované soubory a nesděluj jeho obsah ve veřejném reportu.

Diagnostika musí redigovat i vnořená pole, výjimky s URL a syrové odpovědi. Samotný hash identifikátoru bez posouzení možnosti zpětného odhadu není automaticky anonymizace. Finanční částky a profil se standardně neexportují v diagnostice. Dokumenty nesmějí být ve veřejném `/local/` nebo statické trase.

Neinstaluj telemetrii, analytické skripty ani externí odesílání finančních dat. Uživatelské exporty/zálohy mají odlišný účel a rozsah od diagnostiky a jasně uvedený obsah. Při odebrání přístupu smaž tajemství, ale ne účetní archiv bez zvláštní volby.

## 14. Povinné testy a akceptační kritéria

Níže uvedené kontroly jsou součást definice hotového výsledku. Nestačí pouze kompilace nebo screenshot dashboardu. Každý test musí mít věcnou aserci a odůvodnění; nepiš testy, které jen opakují implementaci.

| ID | Scénář | Požadovaný výsledek |
| --- | --- | --- |
| T01 | Správná/chybná autentizace, vypršení relace, MFA, timeout, omezení serveru | Bez úniku tajemství a opakovaného zamykání účtu, správný reauth/backoff |
| T02 | Dva účty a více míst, změna aktivního místa během požadavku | Žádné promíchání dat, stabilní registrace a žádné duplicity |
| T03 | XLSX se jménem místa, příponou kopie, posunutým záhlavím a oběma date systémy | Správné hodnoty a původ, zachování originálů |
| T04 | Rozpor identit v názvu, nadpisu, Parametry a výběru | Import odmítnut bez částečného přiřazení jinému místu |
| T05 | Vzorce, HTML místo XLSX, XML entity, ZIP bomba, škodlivá cesta, neplatné řádky | Bez spuštění obsahu/úniku cesty, omezené zdroje, jasná diagnostika |
| T06 | Opakovaný import a stejné body s různými statusy | Zdrojové statusy zachovány, jeden logický bod a žádná dvojí spotřeba |
| T07 | Konfliktní hodnoty, reset, výměna měřidla a chybějící návaznost | Neznámý/konfliktní interval místo záporné nebo vymyšlené spotřeby |
| T08 | Prázdný starý export, mezera, časový limit a zrušení historie | Nikdy falešná úplnost; hotové úseky a kurzor zachovány |
| T09 | Duplicitní start, restart, unload a pokračování úlohy | Jedna úloha/relace, idempotence a bezpečné obnovení |
| T10 | Manuální režim bez senzoru i senzorový režim bez ručních zápisů | Obě varianty plnohodnotně použitelné |
| T11 | Všechny příklady priority z kapitoly 5 | Autorita MND, navazující místní data a audit; žádné dvojí účtování |
| T12 | MND pouze s datem a různými intradenními body | Zachovaná časová nejistota, nevymyšlená hodina |
| T13 | `unknown`, `unavailable`, neplatná jednotka, přejmenování a odebrání zdroje | Žádná falešná nula; registry ID zachová kompatibilní vazbu |
| T14 | Kalibrace, reset senzoru, změna měřidla, dlouhá mezera a opakovaná stejná hodnota | Validovaná kontinuita, rozlišení skutečné nuly a zamrzlého zdroje |
| T15 | Koeficient chybí/mění se, m³ vs přepočtený m³, kWh ↔ MWh | Správné jednotky a nedostupná úplná cena při chybějícím podkladu |
| T16 | Změna sazeb/DPH, sleva, následný/alternativní tarif, mezera/překryv | Jen platné sazby, DPH/sleva jednou, odhad přiznaný |
| T17 | Celý/neúplný měsíc, únor, přestupný rok, DST a [od, do) | Správné časové a kalendářní hranice a stálé platby |
| T18 | Předpis, skutečná/částečná/mimořádná úhrada, automatický předpoklad | Oddělené součty, přeplacení je možné, plán nevytvoří skutečnou platbu |
| T19 | Import platby již evidované ručně, nejasné párování | Doložené spárování jednou, nejasnost není automaticky duplicita |
| T20 | Opravená faktura, vratka, převod kreditu, zálohy uvedené na faktuře | Původní a opravený doklad dohledatelný, žádný dvojí náklad/platba |
| T21 | Chybějící saldo/ceny/úhrady vs výslovná nula | Úplný výsledek jen při úplných podkladech; částečné hodnoty odděleně |
| T22 | Syntetický příklad 100 + 1 200 − 1 000, nezaplacený předpis a vratka | Správný průběžný/potvrzený výsledek a stav vypořádání |
| T23 | Tři části grafu, zavádějící CSS a starý tooltip | Výhradně číselná data správného období, budoucnost není skutečný odběr |
| T24 | Chybějící část grafu a překrývající se období | `null` není nula, žádné sčítání překryvu |
| T25 | Nový snapshot, pozdější měření a nesrovnatelná období | Starý odhad zachován, odchylka jen při společném pokrytí |
| T26 | Nedostatek zimní historie a neznámé budoucí ceny | Prognóza označena jako neúplná; žádná přesná zimní hodnota z léta |
| T27 | Zkrácení Recorderu, poškozený Store, neznámá verze, nedostatek místa | Archiv a potvrzená data zachovány; žádný tichý přepis prázdnem |
| T28 | Změna dat během přepočtu a pád během ukládání | Novější revize neztracena, atomický a obnovitelný stav |
| T29 | Import všech volitelných polí kontraktu v1 a opakování importu | Bezeztrátová provenience, schema validace, idempotence a export |
| T30 | Služby, config/options/reauth, setup/unload/reload a migrace | Skutečný HA lifecycle test na minimu i aktuální stable |
| T31 | Nové a přejmenované entity, více míst, chybějící ApexCharts | Generátor používá registry; čitelný náhled a fallback |
| T32 | Přidání do horní lišty, kolize, změna Overview a ztracená odpověď | Zachování cizích views, atomické přidání, bez duplicit a mazání |
| T33 | YAML/automatický Overview, lokálně upravené MND pohledy | Bez nevyžádaného převzetí či přepsání, funkční export fragmentu |
| T34 | Světlé/tmavé téma, mobil/desktop, tooltipy a nulové hodnoty | Správné popisky, navigace a odlišení skutečnosti/odhadu |
| T35 | Oprava dashboardu a nová instalace | Shodná funkce generátoru i přibalené šablony, zachované komentáře |
| T36 | Neoprávněný upload/download/zápis a redakce diagnostiky | Serverová kontrola oprávnění, bez tajemství a osobních dat |
| T37 | Sestavení balíčku z tagu, neshodná verze a existující asset | Reprodukovatelný obsah, chyby při nesouladu, žádný přepis releasu |
| T38 | Kontrola veřejného diffu a ZIP | Jen runtime a syntetická data; žádné zákaznické exporty/přihlášení |

CI: statická kontrola, unit testy doménové logiky, HA lifecycle testy, JS testy generátoru/editoru a balení, HACS, Hassfest, report pokrytí a aktuální stable HA. Verze závislostí musí být reprodukovatelné a kompatibilní s testovaným HA. Ověř Linux a podporovanou architekturu HA; testování pouze na Windows není důkaz použitelnosti integrace.

Živá ověření prováděj jen v rámci aktuální autorizace, s minimem potřebných údajů. Test portálu, skutečného senzoru a zápisu dashboardu vykazuj odděleně. Dostupný přímý HA konektor má přednost před UI, pokud daný krok podporuje. Pokud živé ověření není možné, uveď konkrétní neověřenou funkci; fixture ani test C# nesmí být prezentovány jako živý test nové integrace.

## 15. Etapy implementace a předání

1. **Audit a návrh:** přečti zdroje, doplň mapu M01–M20, ověř současný stav ČEZ a Git politik, rozhodni transport s důkazy. Výstupem je krátký technický návrh a pojmenované blokátory.
2. **Datové jádro a import:** modely, bezpečný XLSX/v1 import, měřicí segmenty, priorita MND, archiv, migrace a účetní engine se syntetickými testy.
3. **HA a portál:** config flow, nativní zdroje spotřeby, manuální formuláře, koordinátory, autentizace, historie, doklady a reauth. Import a lokální účetnictví fungují i offline.
4. **Účetní evidence a prognózy:** zálohy, úhrady, faktury/vratky, uzávěrky, skutečnost vs výhled a historie prognóz; otestuj korekce i zkrácený Recorder.
5. **Frontend:** hlavní přehled, detaily, editory, generátor horní lišty a totožná přibalená šablona; ověř zachování existujícího Overview.
6. **Distribuce:** finální logo s variantami, README CS/EN, dokumentace, testy, CI, bezpečný instalační ZIP, verzování a koncept vydání dle ČEZ. Příprava releasu sama není publikace ani nasazení do živého HA.
7. **Předávací report:** konkrétní implementované funkce, výsledky všech relevantních kontrol, tabulka M/T, seznam skutečně živě ověřených cest, neověřené části, známé limity a návod na instalaci/obnovu.

Za dokončení se nepovažuje jen základ senzorů, graf s pevnými daty nebo náhradní import bez přiznaného chybějícího portálu. Pokud brání externí podmínka, dokonči nezávislé části, dolož překážku a přesně označ zbytek rozsahu.

K odevzdání patří zdroje integrace a příslušné testy, mapování C# → HA, datový kontrakt a migrace, uživatelská dokumentace, vysvětlení účetních vzorců a kvality, popis autentizace a omezení, generátor i šablona, instalovatelný ZIP a report CI. V důležitých blocích kódu popiš česky účel, důvod, vstupy/výstupy, jednotky, časování, prioritu, souběh, restart, ukončení a chování při chybě.

## 16. Ověřené podklady versus dosud neověřený návrh

Upřesnění uživatele 16. 10. 2026: hlavní finanční a spotřební přehled má
používat **účetní období MND, nikoli kalendářní rok**. Originální vyúčtování
má přednost ve vlastním rozsahu. Novější měření HA zůstává označeným
navazujícím zdrojem; nesmí přepsat fakturu ani zdvojit její náklady.
Podrobnosti čtecího přehledu, grafů a cenových předpokladů alpha.4 jsou
v [docs/ALPHA_4.md](docs/ALPHA_4.md).

Reference C# má doložené unit testy a řízený WPF test; živě bylo ověřeno přihlášení, technické údaje místa, dva exporty odečtů a odhlášení. Úplnost historie před nejstarším staženým obdobím potvrzená není. Číselné části živého grafu byly ověřeny samostatně v prohlížeči; programové otevření tooltipů po doplnění C# nebylo znovu živě testováno. Živý test C# neověřil smluvní PDF, profil ani platební přehled. Konkrétní HA senzor a jeho měřicí historie nebyly v referenčním testu k dispozici.

Tato příprava neposkytuje důkaz, že přihlášení MND bude fungovat bez WebView2, že parser pokrývá všechny faktury nebo že nový dashboard běží v HA. Výše uvedené kroky a testy má teprve provést implementující Sol 6.1 v určeném projektu. Aktuální lokální úpravy ČEZ mohou obsahovat důležité opravy, které ještě nejsou v posledním commitu; jejich stav je zachycen v podkladech.
