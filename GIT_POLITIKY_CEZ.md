# Git a vydávání MND — převzetí pravidel projektu ČEZ

Datum auditu: 15. 10. 2026. Tento dokument je zadání budoucího postupu, ne potvrzení provedeného založení/publikace repozitáře.

## Ověřená reference

- Zdroj: `H:\01.programovani\cez-dynamic-tariff\`.
- Vzdálený repozitář: [79thales/cez-dynamic-tariff](https://github.com/79thales/cez-dynamic-tariff), při kontrole **PUBLIC**.
- Lokální i vzdálená výchozí větev: **master_HA**.
- HEAD: `c72633765fd2fa0de150fc70775735eefe053b1b`.
- Pracovní strom obsahuje necommitnuté úpravy a nové soubory. Zejména návrh odolnosti účetnictví a aktuální dashboard se musí posuzovat i podle pracovního stromu, ne jen podle HEAD. Referenční změny nesmějí být přepsány ani commitnuty při práci na MND.
- GitHub API v okamžiku kontroly vrátilo **0 rulesets**. Pro `master_HA` vrátilo „Branch not protected“ (HTTP 404).
- Projektový `AGENTS.md` stanovuje pouze správný adresář H:. Pravidla vydávání jsou zejména ve `scripts/README.md`, balicích skriptech a `.github/workflows/`.
- Licence ČEZ: **MIT**, copyright 2026 79thales. Při převzetí kódu zachovat oznámení a licenci; nepřebírat zákaznická data.

Audit popisuje dostupné podklady. Nenašla se pravidla povinného PR, konkrétního počtu reviewerů, povinných podepsaných commitů ani zvláštní commit konvence. Neprezentuj je jako existující politiku ČEZ a neinstaluj nové restrikce pod záminkou převzetí. Před budoucím založením/releasem znovu ověř aktuální referenci; změněné pokyny uživatele mají přednost.

## Závazná mapa pravidel

| Pravidlo ověřené v ČEZ | Použití v MND |
| --- | --- |
| Samostatný veřejný HACS repozitář, výchozí `master_HA` | Vlastní Git pro MND ve správném H: adresáři, samostatný remote a stejná výchozí větev. Navržený slug `mnd-tariff-accounting`; nevytvářet kopii historie nebo remote ČEZ. |
| Soukromé exporty, finanční zálohy a cache nejsou zdroje | Ignorovat lokální úložiště, přístupy, originály XLSX/PDF, profil, screenshoty s daty, runtime logy, exporty a testovací prostředí. Před commitem zkontrolovat staged diff i nové binární soubory. |
| Jeden integrační adresář a instalační ZIP | `custom_components/mnd_tariff_accounting/`, ZIP `mnd_tariff_accounting.zip`; vše potřebné pro běh uvnitř integračního adresáře. |
| Sémantická verze manifestu odpovídá tagu | `vX.Y.Z` musí přesně odpovídat manifestu MND; nepřebírat číslo verze ČEZ jako verzi nového produktu. |
| Changelog pro každou vydávanou verzi česky a anglicky | Zachovat oddíly `### Čeština` a `### English`; release notes se berou ze správného oddílu daného tagu. |
| Quality, HACS a Hassfest před vydáním | Neoznačit vydání za připravené při selhání nebo neprovedené požadované kontrole. |
| Build z Git stromu konkrétního commitu | Použít ekvivalent `git archive` nad integračním podstromem; žádné balení pracovního adresáře, necommitnutých oprav nebo soukromých souborů. |
| Runtime a release notes z požadovaného tagu | Nástroje balení mohou být z aktuálního workflow, ale musí ověřit obsah požadované revize, manifest a changelog. |
| Reprodukovatelný ZIP | Runtime soubory přímo v kořeni, normalizace textů LF, časy ZIP odvozené od UTC času commitu, kontrola obsahového manifestu. |
| Workflow na tag `v*` nebo ručně pro existující tag | Připraví otestovaný balíček a nejprve **draft release**. Automaticky nezveřejňuje release. |
| Publikovat až kompletní draft | Před publikací zkontrolovat notes, správný přiložený ZIP a úspěch workflow. Nikdy nejprve nezveřejnit prázdný release. |
| Již existující asset pouze ověřit | Neodstraňovat, nepřejmenovávat a nenahrávat nový obsah přes stejný asset; jeho download count se nesmí resetovat náhradou. |
| Zveřejněné release/asset jsou neměnné | Chybu řešit novou verzí. Chybějící instalátor zveřejněného releasu je chyba kontroly, ne důvod k tiché opravě published releasu. |
| Existující tagy se nepřepisují | Žádný force push tagu ani posouvání staré verze na nový commit. |
| Obsahová kontrola starších balíčků | Přípustná odchylka může být jen doložené ZIP metadata/CRLF; změněný soubor, chybějící soubor, poškozený ZIP či manifest musí kontrolu zastavit. |
| Zachování starších release a default branch instalace | Neměnit historické manifesty a balíčky. Podporovat jasně odlišenou instalaci z výchozí větve. |
| Download badges jen pro instalační asset | Filtrovat přesně `mnd_tariff_accounting.zip`; případné další přílohy nesmějí navyšovat údaj o instalátoru. Počet stažení není počet aktivních uživatelů. |
| Minimální oprávnění CI a oddělené psaní | Většina workflow pouze čte; `contents: write` pouze v jobu připravujícím draft. Zohlednit `persist-credentials: false` pro release checkout. |
| Release souběh podle tagu | Stejný release nevytvářej souběžně; jako v ČEZ nerušit probíhající vydávací úlohu novým startem. |
| Žádná telemetrie kvůli statistice instalací | Použít jen veřejné GitHub počty stažení instalátoru; integrace nic o zákazníkovi neodesílá. |

