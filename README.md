# MND Tariff & Accounting for Home Assistant

[![Přidat integraci MND do Home Assistantu](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mnd_tariff_accounting)
[![Otevřít repozitář MND v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=mnd-tariff-accounting&category=integration)

Samostatná integrace plynu podle [úplného zadání](ZADANI_MND_SOL_6_1.md).
Runtime je Python, přibalený frontend JavaScript bez externí Lovelace
závislosti. Nepotřebuje WPF, WebView2 ani REST token k vlastnímu HA.

**Stav: vývojová verze 0.1.0-alpha.3.** Oprava stahování po živém testu je
v [reportu alpha.3](docs/ALPHA_3.md); rozvržení, migrace a omezení popisuje
[alpha.2](docs/ALPHA_2.md). [Původní report](IMPLEMENTACE.md) zachovává historii alpha.1.
Zdroj je ve veřejném repozitáři [79thales/mnd-tariff-accounting](https://github.com/79thales/mnd-tariff-accounting).
Vydání instalátoru je oddělené od zveřejnění zdrojů.

## Funkce

- XLSX s ověřením EIC, českých čísel, obou Excelových kalendářů a bezpečnosti.
- Import C# archivu v1 včetně cen, úhrad, metadat dokumentů a prognóz.
- Auditní odečty a jejich opravy, nativní senzor m³, kalibrace a Recorder backfill.
- Předpisy oddělené od úhrad, částečné i vyšší platby, faktury a vratky.
- Časově platné ceny a převody, explicitní DPH, pravidla stálých plateb.
- Archivované tři části grafu MND a srovnání se shodnou potvrzenou fakturou.
- Vlastní sezonní odhad pouze při pokrytém předchozím roce měření.
- Soukromé originály a JSON/ZIP zálohy, obnova a CSV export.
- Jednoduchý čtecí přehled v horní liště HA, administrace z detailu zařízení MND.
- Průtok m³/h, historie záloh a úhrad, fakturační detaily a oddělené exporty MND.
- Formuláře a Generate dashboard pro horní lištu existujícího Overview.
- Čtecí cloudový klient podle nalezeného veřejného JS MND, reauth a obnovitelná
  historie. [Autentizace a hranice ověření](docs/AUTENTIZACE.md).

## Použití vývojové verze

Tlačítko **Přidat integraci** nahoře otevře přímo konfiguraci MND ve vašem
Home Assistantu. Nejdříve nainstalujte integrační soubory a restartujte HA.
Tlačítko **HACS** otevře tento repozitář jako integraci, stejně jako u ČEZ.
Testovací [vydání v0.1.0-alpha.3](https://github.com/79thales/mnd-tariff-accounting/releases/tag/v0.1.0-alpha.3)
je dostupné jako **prerelease**. V HACS obnovte informace repozitáře, zapněte
zobrazení beta verzí a při stahování vyberte **v0.1.0-alpha.3**. V dialogu má
být uvedena tato verze, nikoli commit výchozí větve. Po instalaci restartujte HA.

Pro ruční instalaci je dostupný [instalační ZIP](https://github.com/79thales/mnd-tariff-accounting/releases/download/v0.1.0-alpha.3/mnd_tariff_accounting.zip).

Quality, HACS a Hassfest se ověřují pro každý tag. Skutečné HA testy používají
minimum 2026.3.1 a aktuální stabilní verzi s přesně odpovídajícím pluginem.
DOM a protokolové testy nenahrazují zákaznické ověření nových finančních
endpointů a mobilní vizuální kontrolu. Úplné automatické smluvní ceny zůstávají
omezením; doložené tarify lze zadat nebo importovat. [Podrobnosti alpha.2](docs/ALPHA_2.md).

Po schválené instalaci patří celý adresář `custom_components/mnd_tariff_accounting/`
do konfigurace HA. ZIP z vydání obsahuje runtime přímo v kořeni; rozbalte
jej do `config/custom_components/mnd_tariff_accounting/` a restartujte HA.
V **Nastavení → Zařízení a služby → Přidat integraci → MND**
zvolte importní profil nebo účet MND. EIC a číslo měřidla jsou text.
Přihlašovací údaje patří do chráněného formuláře HA, nikoli do zdrojů.
Uložení hesla je výslovná volba; běžné úložiště HA není šifrovaný trezor.

Správa je v **Nastavení → Zařízení a služby → Zařízení → MND** pro dané
odběrné místo. Otevřete jeho konfigurační odkaz; účet i místo jsou již vybrané.
Zde nastavíte období, kumulativní senzor, průtok, platnost reportu, kalibraci,
ceny a převod. Přihlášení a odhlášení ovlivňuje celý příslušný účet MND.

Historie záloh a vyúčtování se načítá do odděleného čtecího přehledu.
Před převzetím předpisů a skutečných úhrad do místní knihy potvrďte jejich
přiřazení k nastavenému období a zkontrolujte ruční duplicity. PDF faktury
nepotvrzuje automaticky její úplné účetní náklady.

**Generate dashboard → Vytvořit náhled → Uložit MND v horní liště** přidá nebo
aktualizuje vlastní MND views v `/lovelace`. Použijte stejnou cestu jako dříve.
Před zápisem se stáhne záloha Overview; cizí karty, názvy a pořadí se zachovají.
Generátor i přibalená šablona mají stejnou kompozici verze 2. Po instalaci
obnovte aplikaci/prohlížeč. Importy, editory a generátor jsou dostupné z
konfigurace zařízení; běžný dashboard slouží k prohlížení.
YAML a automatický Overview mají export fragmentu `views`. Soukromé údaje,
doklady a finanční zápisy vyžadují správce a kontrolují se na serveru.

Průběžné saldo, prognóza a potvrzené vyúčtování mají odlišný význam.
Odečet MND převažuje pro shodnou hranici. Neznámý čas není půlnoc a reset
nezíská automatický offset. [Účetní model](docs/UCETNI_A_DATOVY_MODEL.md).

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

## English

[Add MND integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=mnd_tariff_accounting) · [Open in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=mnd-tariff-accounting&category=integration)

Install the integration files and restart HA before using **Add integration**.
The [alpha prerelease](https://github.com/79thales/mnd-tariff-accounting/releases/tag/v0.1.0-alpha.3)
is now public. Refresh repository information in HACS, enable beta versions
and select **v0.1.0-alpha.3** in the download dialog instead of a default-branch
commit. Restart HA after installation. A [manual installer ZIP](https://github.com/79thales/mnd-tariff-accounting/releases/download/v0.1.0-alpha.3/mnd_tariff_accounting.zip)
is also available.

Independent community Home Assistant gas accounting integration. It imports
MND XLSX and the C# v1 archive, keeps auditable readings, tariffs, actual
payments, invoices and historical forecast snapshots, and provides a bundled
panel and an Overview dashboard generator.

Development version 0.1.0-alpha.3 is not a verified production release.
The corrective document download change is described in `docs/ALPHA_3.md`.
The normal Overview tab is read-only; supply point administration opens from
its MND device configuration link. The generator and bundled template update
existing MND cards while preserving unrelated cards, titles and view order.
Flow sensors support exact conversion to m³/h. Advance/invoice histories,
allocated payment details, separate exports and invoice PDF downloads are available.
Accepting advances into the local ledger requires an explicit period allocation.

Quality, HACS and Hassfest run against each release tag, with real HA tests on
the supported minimum and dynamically resolved stable version. New financial
endpoints and mobile visual QA still need customer validation. Complete automatic
contract pricing is not implemented. See `docs/ALPHA_2.md` for migration and limits.

Unknown values remain distinct from zero, planned advances from actual
payments, and forecasts from confirmed invoices. Credentials, private
documents and real customer data are excluded from source control,
diagnostics and the installer. The MIT license preserves adapted ČEZ tooling
notices. Sources do not install themselves into a live HA instance.
