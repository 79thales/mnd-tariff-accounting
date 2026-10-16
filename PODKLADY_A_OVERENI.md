# Podklady a stav ověření

Připraveno 15. 10. 2026 pro implementaci v samostatném projektu. Žádné zde uvedené starší ověření nenahrazuje test nové integrace Home Assistantu.

## Umístění a stav projektů

| Úloha | Ověřená cesta / stav |
| --- | --- |
| Budoucí integrace | `H:\01.programovani\MND Tariff & Accounting for Home Assistant\`; před přípravou prázdný adresář bez Gitu |
| Codex projekt | Již existující **MND Tariff & Accounting for Home Assistant**, stejná H: cesta; nebyl založen nový chat ani zahájeno programování |
| Funkční C# MND | `H:\01.programovani\webdownloader\`; čistý pracovní strom při kontrole |
| C# revize | `96eee20f3237415ce72b75fd7de9b08f91ea8dce` — Přidání WebDownloaderu s podporou Moje MND |
| C# GitHub | Soukromý [79thales/webdownloader](https://github.com/79thales/webdownloader); při přípravě beze změny |
| Reference ČEZ | `H:\01.programovani\cez-dynamic-tariff\`; HEAD `c72633765fd2fa0de150fc70775735eefe053b1b`, pracovní strom obsahuje změny |
| ČEZ GitHub | Veřejný [79thales/cez-dynamic-tariff](https://github.com/79thales/cez-dynamic-tariff), `master_HA` |

Pro kontrolu, zda se reference od přípravy změnila, slouží [otisky vybraných souborů](REFERENCNI_OTISKY.md). Není to kopie zdrojů ani nová Git historie. Otisky jsou pořízeny z pracovních stromů, tedy zahrnují i zjištěné lokální změny ČEZ.

## Co dokládá reference C#

Zdroj: [MND_VALIDATION.md](H:/01.programovani/webdownloader/docs/MND_VALIDATION.md).

- Doložené sestavení C# a 27 jednotkových testů MND, 5 testů stávající EDC části a řízený WPF/WebView2 test. Při tvorbě tohoto zadání se znovu nespouštěly.
- Dřívější jednorázový živý test ověřil přihlášení, identitu/technické údaje místa, dva exporty odečtů a odhlášení. Dokládá funkci desktopového transportu, ne přímého Linux HTTP klienta.
- Samostatné prohlížečové čtení doložilo tři číselné části současného grafu: spotřebu podle odečtů, odhad minulosti a odhad budoucnosti. Nejsou získané měřením výšky sloupce.
- Úplnost historie před nejstarším získaným obdobím zůstává neověřená. Platby, zákaznický profil a smluvní PDF nebyly součástí živého C# testu.
- Po doplnění automatického načítání tooltipů byl proveden řízený test; další živé otevření tooltipů C# adaptérem nebylo potvrzeno.
- Konkrétní skutečný HA senzor a jeho historie nebyly v referenčním testu dodány. Živá kalibrace a návaznost se teprve ověří při implementaci.

Skutečné EIC, čísla měřidel, zákaznické hodnoty a originály zde nejsou opakovány. Zůstávají v soukromé referenci a nejsou určeny pro veřejné fixtures ani výchozí dashboard.

## Co bylo ověřeno při přípravě tohoto zadání

- Načteny aktuální místní dokumenty a klíčové modely/služby modulu MND, inventura testů a skutečných cest.
- Načteny účetní a dashboard dokumenty ČEZ, workflow CI/release, licence, balicí pravidla, Git stav a metadata GitHubu. Rozdíl HEAD/pracovní strom je výslovně zaznamenán.
- GitHub rulesets ČEZ: 0; ochrana `master_HA`: API odpověď „Branch not protected“. Žádný nový povinný PR režim nebyl domyšlen.
- Ověřeno existující umístění cílového Codex projektu. Nástroje přímého HA konektoru byly prohlédnuty; pro sepsání zadání nebylo potřeba měnit nebo číst osobní živý dashboard.
- Zkontrolována aktuální oficiální dokumentace HACS/HA, zejména balení, soukromé repozitáře, lokální brand assets a aktuální stable.
- Vytvořen pouze návrh loga a dokumentace. Není vytvořen `custom_components`, Git, commit, remote, tag, release ani instalace v HA.

## Vnější zdroje a jejich význam

| Zdroj ověřený 15. 10. 2026 | Použití v zadání |
| --- | --- |
| [HACS — integrace](https://www.hacs.xyz/docs/publish/integration/) | Jedna integrace, runtime v integračním adresáři, manifest a brand |
| [HACS — private repositories](https://www.hacs.xyz/docs/faq/private_repositories/) | Standardní HACS nedokáže použít soukromý repozitář |
| [HA — koordinované načítání](https://developers.home-assistant.io/docs/integration_fetching_data/) | Sdílená aktualizace dat a asynchronní klient |
| [HA — senzory](https://developers.home-assistant.io/docs/core/entity/sensor/) | Správný význam jednotek a tříd senzorů, žádné I/O v properties |
| [HA — brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/) | Lokální `brand/` u custom integrace je podporován od HA 2026.3 |
| [HA — vydání 2026.10](https://www.home-assistant.io/blog/2026/10/07/release-202610/) | Při přípravě stránka uváděla stabilní 2026.10.1; při implementaci znovu zjistit aktuální stable |

Požadavky na intervaly, prioritu odečtů, účetní knihu a dashboard vycházejí z uživatelského zadání a místních referencí. Navržené časování nového portálového klienta není doloženým limitem MND. Dostupnost přímé autentizace, přesná podoba API a podporované fakturační formáty jsou výslovné úkoly první implementační etapy.
