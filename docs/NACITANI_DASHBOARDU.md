# Obnova karty po opožděném načtení

Panelové pohledy MND používají jednu nativní kartu `vertical-stack`, jejímž
jediným potomkem je `custom:mnd-accounting-card`. Nativní stack vytváří
`hui-card`; ten umí obnovit obsah po pozdější registraci vlastního elementu.
Přímá vlastní karta v panelu může při souběhu načítání modulů zůstat na
„Chybě nastavení“ až do dalšího načtení stránky. Tento mechanismus popisuje
[hlášení frontend #52570](https://github.com/home-assistant/frontend/issues/52570)
a [implementace nativního stacku](https://github.com/home-assistant/frontend/blob/dev/src/panels/lovelace/cards/hui-stack-card.ts).

Obal zachovává panelovou šířku, hlavní pohled, detailní podstránky, entity
a navigaci. Nepřidává dotazy na účetní data, časovače ani zápisy do evidence.
Pokud modul skutečně chybí nebo obsahuje chybu, obal tuto příčinu neopraví.
Občasné zotavení po znovunačtení je stopa souběhu, nikoli jeho přímý důkaz.

## Chybějící registrace vlastního elementu

Mobilní editor následně doložil `Custom element doesn't exist:
mnd-accounting-card`. Živý HTTP test vrátil pro modul stav 200,
`text/javascript` a registraci této karty; kontrola syntaxe Node prošla.
To dokládá dostupnost souboru ze sítě počítače, nikoli jeho stažení a
vykonání v telefonu. Samotné obalení dashboardu tuto chybu neodstranilo.

Setup nově eviduje přesnou hashovanou URL také v Lovelace resources jako
`module`. Při opakování nevytváří další záznam, při aktualizaci změní
vlastní URL a typ; cizí zdroje zachová. YAML režim pouze vypíše pokyn do
logu. Stávající instalaci lze opravit přidáním jednoho zdroje v UI:
`/mnd_tariff_accounting/mnd-panel.js`, typ **JavaScript module**. Je-li
již záznam přítomen, nejprve ověřit jeho URL a typ a nevytvářet duplikát.
Nový setup vyžaduje následnou instalaci změněného kódu; tato dokumentace
nepotvrzuje, že byl tento kód nasazen nebo že se karta v telefonu načetla.

Živé ověření 1. 11. 2026: v registru Lovelace zdroj MND chyběl. Po výslovné
autorizaci byl přes API přidán jediný zdroj typu `module` s hashovanou URL
stávajícího souboru a následným čtením ověřen. Uživatel potvrdil funkční
zobrazení na telefonu. Automatický setup je součástí nynější změny zdrojů
integrace; ruční oprava registru sama tuto novou verzi nenainstalovala.

Ověření změny: 184 Python testů, 53 Node testů, Ruff, kompilace Pythonu
a kontrola diffu prošly. Asynchronní Python testy vyžadovaly spuštění mimo
omezený sandbox; tam skončily úspěšně. Aktuální metadata PyPI při kontrole
určila stable HA 2026.10.4 / plugin 0.13.375 / Python 3.14; minimum v CI je
HA 2026.3.1 / plugin 0.13.317. V obou verzích zdroj HA obsahuje použité
rozhraní zdrojů. Nové skutečné HA testy kontrolují storage registraci,
opakování, aktualizaci hashované URL a nedotčený YAML režim. Místní WSL
nemá žádnou distribuci a není dostupný Docker; obě skutečná prostředí HA
proto ověřilo [Quality nad opravou rc.2](https://github.com/79thales/mnd-tariff-accounting/actions/runs/41308645949).
Prošly také [HACS](https://github.com/79thales/mnd-tariff-accounting/actions/runs/41308645691)
a [Hassfest](https://github.com/79thales/mnd-tariff-accounting/actions/runs/41308645701).

Generátor používá přibalenou JSON šablonu. Náhled rozbalí jediného potomka
obalu a aktualizace umí převést starší přímou kartu i opakovaně aktualizovat
obalenou kartu. Zachová místní entity a cizí sousední karty; složený obal s
více potomky odmítne jako nejednoznačnou kolizi. Pro tyto cesty jsou regresní
testy v `tests/dashboard.test.js` a `tests/frontend.test.js`.

Změnu již existujícího dashboardu lze provést samostatně bez instalace nové
verze integrace: ve všech šesti vlastních MND pohledech obalit stávající
pole `cards` do jediného `vertical-stack`. Před zápisem vytvořit zálohu,
ověřit původní otisk a po zápisu ověřit celý výsledný otisk. Úpravy generátoru
se do instalované integrace dostanou až následnou aktualizací jejího kódu.

### English

Wrap each MND panel card in a native vertical stack so Home Assistant can
recover when the custom element registers late. The generator, bundled
template, preview and update logic share this structure. Existing dashboards
can receive the wrapper independently of an integration upgrade. A missing
or broken module still needs its own repair; live mobile rendering requires
separate verification.
