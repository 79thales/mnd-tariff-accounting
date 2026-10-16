# MND 0.1.0-alpha.3 — společné stahování dokumentů

Při nasazení alpha.2 do HA 2026.10.1 se úspěšně načetly finanční seznamy
a jejich detaily; původní odečty a místní účetní evidence zůstaly zachované.
Aktualizace šesti existujících MND views zachovala ostatní pohledy Overview.
Test skutečného Exportu ale skončil HTTP 404 při stažení vytvořeného souboru.

Veřejný klient Moje MND používá pro `Documents/GetByGuid` axios klient ZP,
jehož báze je `/api`. Předchozí implementace použila `/data`; samotné vytvoření
exportu a načtení finančních přehledů tím nebyly důkazem úspěšného stažení.
Alpha.3 sjednocuje stahování všech generovaných dokumentů a smluvních PDF
do jediné metody s cestou `/api/Documents/GetByGuid`. GUID pochází z ověřené
předchozí odpovědi nebo ověřeného seznamu dokumentů. Token se do URL ani
stahovacího požadavku nepřenáší. Název a binární podpis se dále kontrolují;
soubory zůstávají v soukromém úložišti.

Regrese ověřuje přesnou cestu, předání GUID a chybějící hlavičku Inatoken
u exportu odečtů, záloh, PDF faktury a smluvního dokumentu. Po vydání se musí
znovu ověřit skutečný Export záloh, Export přehledu faktur a stažení PDF,
nikoli pouze HTTP úspěch seznamu nebo syntetická odpověď.

Rozvržení, konfigurace místa a migrace zůstávají popsané v [alpha.2](ALPHA_2.md).
Nové grafy podle dodaných snímků ČEZ a loňské/topné/netopné srovnání jsou
v oddílu 3.4 [zadání úprav](../ZADANI_UPRAV_MND_SOL_6_1_2026-10-16.md).
Nejde o součást této opravné verze. Přesné senzorové napojení a dostupná
historie se ověřují soukromě v daném HA; zákaznické hodnoty nepatří do zdrojů.

Zdroj datového kontraktu: [veřejný klient Moje MND](https://moje.mnd.cz/_next/static/chunks/pages/_app-d4693e13afff6e1f.js),
modul 22856 (konfigurace bází) a metody Documents/GetByGuid, AdvanceExport,
InvoiceExport a InvoicePdf. Kontrola provedena 16. 10. 2026.
