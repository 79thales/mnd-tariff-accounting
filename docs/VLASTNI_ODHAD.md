# Vlastní odhad podle měření

Hlavní přehled rozlišuje **Náš odhad podle spotřeby** a samostatný výhled
vypočtený z prognózy MND. Potvrzené originální vyúčtování má přednost.
Vlastní odhad je orientační: žádný z výhledů nenahrazuje fakturu.

## Historie výsledku

Podrobnosti účetnictví obsahují sedmidenní graf uložených stavů vlastního
odhadu a proklik do historie Home Assistantu. Kladná hodnota znamená
očekávaný přeplatek, záporná očekávaný nedoplatek v Kč. Graf zachycuje
historické verze odhadu, nikoli zpětně vypočtené skutečné vyúčtování.
Záznam začíná až po vytvoření senzoru a jeho dostupnost závisí na nastavení
a délce uchování Recorderu. Chybějící záznam není nulová hodnota.

## Potřebné podklady

- Dodavatelské účetní období a fyzické odečty. Přesně časovaná kotva má
  přednost; bez ní lze použít odečet MND z počátku období nebo z předchozího
  dne a poslední fyzický odečet před dneškem. Předpokládané denní hranice
  jsou orientační, protože čas odečtu MND není známý.
- Aktuální kumulativní měření navázané na stejné měřidlo a jeho segment.
  Poslední použitý vzorek musí být z aktuálního místního dne. Výpadek,
  reset, nesoulad měřidla nebo časově nejednoznačné odečty výpočet přeruší.
- Pokud není 365 souvislých měřených dnů, chybějící sezónu lze odhadnout
  z nepravidelných fyzických odečtů MND. Rozdíl dvou odečtů se rozdělí
  rovnoměrně mezi dny jejich intervalu, nejvýše 62 dnů. Různé plynoměry,
  konflikty, reset a instalace měřidla interval přerušují. Měřené dny HA
  mají přednost, pokud nejsou ve významném rozporu s MND. Pro každý potřebný budoucí měsíc je třeba alespoň sedm
  dostupných dnů z posledního roku; nejde o záruku reprezentativnosti.
  Takto dopočtené dny se nikdy nevydávají za fyzicky změřené.
- Převod kWh/m³ platný pro celé období nebo orientační převod z poslední
  doložené faktury a ověřený ceník pokrývající období. Převod z faktury
  se za přesný budoucí koeficient nevydává. Převzetí poslední regulované ceny pro
  budoucnost se výslovně označují. Pokud se převod či cena v období mění
  a dostupné podklady nelze bezpečně rozdělit, výsledek zůstane neznámý.
- Úplný seznam předpisů a dostupné úhrady MND. Minulá nezaplacená záloha
  není automaticky budoucí platbou; nejasné vratky či kredity výhled pozastaví.
  Zálohy se z MND znovu ručně neopisují a není nutné nastavovat období
  volitelné vlastní evidence.

Chybějící měsíční předpisy výhled orientačně doplní aktuální výší zálohy,
pokud jsou v seznamu dva sousední měsíce se shodným dnem splatnosti a částkou
odpovídající aktuální záloze MND. Předpoklad se vztahuje jen na chybějící
měsíce vybraného účetního období. Může zahrnovat i minulý měsíc, ale nikdy
se nevydává za skutečně přijatou úhradu ani potvrzený předpis. Po načtení
skutečného předpisu se jeho předpokládaná náhrada automaticky odstraní.
Nepravidelný či nejasný rozvrh nelze tímto způsobem spolehlivě doplnit.

Historický pulsní senzor a aktuální objemový senzor mohou být dvě entity
jednoho plynoměru. V Editoru → Měření a vlastní evidence lze po ověření
výslovně potvrdit jejich vztah. Potvrzení platí pro aktuální registry identity,
segment a zadaný objem pulsu. Změna některého z nich ho zneplatní a vyžaduje
nové potvrzení. Samotné přejmenování entity identitu registry nemění.
Bez potvrzení je u orientační varianty vztah zdrojů výslovně označen jako
předpoklad. Pro přesnou variantu je potvrzení různých zdrojů nutné.

## Výpočet a aktualizace

Ze změny fyzického stavu mezi MND odečty a navazujících měření HA vzniká
odběr dosud. Orientační varianta považuje poslední MND odečet před dneškem
za konec jeho dne; HA přičítá až od následujícího dne. Odečet na počátku
období nebo den před ním je považován za počáteční hranici. Proto je celý
součet pouze orientační. MND odečet s dnešním datem se pro tento odhad
použije až další den, aby se nepřekrýval s dnešním měřením HA.

Dny úplné HA historie porovnáváme s fyzickými odečty MND téhož měřidla.
Pokud rozdíl překračuje všechny možné časy v hraničních dnech i toleranci
2 m³ pro celočíselné odečty, sporný interval (nejvýše 62 dnů) v profilu
orientačně nahradí rovnoměrně rozdělený rozdíl odečtů MND. Původní měření
se nemění a nesoulad je zobrazen; příčinu z něj samotného nelze určit.

Dnešní HA statistika musí pokrývat všechny uzavřené hodiny od půlnoci.
Přírůstky aktuálního senzoru po uzavřené hodině se přidají jen při doložené
návaznosti vzorků. Stav v hranici musí doložit přesný vzorek nebo shodné
spojité vzorky před hranicí a po ní; samotný starší vzorek nestačí. Pokud dojde
k výpadku nebo resetu, výpočet zůstane k času
poslední uzavřené hodiny a zbývající čas zahrne do prognózy, nikoli do
naměřené spotřeby. Budoucí m³ vycházejí ze sezónních měsíčních průměrů
měření HA a případně interpolovaných intervalů MND. Zbývající část dne se
orientačně dělí podle skutečné délky dne v místním pásmu, včetně změny času;
není označena jako měřená spotřeba. Použitý čas měření a výpočtu se uvádí
samostatně. Cena a předpisy jsou nezávislé na elektřině kotle.

Očekávaný výsledek = skutečně doložené platby + očekávané neuhrazené a
předpokládané zálohy − odhad celkových nákladů. Kladný výsledek znamená očekávaný
přeplatek, záporný nedoplatek. Originální faktura pokrytého intervalu
nahrazuje model; neúčtuje se podruhé. Dnešní stálá platba je zahrnuta
v celkovém výhledu, nikoli v orientačních nákladech do začátku dne.

Platný report senzoru se ukládá po existujícím 30sekundovém sloučení změn
a spustí přepočet bez kontaktování portálu MND. Needitorový panel obnovuje
detail přibližně po 30 sekundách; při zaměřeném jiném ovladači aktualizuje
vlastní údaj bez ztráty fokusu. Během restartu se obnoví z archivované
revize, neplatné podklady zůstanou neznámé. Odpojení integrace ukončí její
časovače a běžící úlohy.

Graf má samostatné označení vlastního a dodavatelského výhledu. Přerušované
spojnice spojují pouze známé krajní body; nejsou měsíčními odečty ani
potvrzenými budoucími cenami.

## Entity

Nové entity vlastního výsledku, nákladu a spotřeby mají samostatné identity
`own_forecast_balance_czk`, `own_forecast_cost_czk`, `own_forecast_mwh`
a `own_actual_mwh`. Uvádějí kvalitu, důvod chybějícího výpočtu, časy,
metodu a dostupné pokrytí. Existující entity `billing_forecast_*` si
ponechávají svůj dosavadní dodavatelský význam a historii.
