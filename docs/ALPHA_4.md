# Alpha.4 — přehled účetního období MND

## Období a hlavní přehled

Období přebírá aktuální uložený graf dodavatele, v původních hranicích From/To.
Nejde o leden–prosinec. Místní nastavení intervalu slouží importnímu režimu;
při dvou odlišných souběžných obdobích se výpočet zastaví jako nejednoznačný.

Hlavní pohled ukazuje aktuální průtok m³/h, známou naměřenou část m³,
poslední stav plynoměru MND a předpis zálohy. Následuje souhrn pro celé
účetní období, peněžní graf a měsíční sloupce. Pět čtecích detailů a nativní
horní lišta HA zůstávají zachované. Formuláře jsou pouze v konfiguraci místa.

## Význam částek a přednost originálu

- Uhrazené zálohy jsou doložené PayInfo konkrétních předpisů splatných v
  daném období. Používá se datum přijetí platby. Samostatný bankovní přehled
  ani místní kopie téhož zápisu se znovu nepřičítají.
- Plán záloh obsahuje doložené předpisy splatné uvnitř období. Nevymýšlí
  chybějící měsíce a nepřibírá první předpis následujícího období.
- Náklady k odečtu používají souhrnnou spotřebu MND a doloženou cenu s DPH.
  Orientační rozdělení měsíční stálé platby podle kalendářních dnů je
  výslovně označeno; tato projekce není potvrzenou místní účetní knihou.
- Originální faktura nahradí cenu modelu přesně ve svém rozsahu. Zbývající
  spotřeba se počítá po odečtení fakturovaných MWh a fixní platby jen za
  nevyúčtované dny. Bez rozlišitelné energie se ukáže pouze doložená část
  nákladů. Faktura přes hranici období ani překrývající se originály se
  nerozdělují nebo nesčítají odhadem.
- Po úplném vyúčtování rozhoduje původní náklad a podepsaný výsledek faktury.
  Přeplatek/nedoplatek není celkovou cenou plynu.
- Výhled nákladů oceňuje celkovou prognózu MND. Předpoklad pozdějších
  regulovaných sazeb podle posledního známého ceníku je uvedený u výsledku.
  Výhled výsledku je plán záloh minus celkový výhled nákladů; není dnešním saldem.

Neznámá částka je `null`/pomlčka. Nula vznikne jen z doloženého prázdného
nebo skutečně nulového výsledku. Chyba zdroje nemaže původní originály.

## Cenové podklady

Čtecí parser podporuje jednoznačnou šestisloupcovou měsíční tabulku MND
v cenách s/bez DPH a kontroluje výpočet i odběrové pásmo. Aktuální PRNOW se
nesmí zaměnit za budoucí PRFUT. Individuální zvýhodnění vyžaduje výslovnou
částku Kč/MWh včetně DPH a dobu platnosti; marketingové procento samo nestačí.
Daňový kontext domácnosti je doložen originální fakturou. Spotové, kapacitní
nebo jiné neověřené formáty se nepovažují za známou cenu.

Originál je uložen soukromě s hash. Účetní a zákaznické hodnoty nejsou
součástí diagnostiky, veřejných fixtures ani instalátoru. Čtení podkladů
nevytváří potvrzení ruční faktury nebo platby v účetní knize HA.

## Grafy a historie měření

Peněžní graf má čtyři série: náklady k odečtu, výhled nákladů, úhrady a plán.
Úhrady a předpisy mají schodový průběh podle skutečných dat. Bez měsíčního
profilu MND se kreslí pouze přerušovaná spojnice doložených krajních bodů
výhledu. Nevznikají domnělé měsíční náklady. Svislá čára označuje dnešek.

Sloupce HA obsahují m³ v místním časovém pásmu. Úplný měsíc vyžaduje všechny
hodiny včetně změn letního času. Neúplný měsíc obsahuje jen doložené přírůstky;
chybějící měsíc nemá nulový sloupec. Částečný krajní měsíc účetního období
je rovněž neúplný. Součet HA se nemusí rovnat souhrnnému odečtu MND.

