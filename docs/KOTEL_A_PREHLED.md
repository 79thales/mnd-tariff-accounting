# Volitelné měření kotle a přehled MND

Funkce je ve výchozím stavu vypnutá a nastavuje se samostatně pro každé
odběrné místo: zařízení MND → Konfigurace → Elektrická spotřeba plynového kotle.
Změna je místní evidence Home Assistantu; neodesílá požadavek na portál MND.

## Nastavení a význam měření

- Zapněte „Zobrazovat elektrickou spotřebu kotle“ a výslovně vyberte senzor
  příkonu ve W nebo kW. Integrace nikdy sama nevybírá první zásuvku.
- Volitelně vyberte kumulativní energii Wh/kWh se třídou total/total_increasing
  a entitu požadavku topení (climate, switch nebo binary_sensor).
- Náhled ukazuje dostupné současné hodnoty ještě před uložením. Zásuvka měří
  celý připojený odběr kotle: elektroniku, čerpadlo a případně další části.
  Příkon se nevydává za samostatnou spotřebu čerpadla ani důkaz plamene.
- Platnost reportu má výchozí hodnotu 900 sekund, povolený rozsah 30–86 400 s.
  Nastavte ji podle skutečné četnosti reportování zařízení. Last_changed
  není heartbeat; server používá last_reported, případně last_updated.
- Vypnutí funkce skryje elektrické údaje a uchová zvolené zdroje. Změna názvu
  entity se sleduje přes UUID registru. Nekompatibilní výběr se odmítne před
  změnou archivu. Dočasně nedostupný uložený výběr formulář nesmaže.

Integrace nevypíná zásuvku, nespíná relé ani nemění termostat, ochrany,
časový program nebo provozní limity. Žádné automatické rozpoznávání hoření
podle univerzálního příkonového prahu není zavedeno. Vyžadovalo by další
naměřené úplné cykly pro konkrétní kotel a jeho režimy.

## Přehled a podrobnosti

Hlavní pohled má tři bloky: Právě teď, Spotřeba a Vyúčtování. Při zapnuté
funkci se k průtoku přidá příkon kotle. Dnešní a měsíční plyn pocházejí ze
stejného vybraného profilu HA jako měsíční graf; nejsou nahrazeny odběrem za
celé účetní období. Jediný hlavní graf zobrazuje posledních sedm dní.

Spotřeba obsahuje měsíční historii, odečty a nativní 24hodinový graf HA pro
průtok, příkon a volitelný požadavek topení. Odlišné jednotky mají oddělené
grafy se stejnou časovou osou. Pokud klient nemá nativní pomocník karet,
nabídne se odkaz do Historie HA. Účetnictví zachovává tabulku nákladů,
skutečné a plánované zálohy i finanční graf; Prognózy a Historie/doklady
zůstávají samostatné podstránky. Administrace je nadále na zařízení.

Generátor i dashboard_template.json používají kompozici 4. Existující cesty,
pět čtecích navigačních odkazů, hlavní pohled, pět subviews a návratové cesty
zůstávají. Volitelné zdroje se načítají z nastavení místa; nevytvářejí povinné
placeholdery „chybějících senzorů“. Aktualizace živého Overview je samostatný
uživatelský krok, nikoli vedlejší účinek lokální implementace.

## Časování, souběh a restart

Změna průtoku či zvolených zdrojů kotle vyvolá sloučený místní přepočet
po 1 sekundě. Minutové hodiny ověřují stáří i bez změny hodnoty. Frontend
promítá stavy HA okamžitě a kontroluje jejich stáří každou sekundu bez sítě.
Zaměření tlačítka neblokuje živé hodnoty; DOM se kvůli nim nepřestavuje.

Účetní detail se mimo editor obnovuje po 30 s jediným požadavkem detail;
načtení účtů a jejich souhrnů se na pozadí neopakuje. Při fokusu zachová DOM
a aktualizuje živé metriky. Rozepsaný editor se automaticky nenačítá. Opožděná
odpověď po změně místa se podle existujícího request ID odmítne.

Souhrny plynu používají hodinový profil HA, který existující lokální úloha
obnovuje přibližně po 10 minutách. Čas „data do“ je konec přijatých agregátů,
nikoli čas otevření stránky. Starší profil bez této hranice ukazuje pomlčku.
Nulový průtok se nesnažíme použít k dopočítání chybějícího denního objemu.

Elektrická energie dnes/měsíc se čte na vyžádání z Recorderu. Jeden zámek
na koordinátor sloučí souběžné karty; cache nejvýše 5 minut je oddělená podle
zdroje, aktuálního ID, pásma a místního dne. Dotaz běží v Recorder executoru
s timeoutem 15 s, čte nejvýše aktuální měsíc a předchozí kontrolní hodinu.
Změna místa, přejmenování zdroje nebo půlnoc nepoužije cizí starý souhrn.
Cache není archiv. Po restartu se vytvoří znovu při dalším otevření.

Unload odpojí existující posluchače a časovače; frontend při odpojení zruší
oba intervaly. Již spuštěné čtení Recorderu podléhá timeoutu, zrušení se
nepolyká. Při chybě se nepublikuje nula ani nezapisuje do měření či účetnictví.

## Pokrytí, jednotky a omezení

Elektrický souhrn sčítá doložené změny uzavřených UTC hodin. Vyžaduje
předchozí stav a soulad sum/change; mezera, pokles čítače či neznámý údaj
hodinu vyřadí. Nevymýšlí datum resetu ani nulovou spotřebu za výpadek.
Wh se přesně převádí na kWh; kumulativní stav čítače není spotřeba dne.
Otevřená hodina se nedopočítává z příkonu. Dnešek i aktuální měsíc jsou
označené jako známá část s počtem dostupných uzavřených hodin.

Hranice období používají časové pásmo HA; dny s 23 a 25 hodinami zachovávají
skutečnou délku. Elektřina, plyn a finance se nesčítají. Bez doložené ceny
elektřiny nevzniká elektrický finanční odhad. Původní odečet a faktura MND
nadále mají svoji autoritu a datum, novější HA měření je samostatné.

Veřejné příklady i testy používají výhradně syntetické entity a hodnoty.
Konkrétní domácí entity, zákaznické identity ani finanční data nejsou
zabudovány v šabloně, zdrojích, testech nebo releasu.
