# Prompt pro Codex Sol 6.1

Tento text je připravený pro vložení do nového chatu **v již existujícím projektu MND Tariff & Accounting for Home Assistant**. Jeho uložení samo implementaci nespouští.

---

Naprogramuj samostatnou HACS integraci **MND Tariff & Accounting for Home Assistant** podle kompletního zadání v tomto projektu.

Pracuj výhradně v `H:\01.programovani\MND Tariff & Accounting for Home Assistant\`. Nejprve ověř skutečný pracovní adresář. Nepoužívej staré kopie na C: a nevytvářej integraci uvnitř WebDownloaderu. Nezakládej duplicitní Codex projekt. Komunikuj česky a o sobě piš v ženském rodě.

Než začneš upravovat zdroje, přečti:

1. `AGENTS.md`
2. `ZADANI_MND_SOL_6_1.md` — úplné funkční zadání včetně M01–M20 a T01–T38.
3. `GIT_POLITIKY_CEZ.md` — závazné převzetí pravidel Git, testů, balení a vydávání.
4. `PODKLADY_A_OVERENI.md` a `REFERENCNI_OTISKY.md` — ověřené podklady a hranice dosavadních testů.
5. `NAVRH_LOGA.md` a návrh `brand-concept/mnd-tariff-accounting-concept.png`.

Funkční reference MND je `H:\01.programovani\webdownloader\`. Reference UX/účetnictví/generátoru/Gitu je `H:\01.programovani\cez-dynamic-tariff\`. Oba projekty jsou pro tento úkol pouze ke čtení. ČEZ obsahuje i důležité necommitnuté změny; nevracej je zpět a necommituj je.

Přenes všechny funkce modulu MND z C# do nativní Python integrace HA, včetně portálu, míst, cen, záloh, platebních podkladů, dokumentů, exportů XLSX, veškeré dostupné historie, importu, auditní evidence, grafů a snapshotů prognóz. Není požadováno přenášet části ORLEN/EDC ani technologii WPF/WebView2 do HA.

Pro skutečnou spotřebu musí fungovat volba existujícího kumulativního senzoru plynu nebo ručních odečtů v HA. **Odečet MND má vždy přednost pro odpovídající místo, měřidlo a čas.** Novější měření na něj navazuje; opožděný MND odečet vyvolá auditovatelnou korekci bez dvojího účtování. Odhad MND zůstává označený jako odhad.

Odděl předpis záloh od skutečných úhrad a průběžný/roční odhad od potvrzené faktury. Podporuj částečné i mimořádné úhrady, faktury a jejich opravy, přeplatky, nedoplatky, vratky a převod kreditu. Chybějící cena, koeficient, platba nebo historie není nula. Senzor nepřepisuj a k vlastnímu HA nevyžaduj REST token.

Součástí je **Generate dashboard → Přidat do horní lišty existujícího Overview `/lovelace`**, s hlavním přehledem a detailními subviews. Zachovej ostatní pohledy a místní úpravy. Generátor, přibalenou šablonu a dokumentaci udržuj ve stejné změně.

Začni ověřením skutečného přihlášení/transportu MND z prostředí HA; úspěch C# WebView2 není důkaz bezobslužného API. Endpointy nevymýšlej. Importní režim a účetnictví implementuj nezávisle; nefunkční cloudový rozsah nepovažuj za dokončený jen proto, že funguje ruční import. Živé testy proveď pouze v rozsahu aktuálního povolení; starý jednorázový test nepoužij jako neomezené povolení a nepřebírej tajemství z DOCX do zdrojů.

Převzatá pravidla Git zahrnují cílovou větev `master_HA`, veřejnou distribuci pro HACS jako u ČEZ, testy Quality/HACS/Hassfest, instalační ZIP z konkrétního tagu, shodu verze a český/anglický changelog, nejprve draft release a neměnnost zveřejněných tagů/assetů. WebDownloader zůstává private. Připrav konkrétní ověřený výsledek před případným zveřejněním; založení/publikaci repozitáře či nasazení do živého HA nevydávej za součást již provedené přípravy.

Neukládej skutečné zákaznické exporty, EIC, finanční data ani přístupy do veřejného Gitu. Testuj syntetická data, důležité bloky vysvětli česky včetně jednotek, priority, časování, souběhu, restartu a chyb. Použij nejnovější stabilní HA zjištěný při testu a odpovídající testovací plugin, vedle deklarovaného minima; při nedostupné kontrole chybu přiznej a nenahrazuj ji tiše starší verzí.

Pokračuj po etapách až k celému požadovanému výsledku. Veď průběžnou matici M01–M20/T01–T38, dělej smysluplné testy a nezastavuj se u scaffoldingu nebo pouhého návrhu. Při externím omezení dokonči nezávislé části a přesně dolož, co zůstalo neověřené či nehotové. Závěrečné předání musí obsahovat instalační balíček, dokumentaci, migrace, generátor i šablonu a poctivý report testů.