Vedle hlavního objemového a průtokového senzoru lze v konfiguraci vybrat
původní historický pulsní čítač a jeho fyzický objem jednoho pulsu. Faktor
není korekce podle odchylky MND. Registr, segment, původní jednotka a faktor
zůstávají u profilu; dvě řady téhož měřidla se nesčítají. Po změně faktoru je
nutný nový import; staré přírůstky s odlišným faktorem se zatím nepoužijí.

Recorder se čte po nejvýše sedmi dnech. Samostatná úloha obnovuje poslední
tři dny po deseti minutách, pokud neběží úplný import; unload ji zruší.
Minutový přepočet nevolá MND. Frontend obnovuje čtecí pohled po 30 sekundách
a nepřerušuje rozpracovaný formulář. Nové instalace hledají nejdelší
dostupnou historii; lokální omezení ověřování této alfy od ledna není
omezením produktu.

## Generátor a ověření

Generate dashboard a přibalená JSON/YAML šablona mají kompozici 3 a stejné
vazby osmi nových účetních senzorů. Aktualizace nahrazuje pouze vlastní
karty příslušného účtu a místa; zachovává ostatní pohledy, názvy a navigaci.
Komentář kompozice je součástí vrácených metadat generátoru.

Regrese používají syntetické podklady: období přes Nový rok, původní faktury
včetně částečných intervalů, duplicitní platby, nulové a chybějící údaje,
pulsní Recorder, privátní obnovu a DOM obou grafů. CI ověřuje skutečný HA
na deklarovaném minimu i dynamicky zjištěné stabilní verzi. DOM testy a
ověření uložené konfigurace nejsou vizuální zkouškou mobilní aplikace.

Loňské a topné/netopné srovnání nadále vyžaduje odpovídající historii;
alpha.4 z chybějícího minulého roku nevytváří odhadnutou skutečnost.

## Dokončené ověření 16. 10. 2026

[Workflow tagu](https://github.com/79thales/mnd-tariff-accounting/actions/runs/38918479190)
úspěšně ověřilo Quality, HACS a Hassfest: 130 Python testů, 26 Node testů
a 22 skutečných HA testů na každé z dvojic HA 2026.3.1/plugin 0.13.317
a aktuální stable HA 2026.10.1/plugin 0.13.372.

Tag `v0.1.0-alpha.4` ukazuje na runtime commit
`431a75ff08dd242376ba2896cba82366a7ba4d02`. Instalační ZIP má 175 772 bajtů,
47 runtime souborů a SHA-256
`4812d1d1ac508d73d26ede1393b6c78ae7c69d32789c59225717538332f3430f`.
Draft i anonymní stažení zveřejněného prerelease odpovídají sestavení z tagu.

Uživatelem schválené nasazení přes HACS a jediný restart potvrdily běžící
alpha.4. Živý přehled načetl dodavatelské účetní období, nenulové úhrady,
plán, odběr, náklady a výhled výsledku bez chyby MND. Historie původního
pulsního zdroje byla načtena v potvrzeném rozsahu této alfy; při kontrolním
překryvu 1 080 hodin souhlasily přírůstky s odvozeným objemovým senzorem.

Šest existujících MND karet v Overview je aktualizovaných na kompozici 3,
bez změny ostatních pohledů. Uložená konfigurace byla porovnána s připraveným
patchem, generátor nemá chybějící entity a poskytovaný JS odpovídá tagu.
Živě prošly oba finanční exporty, PDF vyúčtování a kontrola odkazu konfigurace
zařízení. Konečný privátní ZIP prošel kontrolou hash originálů i obnovou
nastavení, odečtů, profilu a cenových podkladů do izolované paměti.

Skutečné mobilní vykreslení není tímto ověřené; prohlížeč nebyl k dispozici.
Soukromé hodnoty a podrobný protokol zůstávají mimo veřejný repozitář.
