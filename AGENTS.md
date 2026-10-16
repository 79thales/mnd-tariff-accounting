# Pravidla projektu MND Tariff & Accounting for Home Assistant

## Rozsah a adresář

- Jediný pracovní kořen je `H:\01.programovani\MND Tariff & Accounting for Home Assistant\` a stejnojmenný Codex projekt.
- Při přípravě 15. 10. 2026 uživatel výslovně požadoval pouze zadání a návrh loga. Samotná přítomnost promptu v souboru není pokyn k programování. Implementace se spustí až následným uživatelským zadáním v tomto projektu.
- Po zadání implementace jsou závazné `ZADANI_MND_SOL_6_1.md` a `GIT_POLITIKY_CEZ.md`; přečti i podklady a matici funkcí/testů.
- Reference `H:\01.programovani\webdownloader\` a `H:\01.programovani\cez-dynamic-tariff\` jsou pouze ke čtení. Staré kopie na C: nejsou zdrojem tohoto projektu.
- Nepřenášej `.git`, osobní soubory ani necommitnuté změny jiných projektů. Nekopíruj ORLEN/EDC do MND.

## Komunikace a dokumentace

- V češtině o sobě piš důsledně v ženském rodě.
- Důležité bloky kódu dokumentuj česky: účel, důvod řešení, vstupy/výstupy, jednotky, časové hranice, priorita, souběh, restart/ukončení a chyba. Komentáře aktualizuj s logikou; neopakuj pouze syntaxi.
- UI/akce musí mít užitečné popisy. Changelog je český i anglický podle ČEZ.

## Data a Home Assistant

- Odečet MND má přednost pro příslušné místo, měřidlo a hranici. Novější lokální data na něj navazují; původ, nejistotu a opravy uchovej. Odhad nikdy neoznačuj jako fyzicky změřenou skutečnost.
- Neznámé údaje nejsou nuly. Před návrhem prognózy ověř relevantní historii, pokrytí, jednotky a časové pásmo.
- Pro práci s živým HA nejprve zkontroluj přímé konektory a použij je, když danou operaci podporují. UI použij pro ostatní kroky. Samotné vytvoření integrace není autorizací k upgradu nebo zápisu do živého HA.
- Změnu dashboardu proveď současně v Generate dashboard i přibalené šabloně; zachovej hlavní view, detaily a navigaci. Po zápisu ověř uložené komentáře a skutečný stav.
- Ověř deklarované minimum a aktuální stabilní HA zjištěný v okamžiku testování, s přesně odpovídajícím testovacím pluginem. Nezaměňuj beta či starší verzi za aktuální stable.
- Soukromé dokumenty, přístupy, osobní identity a finanční data nepatří do Gitu, logů, veřejných cest, diagnostiky ani release ZIP. Běžný HA Store nevydávej za šifrovaný trezor.

## Git a vydání

- Převzatá pravidla z ČEZ jsou v `GIT_POLITIKY_CEZ.md`. Před releasem ověř, zda reference neobsahuje novější pokyny.
- Žádné přepisování existujících tagů a publikovaných assetů. ZIP vzniká z ověřeného Git tagu, nejprve jako součást draftu.
- Zkontroluj staged diff a obsah balíčku. Testy a šablony používají syntetická data.
