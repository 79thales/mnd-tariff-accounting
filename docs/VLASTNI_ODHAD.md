# Vlastní odhad podle měření

Hlavní přehled rozlišuje **Náš odhad podle spotřeby** a samostatný výhled
vypočtený z prognózy MND. Potvrzené originální vyúčtování má přednost.
Vlastní odhad je orientační: žádný z výhledů nenahrazuje fakturu.

## Potřebné podklady

- Dodavatelské účetní období a fyzický odečet na jeho přesné počáteční
  hranici. Přesně časovaný odečet MND má přednost; shodně doložený ruční
  fyzický odečet se použije, pokud přesná kotva MND chybí. Odečet se nesmí
  zpětně vymyslet. Datum MND bez času nelze prohlásit za půlnoc.
- Aktuální kumulativní měření navázané na stejné měřidlo a jeho segment.
  Poslední použitý vzorek musí být z aktuálního místního dne. Výpadek,
  reset, nesoulad měřidla nebo časově nejednoznačné odečty výpočet přeruší.
- Profil 365 souvislých dokončených měřených dnů. Chybějící den ani zima
  nejsou nulové. Při neúplném profilu se uvádí počet dostupných dnů a měsíce
  s mezerami; MND výhled zůstává dostupný zvlášť.
- Doložený převod kWh/m³ platný pro celé období a ověřený ceník pokrývající
  období. Odhadovaný převod a převzetí poslední známé regulované ceny pro
  budoucnost se výslovně označují. Pokud se převod či cena v období mění
  a dostupné podklady nelze bezpečně rozdělit, výsledek zůstane neznámý.
- Úplný seznam předpisů a dostupné úhrady MND. Minulá nezaplacená záloha
  není automaticky budoucí platbou; nejasné vratky či kredity výhled pozastaví.
  Zálohy se z MND znovu ručně neopisují a není nutné nastavovat období
  volitelné vlastní evidence.

Historický pulsní senzor a aktuální objemový senzor mohou být dvě entity
jednoho plynoměru. V Editoru → Měření a vlastní evidence lze po ověření
výslovně potvrdit jejich vztah. Potvrzení platí pro aktuální registry identity,
segment a zadaný objem pulsu. Změna některého z nich ho zneplatní a vyžaduje
nové potvrzení. Samotné přejmenování entity identitu registry nemění.

## Výpočet a aktualizace

Ze změny fyzického stavu od doložené počáteční kotvy a navazujících měření
vzniká odběr dosud. Budoucí m³ vycházejí ze sezónních měsíčních průměrů
úplných denních měření před dneškem. Zbývající část aktuálního dne se
orientačně dělí podle skutečné délky dne v místním pásmu, včetně změny času;
není označena jako měřená spotřeba. Použitý čas měření a výpočtu se uvádí
samostatně. Cena a předpisy jsou nezávislé na elektřině kotle.

Očekávaný výsledek = skutečně doložené platby + zbývající očekávané budoucí
zálohy − odhad celkových nákladů. Kladný výsledek znamená očekávaný
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
