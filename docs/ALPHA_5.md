# Alpha.5 — měření kotle a jednodušší přehled

Report 26. 10. 2026. Verze `0.1.0-alpha.5` má ověřený neměnný tag,
úspěšné CI a připravený draft s instalačním ZIPem. Runtime byl z tohoto tagu
zkopírován do živého HA a omezená změna Overview byla zapsána a ověřena.
Restart HA Core v 18:28 Europe/Prague byl úspěšně dokončen. V běžícím
HA 2026.10.4 bylo následně ověřeno uložené nastavení zdrojů kotle, aktualizace
živých metrik, nativní provozní historie a zachování kontrolovaných účetních
podkladů. Neveřejný draft ani zbývající omezení uvedená níže se tím nemění.

## Rozsah

- Volitelné čtecí měření elektrického příkonu kotle pro každé odběrné místo.
  Administrace nabízí výběr W/kW, volitelné kumulativní Wh/kWh a požadavku
  topení; před uložením ukazuje náhled a dostupnost zvolených zdrojů.
- Elektřina kotle zůstává oddělená od plynu, cenových úseků a vyúčtování MND.
  Požadavek termostatu ani samotný elektrický příkon není důkaz plamene.
  Tato úprava nemění ovládání kotle, napájení zásuvky ani teplotní program.
- Hlavní přehled obsahuje právě teď, spotřebu a výhled vyúčtování s nejvýše
  jedním sedmidenním grafem. Provozní a měsíční grafy jsou v podrobnostech
  Spotřeba, finanční tabulky a graf zůstávají v Účetnictví.
- Živé hodnoty nevyžadují nové načtení celé karty a zachovávají fokus i
  rozepsané formuláře. Nula, zastaralý report a chybějící údaje jsou odlišné.
- Generátor a přibalená šablona používají kompozici 4, zachovávají hlavní
  pohled, pět subviews, navigaci a zpětné cesty. Konkrétní domácí entity
  nejsou součástí distribuované šablony.

Význam jednotek, pokrytí, časování, souběhu a restartu podrobně popisuje
[Kotel a přehled](KOTEL_A_PREHLED.md).

## Dokončené ověření

| Oblast | Doložený stav |
| --- | --- |
| Doménové testy a validace | 148 testů prošlo; Ruff a compileall bez chyb |
| Frontend a navigace | 40 Node testů prošlo; desktopový syntetický náhled i živá kompozice tří bloků ověřeny. Mobilní viewport nebyl prohlížečem skutečně přepnut, proto mobilní vizuální ověření zatím není doložené |
| HA minimum | Skutečný Linux běh HA 2026.3.1 / plugin 0.13.317 / Python 3.14: 32 testů prošlo |
| Aktuální stable | Skutečný Linux běh HA 2026.10.4 / plugin 0.13.375 / Python 3.14: 32 testů prošlo |
| Quality, HACS, Hassfest | Úspěšné kontroly nové revize; konkrétní odkazy níže |
| Tag a instalační ZIP | `v0.1.0-alpha.5`, 49 runtime souborů; draft ZIP ověřen proti tagu |
| Záloha | Na HA ověřen TAR runtime, účetního archivu a dokladů; původní runtime navíc odděleně |
| Živé nasazení | Alpha.5 nasazena do HA 2026.10.4; restart Core úspěšný, nastavení zdrojů a funkční živé metriky ověřeny po restartu |
| Overview | Šest vlastních MND karet aktualizováno z kompozice 3 na 4; uložená konfigurace ověřena a ostatní pohledy zachovány |
| Účetní a dokladová integrita | Kontrolované sekce všech míst před a po nasazení přesně shodné; SHA-256 zahrnutých originálních dokumentů souhlasí |

Předchozí úspěšné testy alpha.4 nejsou důkazem kompatibility nových změn.
Proto byly dokončeny nové Ubuntu běhy pro obě výše uvedené přesné dvojice.
Samostatný doménový běh má 148 Python testů a frontendový běh 40 Node testů;
tyto počty se nevydávají za počet lifecycle testů Home Assistantu.

## Ověřená revize a artefakty

Neměnný tag `v0.1.0-alpha.5` ukazuje na commit
`6e3b5db8d87a96118ebf2bf54753c969fc8e2429`.

