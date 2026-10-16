# Vzhled odvozený od Moje MND

Uživatelka požadovala 16. 10. 2026 podobný nebo výrazně odvozený vzhled MND.
Panel, generátor, jeho náhled a všech šest generovaných views proto používají
jedinou vlastní komponentu `mnd-accounting-card` a společné CSS v `mnd-panel.js`.
Složení generátoru pochází výhradně z `dashboard_template.json`.

Předloha byla ověřena na veřejné přihlašovací stránce
[Moje MND](https://moje.mnd.cz/login) a jejím
[veřejném CSS](https://moje.mnd.cz/_next/static/css/ebc21b051b544749.css).
Ověření nevyžadovalo přihlášení ani zákaznické údaje. Hashované adresy se mohou
s vydáním portálu změnit; nejde o runtime závislost integrace.

| Prvek | Odvození a vlastní provedení |
| --- | --- |
| Hlavní barva | Zelená `#2b6e33`; tmavší stav tlačítka `#1b5c22` |
| Akcent | Limetková `#a8be32`, podtržení aktivní záložky, třetí skupina karet |
| Záhlaví | Zelený přechod s limetkovým akcentem; bílé titulky jsou na tmavší části |
| Text a ohraničení | `#2e332e`, doprovodný text `#545c58`, linky `#c0d1c0` |
| Typografie | Místní Avenir / Avenir Next, náhradně Arial; bez přibalení cizího fontu |
| Karty a formuláře | Bílé plochy, jemné linky, poloměr 8 px, výrazná čísla, střídmé stíny |
| Graf | Měření zeleně, minulý odhad limetkově, budoucí odhad prázdně s přerušovaným okrajem |

Nejde o stažený stylesheet ani oficiální aplikaci MND. Přibalený kód je vlastní,
bez cizích fontů, sledování a vzdálených obrázků. Označení komunitní integrace je
v patičce. Stavy, doklady a částky vycházejí z archivu vybraného místa.

Tmavý režim se řídí `hass.themes.darkMode`, ne režimem operačního systému.
Přizpůsobuje plochy, texty, graf i focus; značková zelená zůstává na tlačítkách
a záhlaví. Na malém displeji se karty skládají a navigace vodorovně posouvá.
Ovládání má viditelný focus a respektuje omezení pohybu. Přístup k detailu entity
funguje přes skutečné registry ID přeložené na aktuální entity ID v generátoru.

DOM testy ověřují skutečné vykreslení, neznámé hodnoty, odkazy, formuláře a
oddělení účtů. Nenahrazují vizuální kontrolu v běžícím HA. V tomto prostředí
nebyl dostupný prohlížeč CUA; vizuální kontrola v HA zůstává otevřená.