Nepřenášet zákaznické exporty z privátního WebDownloaderu do veřejného MND repozitáře ani jako fixtures. `gitignore` sám neodstraní soubor již sledovaný Gitem; vždy ověř skutečný index, diff a obsah ZIP. Ignore pravidla navrhnout tak, aby neblokovala záměrně syntetická testovací data, changelog, legitimní dokumentaci či produkční brand soubory.

## CI podle ČEZ

Převzít význam těchto workflow, přizpůsobit názvy/doménu/cesty a ověřit jejich aktuální verze, nikoli mechanicky kopírovat nesouvisející závislosti:

- `.github/workflows/quality.yaml`: push, pull request a ruční spuštění; kompilace Pythonu, Ruff, doménové testy s pokrytím, Node testy frontendu/release a skutečné testy HA lifecycle.
- `.github/workflows/hacs.yaml`: HACS validation pro integraci při push/PR, ručně a pravidelně.
- `.github/workflows/hassfest.yaml`: ověření manifestu, překladů a struktury HA.
- `.github/workflows/release.yml`: test a build z požadovaného tagu; uložení instalačního artefaktu a notes; samostatný job přípravy draftu nebo ověření již existujícího assetu. Reference uchovává mezilehlý artefakt 7 dní.
- `scripts/resolve_latest_ha.py`: zjistit nejnovější stabilní HA a nevyřazenou verzi `pytest-homeassistant-custom-component`, jejíž závislost přesně odpovídá tomuto HA. Nepoužívat slepě nejnovější plugin, může cílit beta.

Referenční resolver omezuje hledání na 25 stabilních verzí pluginu s timeoutem 20 sekund na požadavek. Nedostupná metadata či chybějící odpovídající plugin mají být jasná chyba CI. Starší připnuté testovací varianty zůstávají pro ochranu deklarované kompatibility; MND musí mít vlastní reálně ověřené minimum a aktuální stable. Původní matice ČEZ není důkazem kompatibility nové integrace.

## Co je pozorování a co rozhodnutí pro nový projekt

Veřejnost a název větve ČEZ byly ověřeny přes GitHub, pravidla vydávání pocházejí z místní dokumentace a workflow. Pro MND jsou zde výslovně převzaty na přání uživatele. Slug `mnd-tariff-accounting`, doména a název ZIP jsou nové konkrétní návrhy; jejich dostupnost se ověří před založením/publikací.

Dřívější požadavek na **private** se týkal WebDownloaderu. Ten zůstává soukromý a nemění se. HACS podle své [dokumentace soukromých repozitářů](https://www.hacs.xyz/docs/faq/private_repositories/) soukromé repozitáře nepodporuje. Pokud uživatel později výslovně změní viditelnost MND na private, vysvětli dopad na HACS a připrav odpovídající způsob distribuce; nepředstírej standardní instalaci private repozitáře přes HACS.

Zadání se nyní jen předává. Samotné uložení těchto dokumentů nevytváří remote, Git commit, tag, release, publikaci ani instalaci. Při budoucí implementaci se nejprve dokončí a ověří konkrétní změna; zveřejnění draftu je samostatný krok uvedený v procesu ČEZ.

## Přímé místní zdroje

- [Pravidla release](H:/01.programovani/cez-dynamic-tariff/scripts/README.md)
- [Workflow release](H:/01.programovani/cez-dynamic-tariff/.github/workflows/release.yml)
- [Workflow Quality](H:/01.programovani/cez-dynamic-tariff/.github/workflows/quality.yaml)
- [HACS](H:/01.programovani/cez-dynamic-tariff/.github/workflows/hacs.yaml)
- [Hassfest](H:/01.programovani/cez-dynamic-tariff/.github/workflows/hassfest.yaml)
- [Balicí nástroj](H:/01.programovani/cez-dynamic-tariff/scripts/build_release.py)
- [Přiložení a ověření assetu](H:/01.programovani/cez-dynamic-tariff/scripts/attach_release_installer.cjs)
- [Ověření balíčku](H:/01.programovani/cez-dynamic-tariff/scripts/verify_release_package.py)
- [Licence](H:/01.programovani/cez-dynamic-tariff/LICENSE)
