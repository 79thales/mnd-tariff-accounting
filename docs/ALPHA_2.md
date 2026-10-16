# MND 0.1.0-alpha.2 — přehled, správa místa a finanční podklady

Tato verze navazuje na alpha.1 a na připomínky uživatele z 16. 10. 2026.
Jde dále o testovací prerelease. Původní tag a instalační asset alpha.1 se nemění.

## Ovládání

- Běžný přehled je hlavní view existujícího Overview `/lovelace/mnd`.
  Nativní HA lišta s menu a ostatními záložkami tak zůstává součástí stránky.
  Vlastní panel správy nemá duplicitní položku MND v bočním menu.
- Veškerá správa začíná v **Nastavení → Zařízení a služby → Zařízení → MND**
  pro konkrétní místo. Konfigurační odkaz zařízení nese účet i místo a otevírá
  místní správu. K dispozici je také akce Konfigurace odběrného místa;
  backendové tlačítko vytvoří odkaz v notifikaci, nemůže samo vybrat prohlížeč.
- Čtecí karty nepřipojují editory, generátor, soukromé importní formuláře
  nebo diagnostické JSON. Kompatibilní starý pohled editoru nabídne odkaz na zařízení.
- Rozsáhlý úvodní banner byl odstraněn. Přehled obsahuje průtok, spotřebu,
  poslední odečet, aktuální předpis, skutečné úhrady místní knihy a známé náklady.
- Chyba požadavku ukončí načítání a nabídne opakování. Samotný číselný kód
  již není jediným vysvětlením. Příčinu původního snímku s číslem 3 nelze zpětně
  potvrdit z chybějícího záznamu; test pokrývá zotavení z takového odmítnutí.

## Generátor i existující šablona

Po aktualizaci integrace otevřete zařízení MND → konfiguraci → Generate dashboard.
Vytvořte náhled pro **stejnou cestu**, jakou používá existující MND view, a zvolte
Uložit MND v horní liště. Před zápisem se stáhne soukromá záloha Overview.

Generátor a `dashboard_template.json` sdílejí kompozici verze 2. Aktualizace
rozpozná vlastní kartu podle typu, účtu a místa. Nahrazuje její řízená nastavení;
cizí karty, pořadí pohledů, místní názvy a ostatní vlastnosti zachová. Nejednoznačná
kolize se odmítne. Čtení těsně před zápisem chrání před změnou od náhledu; po
jednom zápisu se znovu ověří uložený celek. Nativní HA API save nemá CAS a nemůže
vyloučit závod s cizím zápisem během samotného ukládání.

Pět navigačních odkazů směřuje na čtecí přehled, spotřebu, finance, prognózy
a vyúčtování. Zachována je také kompatibilní skrytá cesta starého editoru.
U YAML/automatického Overview je dostupný export fragmentu; nativní storage
Lovelace neuchovává YAML komentáře. Pravidla a účel jsou v generátoru a dokumentaci.

## Zálohy, úhrady, faktury a exporty

Veřejný klient `moje.mnd.cz` doložil 16. 10. 2026 následující čtecí rozhraní:

- `/api/payments` používá `payPeriod=365`; přehled za rok není úplná historie.
- `/api/advances` a `/api/invoices` mají rostoucí `maxRowCount`, samostatný
  detail `/api/advance?adviId=…` a `/api/invoice?ivaId=…`.
- Exporty vytváří `/api/Documents/AdvanceExport`, `InvoiceExport` a
  `PaymentExport`; PDF vyúčtování získává `Documents/InvoicePdf`.
  GUID slouží pouze ke stažení ověřeného souboru; token se neposílá v URL.

Finanční historie se automaticky obnovuje s cloudovými podklady. Seznamy
rostou po 100 do ochranné hranice 2 000 řádků. Detaily se obnovují po dávkách
nejvýše 40 požadavků s časovým rozpočtem 120 sekund na druh; jednotlivý zahájený
požadavek má vlastní timeout 30 sekund. Kurzor brání vyhladovění starších dokladů.
Chyba zachová dříve přijatá data a částečné pokrytí je přiznané.

