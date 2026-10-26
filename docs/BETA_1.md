# První beta — 0.1.0-beta.1

Uživatel 26. 10. 2026 požádal o přechod ze stavu alpha na beta a zveřejnění
v HACS. Beta.1 přebírá runtime ověřené alpha.5; funkční kód se při změně
stavu nemění. Nové číslo má vlastní neměnný tag a samostatný instalátor.
Původní tagy a instalační přílohy zůstávají zachované.

## Co je nové oproti veřejné alpha.4

- Volitelné měření elektrického příkonu a kumulativní energie kotle pro
  jednotlivá odběrná místa, včetně náhledu zdrojů v administraci.
- Jednodušší hlavní přehled: právě teď, spotřeba a vyúčtování; podrobné
  grafy zůstávají v detailu Spotřeba a účetní přehledy v Účetnictví.
- Živé metriky, provozní historie a elektrické souhrny s přiznaným pokrytím.
- Stejná kompozice 4 v generátoru a přibalené šabloně, zachované navigace.
- Český úvod HACS ve stejném členění jako ČEZ: odznaky, značka, novinky,
  popis integrace, požadavky, funkce a postup instalace.

## Aktualizace

V HACS obnovte informace repozitáře, povolte beta verze a vyberte
`v0.1.0-beta.1`. Po instalaci restartujte Home Assistant a obnovte prohlížeč.
V konfiguraci příslušného zařízení MND lze zapnout elektrické měření kotle
a vybrat zdroj příkonu a případně kumulativní energie. Zásuvku ani termostat
tato funkce neovládá. Elektřina je oddělená od plynu a účetnictví MND.

Před aktualizací uloženého dashboardu stáhněte zálohu Overview a zkontrolujte
náhled generátoru. Instalace souborů sama existující dashboard nepřepíše.

## Ověření a omezení

Funkční podklady, přesné testované dvojice HA a výsledky živého ověření
jsou v [reportu alpha.5](ALPHA_5.md). Nejde o náhradu kontrol nového beta tagu:
release workflow pro něj samostatně ověřuje Quality, HACS a Hassfest
a teprve po úspěchu vytvoří draft s instalátorem z daného tagu.

Označení beta neznamená dokončené mobilní vizuální ověření ani plné
automatické převzetí všech smluvních cen. Informativní požadavek termostatu
nemá samostatné hodnocení stáří a není důkazem hoření. Neznámé údaje nejsou
nuly; elektrické souhrny zahrnují pouze doložené uzavřené hodiny.
Podrobnosti: [Kotel a přehled](KOTEL_A_PREHLED.md).
