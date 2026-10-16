# Technický návrh a stav ověření

Implementace byla zahájena 16. 10. 2026 na výslovný pokyn „Programuj“.
Jediný pracovní kořen je tento projekt. Reference C# a ČEZ se pouze čtou.

Jádro `core/` neimportuje HA ani síťové knihovny. Obsahuje importní kontrakt,
bezpečný parser XLSX, měřicí body a jejich revize, návaznost senzoru,
cenové intervaly, účetní události, faktury a uložené prognózy. Desetinné vstupy a výstupy používají Decimal; měnový mezisoučet a časové
poměry Fraction pro zachování přesné poloviny haléře; interní export ukládá desetinná čísla
jako řetězce. Import C# v1 zachovává původní PascalCase i zdrojové výsledky.

Adaptér HA používá samostatný Store pro config entry, transakční zápisy
a nativní registry entit. Zápis do veřejných statistik zdroje není potřebný.
Frontend nabízí přehled a formuláře přes autentizované rozhraní; správce
vidí náhled přidání hlavního view a detailních subviews do Overview.
Generátor i šablona mají společný zdroj složení.

## Přenos MND

C# reference používá WebView2 a DOM, nikoli doložený HTTP API klient.
Veřejné HTML a JS byly následně získány samostatným pouze čtecím
průzkumem. Doloženy jsou přihlašovací payload, autorizační hlavička, čtecí
endpointy, exportní payload a stahování GUID. Přesná evidence a hranice
živého ověření jsou v AUTENTIZACE.md. Přihlášení z prostředí HA, obnova
relace, MFA a limity zůstávají předmětem oprávněného živého ověření.
Do HA se neinstaluje browser runtime.
Import má vlastní funkční cestu, ale nenahrazuje cloudové M01–M08.

## Reference a testování

Pracovní strom ČEZ obsahuje necommitnuté opravy; nebyl upraven. C# pracovní
strom byl při úvodní kontrole čistý. Dostupný Python je 3.12.14; minimum
HA 2026.3.1 i aktuální stable 2026.10.1 vyžadují samostatně odpovídající prostředí.
Lokální unit testy nenahrazují lifecycle; následné skutečné Linux CI již
ověřilo 16 HA testů na obou přesných párech HA/plugin. Tím není ověřen
zákaznický cloudový účet ani vizuální frontend v prohlížeči.
Stav testů a všech požadavků je v IMPLEMENTACE.md; neprovedené kontroly
zůstávají výslovně neověřené.
