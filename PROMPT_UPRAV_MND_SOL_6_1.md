# Předávací prompt — opravy MND pro Sol 6.1

**Pouze připravený text pro pozdější spuštění. Aktuální pokyn uživatele je připravit zadání a nic neopravovat. Vložení souboru do projektu není autorizací k implementaci.**

Následující text použij až ve chvíli, kdy uživatel výslovně spustí opravy:

---

Uprav existující integraci MND v projektu `H:\01.programovani\MND Tariff & Accounting for Home Assistant\` podle `ZADANI_UPRAV_MND_SOL_6_1_2026-10-16.md`. Nezakládej nový projekt a nezačínej znovu od scaffoldingu. Nejprve přečti `AGENTS.md`, uvedené zadání oprav, původní `ZADANI_MND_SOL_6_1.md`, `GIT_POLITIKY_CEZ.md` a `IMPLEMENTACE.md`. Novější požadavky na vzhled a administraci mají přednost před původní kompozicí.

Výsledek musí splnit zejména:

- Jednoduchý MND přehled v horní liště existujícího Overview `/lovelace`, se skutečnou navigační lištou HA a menu i na iPhonu. Systémová lišta iOS na snímku nechybí; problém je chybějící okolní navigace HA na vlastní obrazovce MND.
- Veškerou administraci zpřístupni z detailu zařízení MND pro konkrétní odběrné místo v Nastavení → Zařízení a služby → Zařízení. Uživatel výslovně označil obrazovku s bloky „Zařízení – informace“, „Ovládací prvky“ a „Senzory“, kde jsou nyní Generate dashboard a Recompute accounting. Odtud otevírej konfiguraci a rozsáhlejší formuláře s již vybraným místem a návratem na stejné zařízení. Běžný přehled obsahuje údaje a čtecí detaily; žádné rozsáhlé editory, importní formuláře nebo generátor pod každou stránkou.
- Oprav prázdnou historii záloh, předpisů, úhrad a vyúčtování. Dolož skutečné rozhraní a význam dat ze stránky `https://moje.mnd.cz/payments`, Exportu historie záloh, Exportu přehledu vyúčtování a Detailu jednotlivé faktury. Samotné HTML tlačítek není datový kontrakt.
- Vyšetři `portal_request_failed`, samotné hlášení `3`, prázdný výběr místa a nekončící „Načítání…“. Nepředstírej potvrzenou příčinu. Ošetři také zotavení z přerušeného přihlášení.
- Zachovej účetní archiv a správný rozdíl mezi předpisem, skutečnou úhradou, fakturou, vratkou a odhadem. Ověř deduplikaci, stránkování, opravy dokladů, izolaci účtů a míst i migraci existujících záznamů.
- Připoj pro každé místo živý průtok a kumulativní spotřebu z existujících senzorů HA. Nastavení a kalibrace patří do konfigurace místa. Ověř jednotky, historii a časovou kotvu; odečet MND má přednost a nové lokální přírůstky na něj navazují. V přehledu/detailu porovnej skutečnou spotřebu s odečty a s archivovanou predikcí za shodný interval a energetickou bázi. Zachovej historii odchylek, měřicí segmenty a nejistotu při výpadku; průtok není stav plynoměru a odhad není měření.
- Uprav současně generátor a přibalenou šablonu; zachovej cizí Overview a čtecí detaily. Existující MND horní view už bylo při předchozí kontrole přítomné současně s bočním panelem.
- Pro navazující rozšíření grafů respektuj oddíl 3.4 a scénáře V01–V06: hlavní ukazatele a loňské srovnání na přehledu, sloupce úplných/neúplných měsíců, časový průběh známých/odhadovaných nákladů a zaplacených/plánovaných záloh se značkou Dnes, přehled očekávaného přeplatku a srovnání topné/netopné sezóny. Nové snímky ČEZ jsou vzorem čitelnosti, ne zdrojem zákaznických hodnot ani elektrické logiky pro plyn. Nezaměňuj toto rozšíření za již dokončenou součást alpha.2; před výpočtem ověř skutečnou historii a při implementaci vydej novou verzi.
- Proveď akceptační scénáře z dodatku, odpovídající testy a skutečné mobilní vizuální ověření. Soukromá data a přístupy nesmějí do Gitu, logů, fixtures ani balíčku. Komentáře a dokumentaci piš česky, o sobě v ženském rodě.

Pokračuj až k ověřené opravě v rozsahu následného pokynu. Při vydání respektuj nový tag/verzi, kompletní draft a neměnnost starých assetů. Autorizaci k nasazení, publikaci nebo restartu vyhodnoť z aktuálního uživatelského pokynu; samotné toto připravené zadání ji neposkytuje.
