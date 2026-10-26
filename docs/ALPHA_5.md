# Alpha.5 — měření kotle a jednodušší přehled

Průběžný report přípravy 26. 10. 2026. Verze manifestu a připravených notes
je `0.1.0-alpha.5`. V okamžiku založení tohoto reportu nebyl vytvořen nový
commit, tag, draft ani instalační ZIP a změna nebyla nasazena do živého HA.
Výsledky závěrečného CI a živého ověření se doplní až po jejich provedení.

## Rozsah

- Volitelné čtecí měření elektrického příkonu kotle pro každé odběrné místo.
  Administrace nabízí výběr W/kW, volitelné kumulativní Wh/kWh a požadavku
  topení; před uložením ukazuje náhled a dostupnost zvolených zdrojů.
- Elektřina kotle zůstává oddělená od plynu, cenových úseků a vyúčtování MND.
  Požadavek termostatu ani samotný elektrický příkon není důkaz plamene.
  Tato úprava nemění ovládání kotle, napájení zásuvky ani teplotní program.
- Hlavní přehled obsahuje právě teď, spotřebu a výhled vyúčtování s nejvýše
  jedním sedmidenním grafem. Provozní a měsíční grafy jsou v podrobnostech
  Spotřeba, finanční tabulky a graf zůstávají v Účetnictví.
- Živé hodnoty nevyžadují nové načtení celé karty a zachovávají fokus i
  rozepsané formuláře. Nula, zastaralý report a chybějící údaje jsou odlišné.
- Generátor a přibalená šablona používají kompozici 4, zachovávají hlavní
  pohled, pět subviews, navigaci a zpětné cesty. Konkrétní domácí entity
  nejsou součástí distribuované šablony.

Význam jednotek, pokrytí, časování, souběhu a restartu podrobně popisuje
[Kotel a přehled](KOTEL_A_PREHLED.md).

## Ověření a co zatím není dokončené

| Oblast | Stav při založení reportu |
| --- | --- |
| Doménové testy a validace | 148 testů prošlo; Ruff a compileall bez chyb |
| Frontend a navigace | 40 Node testů prošlo; desktopový syntetický náhled ověřen. Mobilní viewport nebyl prohlížečem skutečně přepnut, proto mobilní vizuální ověření zatím není doložené |
| HA minimum | Nutné nové skutečné Linux testy HA 2026.3.1 / plugin 0.13.317 |
| Aktuální stable | Resolver 26. 10. určil HA 2026.10.4 / plugin 0.13.375 / Python 3.14; běh nového kódu je nutné dokončit |
| Quality, HACS, Hassfest | Nová revize ještě nemá doložené dokončené CI |
| Tag a instalační ZIP | Zatím nevytvořeno; pouze budoucí neměnný tag a build z Git stromu |
| Záloha a živé nasazení | Uživatel autorizoval; zatím neprovedeno v rámci alpha.5 |

Předchozí úspěšné testy alpha.4 nejsou důkazem kompatibility nových změn.
Místní Windows prostředí bez dostupné distribuce WSL nenahrazuje skutečný
Linux běh HA. Dostupné GitHub Actions obsahují přesné minimum i dynamicky
ověřovaný stable a dovolují provést požadované testy na novém commitu.

## Vydání a návrat

Před přípravou metadat byly ověřeny místní tagy a GitHub release alpha.1 až
alpha.4; vzdálený tag `v0.1.0-alpha.5` tehdy neexistoval. Před jeho vytvořením
se kontrola provede znovu. Starší tagy, release a assety se nemění.

Po kontrole diffu a úspěšném Quality/HACS/Hassfest následuje nový tag,
reprodukovatelný ZIP a nejprve draft se správným assetem. Publikace a živé
nasazení jsou další ověřené kroky. Balík nesmí vzniknout z pracovního adresáře
ani obsahovat soukromé exporty, identity či přístupy.

Před nasazením se uloží aktuální privátní MND archiv včetně dokladů, konfigurace
Overview a kopie současného integračního adresáře. Výchozí místní kořen je
`H:\01.programovani\04.HA\mnd-backups\`; konkrétní časová složka a hashe se
zaznamenají pouze do soukromého protokolu. Nasazení nesmí přepsat účetní
archiv ani `.storage` relace. Návrat používá zálohovaný runtime a uložený
dashboard při zachování novějších měřených dat.

Backendové Python moduly a jednorázová registrace statického frontendu
vyžadují po výměně runtime plné znovunačtení HA Core; samotný reload
ConfigEntry není dokladem načtení nové verze. Nejde o upgrade HA ani restart
hostitelského systému. Po restartu se cíleně ověří verze, dostupnost místa,
zdroje kotle, průtok, čerstvost, souhrny a zachování účetních podkladů.
