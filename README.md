# MND Tariff & Accounting for Home Assistant

Samostatná integrace plynu podle [úplného zadání](ZADANI_MND_SOL_6_1.md).
Runtime je Python, přibalený frontend JavaScript bez externí Lovelace
závislosti. Nepotřebuje WPF, WebView2 ani REST token k vlastnímu HA.

**Stav: vývojová verze 0.1.0.** Jednotkové testy nepotvrzují funkci na
zákaznickém účtu. Přesný stav a omezení jsou v [reportu](IMPLEMENTACE.md).
Cílový veřejný repozitář uvedený v manifestu ještě není publikací projektu.

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

Před provozním použitím musí projít Quality, HACS, Hassfest, skutečná HA
lifecycle matice a samostatná oprávněná živá kontrola. Testovací minimum
je **HA 2026.3.1** s přesně odpovídajícím pluginem 0.13.317. Metadata tohoto
páru nenahrazují provedené testy. Pro původně navržené 2026.3.0 přesný plugin
nebyl nalezen, proto bylo minimum zvýšeno.

Po schválené instalaci patří celý adresář `custom_components/mnd_tariff_accounting/`
do konfigurace HA. V **Nastavení → Zařízení a služby → Přidat integraci → MND**
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

Independent community Home Assistant gas accounting integration. It imports
MND XLSX and the C# v1 archive, keeps auditable readings, tariffs, actual
payments, invoices and historical forecast snapshots, and provides a bundled
panel and an Overview dashboard generator.

Development version 0.1.0 is not a verified production release. Live MND
validation and the Linux HA compatibility matrix are pending; see
`IMPLEMENTACE.md`. The minimum test target is HA 2026.3.1.

Unknown values remain distinct from zero, planned advances from actual
payments, and forecasts from confirmed invoices. Credentials, private
documents and real customer data are excluded from source control,
diagnostics and the installer. The MIT license preserves adapted ČEZ tooling
notices. Sources do not install themselves into a live HA instance.
