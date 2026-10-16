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

## Dodatečné ověření vydaného balíčku

Po zveřejnění neměnného tagu `v0.1.0-alpha.3` dne 16. 10. 2026 proběhlo
anonymní stažení a porovnání s draftem i lokálním sestavením z téhož tagu:
157 236 bajtů, 45 runtime souborů, SHA-256
`be56045d9ca387de04a3d2c0f0dfa83892f265fb3cf5fe4df7e28ad3fa9d289c`.
Quality, HACS, Hassfest a release workflow prošly. Ověřeno 114 Python testů,
24 Node testů a po 20 integračních testech na HA 2026.3.1/plugin 0.13.317
a HA 2026.10.1/plugin 0.13.372, s Pythonem 3.14 v HA matici.

Schválené nasazení přes HACS a restart potvrdily runtime alpha.3 v HA
2026.10.1. Živě prošly oba finanční Exporty i stažení konkrétního PDF
vyúčtování, včetně porovnání SHA-256 uloženého originálu. Finanční seznamy,
detaily a platby byly načtené bez zdrojové chyby; původní odečty a místní
účetní záznamy zůstaly zachované. Pět detailních subviews a hlavní MND view
odpovídají generátoru a šabloně, ostatní Overview se obsahově nezměnilo.
Statické JS poskytované HA přesně odpovídá ověřenému vydanému zdroji.

Potvrzený pár senzorů byl připojen, průtok je dostupný. Souběžná kalibrace
plynoměru a účetní období tohoto místa dosud nejsou nastavené; ověření
čtecích finančních podkladů není potvrzením úplného účetního výsledku.
V historii jsou mezery. Žádné chybějící měření ani platba se nedoplnily nulou.
Mobilní vizuální test na skutečném iPhonu nebyl proveden; ověření konfigurace
a DOM testy za něj nejsou vydávány. Soukromé protokoly, hodnoty a soubory
zůstávají mimo Git a mimo instalační ZIP.