- [Quality 40322857560](https://github.com/79thales/mnd-tariff-accounting/actions/runs/40322857560): úspěšné doménové, frontendové a obě skutečné HA testovací varianty.
- [HACS 40322857186](https://github.com/79thales/mnd-tariff-accounting/actions/runs/40322857186): úspěšné.
- [Hassfest 40322857289](https://github.com/79thales/mnd-tariff-accounting/actions/runs/40322857289): úspěšné.
- [Příprava draftu 40323842786](https://github.com/79thales/mnd-tariff-accounting/actions/runs/40323842786): úspěšná včetně závislých kontrol, buildu a přiložení instalátoru.
- [Připravený draft](https://github.com/79thales/mnd-tariff-accounting/releases/tag/untagged-e186e3243c6223c0f8ac) zůstává neveřejný; jeho popis používá český styl podle reference ČEZ. Existující release a assety alpha.1 až alpha.4 se nemění.

Instalační ZIP `mnd_tariff_accounting.zip` má **187 926 bajtů**, **49 runtime
souborů** a SHA-256
`d72c76579ef5a52a8de3fc677b7ea6c487c08fccddd8583022890f6b976bfefb`.
Obsah byl ověřen proti neměnnému tagu; pracovní adresář není zdrojem balíku.

Pro povolené živé nasazení bez veřejné publikace prerelease byl použit
veřejný neměnný zdrojový TAR téhož tagu. SHA-256
`72161c96469c18d367434c46564709cb74a38cc0d21fc2e57f64f2934ed7eb36`
bylo ověřeno místně i na HA. Z něj se použilo pouze 49 souborů integračního
runtime; manifest v cílovém adresáři potvrzuje alpha.5. Po dokončeném restartu
byly ověřeny nové administrační volby, jejich uložený readback a živé metriky
v běžícím Core. Ověření tedy nezůstalo pouze u obsahu cílového adresáře.

## Živé ověření po restartu

- HA Core 2026.10.4 znovu běží. V administraci odběrného místa bylo uloženo
  zapnutí elektrického měření a výslovný výběr zdrojů příkonu a kumulativní
  energie. Následný readback potvrdil, že volba přetrvala. Volitelný požadavek
  topení při tomto živém ověření nebyl vybrán.
- Přehled a detail Spotřeba zobrazují aktuální elektrické metriky a jejich
  aktualizace. Detail načetl nativní 24hodinovou historii. Denní a měsíční
  elektrické souhrny výslovně přiznávají neúplné pokrytí uzavřených hodin
  a čas „data do“; známá část se nevydává za úplný den nebo měsíc.
- Následná kontrola přehledu po 18:36 potvrdila čerstvý živý průtok i příkon
  a dotažení plynových souhrnů k jejich novější hranici pokrytí. Na desktopu
  byla vizuálně ověřena kompozice tří hlavních bloků.
- Účetní podstránka bez UI chyby načetla účetní období, náklady a zálohy,
  historii záloh i vyúčtování. Jejich skutečné částky se nezveřejňují.
- Soukromé porovnání kanonicky seřazených JSON údajů pomocí `jq -S` potvrdilo
  pro všechna místa přesnou shodu sekcí `readings`, `tariffs`, `conversions`,
  `events`, `invoices`, `imports` a `artifacts` před a po nasazení. Nová volba
  kotle se ukládá v nastavení; toto očekávané rozšíření není vydáváno za
  bezezměnovou shodu celého úložiště.
- SHA-256 všech zahrnutých originálních dokumentů odpovídají záloze;
  kontrola nehlásila neshodný originál. Identifikátory, entity, skutečné
  provozní a finanční hodnoty zůstávají pouze v soukromém protokolu.
- V kontrolovaném omezeném vzorku logu HA Core nebyla nalezena chyba,
  výjimka ani traceback přiřazený MND. Nejde o tvrzení o úplné historii
  logů nebo bezchybnosti všech ostatních integrací.
- Uložená konfigurace šesti vlastních MND karet používá layout 4. Porovnání
  potvrdilo zachování ostatních pohledů Overview.

## Vydání a návrat

Před vytvořením nové verze byly ověřeny existující tagy a release; žádný starý
tag ani asset nebyl přepsán. Publikace draftu je oddělená od autorizovaného
živého nasazení. Draft není veřejnou HACS aktualizací a tento report její
dostupnost uživatelům HACS netvrdí.

Před výměnou runtime byla na HA úspěšně vytvořena záloha runtime, účetního
archivu a dokladů v TARu a navíc samostatná kopie původního runtime. Archiv
a `.storage` relace se při výměně integračního kódu nepřepisují. Konfigurace
Overview byla před omezeným patchem načtena; změna šesti vlastních MND karet
z layoutu 3 na 4 byla po zápisu ověřena. Zachování ostatních pohledů bylo
potvrzeno porovnáním uložené konfigurace.

Existence těchto záloh je doložená na HA. Tento report zatím nedokládá jejich
samostatné stažení na PC ani dokončenou zkoušku obnovy aktuální zálohy.
Soukromé zálohy, názvy souborů s identitami, entity a detailní protokol
nepatří do veřejného repozitáře. Návrat použije původní runtime a uložený
dashboard při zachování novějších měřených dat.

Backendové Python moduly a jednorázová registrace statického frontendu
vyžadují po výměně runtime plné znovunačtení HA Core; samotný reload
ConfigEntry není dokladem načtení nové verze. Nejde o upgrade HA ani restart
hostitelského systému. Tento restart i cílená kontrola nových administračních
voleb, uložených zdrojů, živých metrik, historie, souhrnů a zachování
kontrolovaných účetních podkladů jsou dokončené.

## Zbývající omezení

- Požadavek termostatu je informativní. Samostatná čerstvost tohoto požadavku
  se zatím nevyhodnocuje stejně jako stáří průtoku a příkonu; starý stav
  požadavku se nesmí použít jako důkaz aktuálního topení ani hoření. Integrace
  podle něj neprovádí provozní řízení.
- Desktopový syntetický náhled i živý hlavní přehled jsou ověřené. Skutečné přepnutí mobilního
  viewportu a vizuální ověření na mobilu zatím není doložené; samotné DOM
  testy a responsivní CSS nejsou jeho náhradou.
- Zálohy jsou ověřené na HA, ale samostatnou kopii na PC se přes použité UI
  ani stažení ve File editoru nepodařilo doložit. Zkouška obnovy aktuální
  zálohy nebyla provedena; kontroly shody dat a hash originálů nejsou její
  náhradou.