`ADVI_SUMTOTAL` je předpis, `ADVI_BALANCE` zbývající částka a skutečné úhrady
jsou pouze doložené položky `PayInfo` s `PAY_DATE`/`PAY_AMOUNT`. Stejné částky
ve stejný den se neslévají. Přehled zobrazuje fakturační výsledek podle MND,
nikoli odhadnuté plné náklady faktury. Měna musí být doložená CZK. Pole
`BALANCE_SAVED` se nepoužívá jako celková cena energie.

Převzetí do místní účetní knihy je samostatné potvrzení v konfiguraci místa.
Správce potvrzuje přiřazení dokladů splatných ve vybraném účetním období
a kontrolu ručních duplicit. Následně se předpisy a skutečné úhrady uloží
odděleně se stabilními zdrojovými identitami. Opakování je idempotentní,
změna vytváří revizi, zrušená zdrojová úhrada nulovou opravnou verzi.
Úplnost plateb se nepotvrzuje automaticky. Faktury a jejich vypořádání nejsou
znovu přičteny k zálohám; potvrzené plné náklady faktury nadále vyžadují
doložený doklad a samostatné potvrzení v místní evidenci.

Zálohový export a přehled faktur mají oddělená tlačítka v konfiguraci místa.
Čtecí detail vyúčtování umožňuje stáhnout konkrétní PDF. ID ověřuje backend
pro dané místo; soubory se ukládají do neveřejného úložiště s SHA-256.

Veřejné podklady: [stránka plateb](https://moje.mnd.cz/payments),
[společný veřejný klient](https://moje.mnd.cz/_next/static/chunks/pages/_app-d4693e13afff6e1f.js),
[veřejná stránka payments](https://moje.mnd.cz/_next/static/chunks/pages/payments-e2660f392bd9f935.js).
Znalost veřejných polí není důkaz živého ověření všech odpovědí účtu.

## Průtok a měřená spotřeba

V konfiguraci vyberte samostatně kumulativní senzor m³ a senzor průtoku.
Průtok se přesně převádí z m³/h, m³/s, l/min nebo l/h na m³/h. Neprovádí
se neověřené dopočítávání kumulativního stavu integrací neúplného průtoku.
Platnost reportu je konfigurovatelná v sekundách, výchozí 900 s; nastavte ji
podle skutečného reportování zařízení, zejména u senzorů hlásících pouze změny.

Průtok reaguje po sekundovém sloučení událostí a minutový místní přepočet
ověřuje čerstvost i bez nového pulsu. Neprovádí síťové čtení. Unload odpojí
časovače a posluchače. Identita z registru přežije přejmenování zdroje.
Neznámé, neplatné a zastaralé údaje nejsou nula.

Odečet MND má nadále přednost pro stejnou měřicí hranici. Porovnání očekávaného
senzorového stavu s novým MND bodem vyžaduje stejný přesný okamžik a segment;
pouhý den nedokládá souběh. Rozdíl se nepromění v další spotřebu. Historická
kalibrace zůstává v auditu. Srovnání prognóz s dokončeným měřením nebo potvrzenou
fakturou se ukládá k původnímu snapshotu a shodnému období. Bez doloženého
převodu na energii se m³ a MWh neporovnávají jako stejná veličina.

## Migrace a hranice ověření

- Není potřebná destruktivní migrace Store. Nové finanční a porovnávací
  sekce jsou doplňkové; staré odečty, účetní události, doklady a prognózy zůstávají.
- Přerušený cloudový průvodce lze po nově ověřeném přihlášení převzít s
  potvrzením. Ruší se pouze shodný uživatelský průvodce stejného účtu;
  ochrana duplicitních účtů zůstává aktivní. Chyba načtení míst již předem
  nerezervuje identitu účtu.
- Nové finanční endpointy/exporty nejsou v této revizi potvrzené novým
  zákaznickým testem. Dosavadní nasazená alpha.1 obsahovala čtecí chybu plateb;
  HA nebyl během přípravy alpha.2 aktualizován ani restartován.
- Vizuální test na skutečném iPhonu a v HA zatím není potvrzen: dostupný
  nástroj vrací prázdnou nabídku prohlížečů. DOM testy to nenahrazují.
- Plné automatické mapování smluvních cen zůstává omezením předchozí alpha.
  Jde o prerelease, nikoli tvrzení o dokončené produkční paritě všech MND dat.

Přesné výsledky CI, testované verze HA a hash instalátoru jsou doloženy
v běhu vydání a v místním protokolu balení; nevydávají se za živý zákaznický test.
