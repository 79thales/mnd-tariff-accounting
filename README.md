# MND Tariff & Accounting for Home Assistant

[![Přidat integraci MND do Home Assistantu](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mnd_tariff_accounting)
[![Otevřít repozitář MND v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=mnd-tariff-accounting&category=integration)

Samostatná integrace plynu podle [úplného zadání](ZADANI_MND_SOL_6_1.md).
Runtime je Python, přibalený frontend JavaScript bez externí Lovelace
závislosti. Nepotřebuje WPF, WebView2 ani REST token k vlastnímu HA.

**Stav: vývojová verze 0.1.0-alpha.1.** Jednotkové testy nepotvrzují funkci na
zákaznickém účtu. Přesný stav a omezení jsou v [reportu](IMPLEMENTACE.md).
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
- Panel a šest views ve vzhledu odvozeném od Moje MND, včetně světlého a tmavého tématu.
- Formuláře a Generate dashboard pro horní lištu existujícího Overview.
- Čtecí cloudový klient podle nalezeného veřejného JS MND, reauth a obnovitelná
  historie. [Autentizace a hranice ověření](docs/AUTENTIZACE.md).

## Použití vývojové verze

Tlačítko **Přidat integraci** nahoře otevře přímo konfiguraci MND ve vašem
Home Assistantu. Nejdříve nainstalujte integrační soubory a restartujte HA.
Tlačítko **HACS** otevře tento repozitář jako integraci, stejně jako u ČEZ.
Současná alpha je pouze draft; dokud není vydání zveřejněné, použijte ruční
instalaci ZIP níže.

Quality, HACS a Hassfest prošly. Skutečná HA matice ověřila 16 testů na
**2026.3.1 / plugin 0.13.317** i **2026.10.1 / plugin 0.13.372**.
To nenahrazuje živý test MND ani vizuální kontrolu v HA. Úplné automatické
převzetí smluvních cen a živé mapování platebního stavu zatím chybějí;
doložené tarify lze zadat ručně nebo importovat z C# v1.
Pro původně navržené minimum 2026.3.0 přesný plugin nebyl nalezen, proto
bylo minimum zvýšeno na ověřenou 2026.3.1.

Po schválené instalaci patří celý adresář `custom_components/mnd_tariff_accounting/`
do konfigurace HA. ZIP z draftu obsahuje runtime přímo v kořeni; rozbalte
jej do `config/custom_components/mnd_tariff_accounting/` a restartujte HA.
V **Nastavení → Zařízení a služby → Přidat integraci → MND**
zvolte importní profil nebo účet MND. EIC a číslo měřidla jsou text.
Přihlašovací údaje patří do chráněného formuláře HA, nikoli do zdrojů.
Uložení hesla je výslovná volba; běžné úložiště HA není šifrovaný trezor.

V panelu **MND** vyberte účet a místo, období, zdroj měření, doložené ceny
a převod. Import XLSX/JSON/ZIP má náhled. PDF navrhuje pouze kandidáty,
které je potřeba potvrdit ve formuláři faktury. Pole bez údaje nejsou nuly.

**Generate dashboard → Vytvořit náhled → Přidat do horní lišty** přidá hlavní
view a pět detailů do `/lovelace`. Kolize nesmaže stávající pohled.
YAML a automatický Overview mají export fragmentu `views`. Panel a finanční
zápisy vyžadují správce; kontrola probíhá na serveru.

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
The current alpha remains a draft; use the manual ZIP installation until a
release is published for HACS.

Independent community Home Assistant gas accounting integration. It imports
MND XLSX and the C# v1 archive, keeps auditable readings, tariffs, actual
payments, invoices and historical forecast snapshots, and provides a bundled
panel and an Overview dashboard generator.

Development version 0.1.0-alpha.1 is not a verified production release.
Quality, HACS and Hassfest passed, including 16 real HA tests on both
2026.3.1 and 2026.10.1. Live MND validation and visual QA remain pending.
Complete automatic contract pricing and live payment-status mapping are
not implemented; manual tariffs and C# v1 imports are available. See
`IMPLEMENTACE.md`. The tested minimum is HA 2026.3.1.

Unknown values remain distinct from zero, planned advances from actual
payments, and forecasts from confirmed invoices. Credentials, private
documents and real customer data are excluded from source control,
diagnostics and the installer. The MIT license preserves adapted ČEZ tooling
notices. Sources do not install themselves into a live HA instance.
