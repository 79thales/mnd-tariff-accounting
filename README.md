# MND Tariff & Accounting – plyn a vyúčtování pro Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.3.1%2B-41BDF5?logo=home-assistant&logoColor=white&style=flat)](https://www.home-assistant.io/)
[![Integrace HACS](https://img.shields.io/badge/HACS-Integrace-41BDF5?logo=home-assistant-community-store&logoColor=white&style=flat)](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=mnd-tariff-accounting&category=integration)
[![Nejnovější vydání](https://img.shields.io/github/v/release/79thales/mnd-tariff-accounting?include_prereleases&label=Vyd%C3%A1n%C3%AD&logo=github&style=flat)](https://github.com/79thales/mnd-tariff-accounting/releases)
[![Stažení instalátoru celkem](https://img.shields.io/github/downloads/79thales/mnd-tariff-accounting/mnd_tariff_accounting.zip?label=Sta%C5%BEen%C3%AD%20celkem&displayAssetName=false&logo=github&style=flat)](https://github.com/79thales/mnd-tariff-accounting/releases)
[![Stažení instalátoru nejnovější verze](https://img.shields.io/github/downloads/79thales/mnd-tariff-accounting/v0.1.0-beta.4/mnd_tariff_accounting.zip?label=Sta%C5%BEen%C3%AD%20verze&displayAssetName=false&logo=github&style=flat)](https://github.com/79thales/mnd-tariff-accounting/releases/tag/v0.1.0-beta.4)
[![Kontroly](https://img.shields.io/github/check-suites/79thales/mnd-tariff-accounting/master_HA?label=Kontroly&logo=github&style=flat)](https://github.com/79thales/mnd-tariff-accounting/actions)
[![Licence MIT](https://img.shields.io/github/license/79thales/mnd-tariff-accounting?label=Licence&style=flat)](LICENSE)

<p align="center">
  <img src="https://raw.githubusercontent.com/79thales/mnd-tariff-accounting/master_HA/custom_components/mnd_tariff_accounting/brand/icon@2x.png" alt="MND Tariff & Accounting" width="180">
</p>

## Nově ve verzi 0.1.0-beta.4

Přehled rozlišuje vlastní odhad podle měření a výhled MND. Výsledek se
průběžně přepočítává z doloženého odběru, sezónní historie, cen a záloh.
Při chybějících podkladech zobrazí konkrétní důvod; historie, platby ani
prognóza MND se nevydávají za nulové hodnoty. [Podmínky a postup](docs/VLASTNI_ODHAD.md).

## O integraci

Nezávislá komunitní integrace pro sledování plynu, nákladů a vyúčtování MND
v Home Assistantu. Spojuje odečty a doklady dodavatele s místním měřením,
uchovává jejich původ a rozlišuje skutečné platby, předpisy záloh a prognózy.
Běžný dashboard slouží k prohlížení; správa odběrného místa je v konfiguraci
příslušného zařízení MND.

[Aktuální vydání](https://github.com/79thales/mnd-tariff-accounting/releases/tag/v0.1.0-beta.4)

**Stav: beta.** Verze je určená k testování, nikoli označená jako stabilní.
Přípravu a živé ověření funkcí popisuje [report](docs/ALPHA_5.md).
Historii ověřování popisují [alpha.4](docs/ALPHA_4.md), [alpha.3](docs/ALPHA_3.md),
[alpha.2](docs/ALPHA_2.md) a [původní report](IMPLEMENTACE.md).

Odznaky stažení počítají pouze instalační přílohu `mnd_tariff_accounting.zip`,
včetně aktualizací a ručního stažení. Nejde o počet uživatelů ani aktivních
instalací. Celkový odznak sčítá přílohy všech vydání; odznak verze patří
veřejné beta.4. Zdrojové archivy a instalace z větve se nezapočítávají.
Údaje mohou být dočasně uložené v mezipaměti; integrace kvůli nim neposílá
telemetrii.

## Požadavky

- Home Assistant `2026.3.1` nebo novější.
- HACS při instalaci přes HACS.
- Účet MND pro přístup k portálu, nebo vlastní podklady pro importní profil.
- Běžný přehled používá přibalený frontend bez externích karet Lovelace.

## Co integrace umí

- XLSX s ověřením EIC, českých čísel, obou Excelových kalendářů a bezpečnosti.
- Import C# archivu v1 včetně cen, úhrad, metadat dokumentů a prognóz.
- Auditní odečty a jejich opravy, nativní senzor m³, kalibrace a Recorder backfill.
- Předpisy oddělené od úhrad, částečné i vyšší platby, faktury a vratky.
- Časově platné ceny a převody, explicitní DPH, pravidla stálých plateb.
- Archivované tři části grafu MND a srovnání se shodnou potvrzenou fakturou.
- Vlastní sezonní odhad pouze při pokrytém předchozím roce měření.
- Soukromé originály a JSON/ZIP zálohy, obnova a CSV export.
- Jednoduchý čtecí přehled v horní liště HA, administrace z detailu zařízení MND.
- Účetní období MND, náklady a zálohy ve společném grafu, měsíční HA sloupce m³.
- Průtok m³/h, historie záloh a úhrad, fakturační detaily a oddělené exporty MND.
- Formuláře a Generate dashboard pro horní lištu existujícího Overview.
- Volitelné měření příkonu a elektrické energie kotle s pokrytím denních
  a měsíčních souhrnů; provozní historie v detailu Spotřeba.
- Čtecí cloudový klient podle nalezeného veřejného JS MND, reauth a obnovitelná
  historie. [Autentizace a hranice ověření](docs/AUTENTIZACE.md).

## Instalace do Home Assistantu

[![Otevřít repozitář MND v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=mnd-tariff-accounting&category=integration)
[![Přidat integraci MND do Home Assistantu](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mnd_tariff_accounting)

Tlačítko **Přidat integraci** otevře přímo konfiguraci MND ve vašem
Home Assistantu. Nejdříve nainstalujte integrační soubory a restartujte HA.
Tlačítko **HACS** otevře tento repozitář jako integraci, stejně jako u ČEZ.
Testovací [vydání v0.1.0-beta.4](https://github.com/79thales/mnd-tariff-accounting/releases/tag/v0.1.0-beta.4)
je dostupné jako **prerelease**. V HACS obnovte informace repozitáře, zapněte
zobrazení beta verzí a při stahování vyberte **v0.1.0-beta.4**. V dialogu má
být uvedena tato verze, nikoli commit výchozí větve. Po instalaci restartujte HA.

Pro ruční instalaci je dostupný [instalační ZIP](https://github.com/79thales/mnd-tariff-accounting/releases/download/v0.1.0-beta.4/mnd_tariff_accounting.zip).

Quality, HACS a Hassfest se ověřují pro každý tag. Skutečné HA testy používají
minimum 2026.3.1 a aktuální stabilní verzi s přesně odpovídajícím pluginem.
Alpha.4 přidává čtecí finanční přehled z MND, původní faktury a aktuálního
ověřeného ceníku. Náklady používají doložené ceny s DPH; orientační poměr
stálých plateb a dosud neznámé budoucí regulované ceny jsou označené jako
předpoklady. Nepodporovaný formát dokumentu zůstane neznámý, nikoli nulový.
DOM a protokolové testy nenahrazují mobilní vizuální kontrolu.
[Podrobnosti a omezení alpha.4](docs/ALPHA_4.md).

Po schválené instalaci patří celý adresář `custom_components/mnd_tariff_accounting/`
do konfigurace HA. ZIP z vydání obsahuje runtime přímo v kořeni; rozbalte
jej do `config/custom_components/mnd_tariff_accounting/` a restartujte HA.
V **Nastavení → Zařízení a služby → Přidat integraci → MND**
zvolte importní profil nebo účet MND. EIC a číslo měřidla jsou text.
Přihlašovací údaje patří do chráněného formuláře HA, nikoli do zdrojů.
Uložení hesla je výslovná volba; běžné úložiště HA není šifrovaný trezor.

## Nastavení odběrného místa

Správa je v **Nastavení → Zařízení a služby → Zařízení → MND** pro dané
odběrné místo. Otevřete jeho konfigurační odkaz; účet i místo jsou již vybrané.
Zde nastavíte období, kumulativní senzor, průtok, platnost reportu, kalibraci,
ceny a převod. Přihlášení a odhlášení ovlivňuje celý příslušný účet MND.

Historie záloh a vyúčtování se načítá do odděleného čtecího přehledu.
Před převzetím předpisů a skutečných úhrad do místní knihy potvrďte jejich
přiřazení k nastavenému období a zkontrolujte ruční duplicity. PDF faktury
nepotvrzuje automaticky její úplné účetní náklady.

## Dashboard

**Generate dashboard → Vytvořit náhled → Uložit MND v horní liště** přidá nebo
aktualizuje vlastní MND views v `/lovelace`. Použijte stejnou cestu jako dříve.
Před zápisem se stáhne záloha Overview; cizí karty, názvy a pořadí se zachovají.
Generátor i přibalená šablona používají stejnou kompozici dané verze. Po instalaci
obnovte aplikaci/prohlížeč. Importy, editory a generátor jsou dostupné z
konfigurace zařízení; běžný dashboard slouží k prohlížení.
YAML a automatický Overview mají export fragmentu `views`. Soukromé údaje,
doklady a finanční zápisy vyžadují správce a kontrolují se na serveru.

Průběžné saldo, prognóza a potvrzené vyúčtování mají odlišný význam.
Odečet MND převažuje pro shodnou hranici. Neznámý čas není půlnoc a reset
nezíská automatický offset. [Účetní model](docs/UCETNI_A_DATOVY_MODEL.md).

## Licence

Integrace používá [licenci MIT](LICENSE), stejně jako ČEZ Dynamic Tariff
& Accounting. Úplný text licence a copyright jsou přibalené také
v integračním adresáři a instalačním ZIPu.

## Vývoj a vydání

```text
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
pnpm install --frozen-lockfile --ignore-scripts
node --test tests/*.test.js
python scripts/resolve_latest_ha.py
```

Skutečné HA testy jsou v `tests_homeassistant/`; CI používá Linux, minimum
a dynamicky zjištěnou stable s přesným pluginem. Chyba resolveru nepřejde
na beta či starší náhradu. Instalační ZIP vzniká pouze z Git stromu tagu.
Vydání začíná draftem, publikované tagy/assets jsou neměnné.
[Proces vydání](docs/VYDANI.md), [Git politika](GIT_POLITIKY_CEZ.md),
[changelog](CHANGELOG.md), [návrh značky](NAVRH_LOGA.md), [vzhled MND](docs/VZHLED_MND.md).
