# Účetní a datový model

## Jednotky a hranice

Objem je v provozních m³. `MWh = m³ × doložené kWh/m³ / 1000`.
Je-li převod součinem objemového koeficientu a spalného tepla, musí to
uvádět důkaz. Převod se nepoužije znovu na již přepočtený objem.
Orientační koeficient je odhad, chybějící koeficient není nula.

Účetní/cenové intervaly jsou `[od, do)`. Exportní formulář MND má oba dny
včetně, OD 00:00:00 a DO 23:59:00. Skutečné okamžiky mají offset a ukládají
se v UTC; lokální datum vychází z pásma HA. Denní bod bez času není půlnoc.

Čísla se načítají přímo do Decimal. Vstup má maximálně 24 desetinných míst
a absolutní hodnotu 10²⁰. NaN, Infinity, bool a neplatné hodnoty se odmítají.
Recorder má vlastní float reprezentaci měření; převod přes str zachová
jeho dodanou přesnost, nepoužívá se pro import finančních částek.

## Měření a opravy

Doklad má ID, místo, segment, datum/čas, hodnotu, metodu, status a důkaz.
Stejné datum+segment+hodnota je jeden měřicí bod s více doklady. Různé
hodnoty stejné hranice jsou konflikt. Fakturační status neurčuje fyzický původ.
Oprava vytváří novou revizi s `supersedes`; cyklus a větvení se odmítají.

MND převažuje na shodné hranici. Novější místní měření zůstává zachované.
Kalibrace má souběžný fyzický/senzorový stav a registry ID; rebaze podle MND
vyžaduje odpovídající původní vzorek. Mezilehlý reset či nedostupnost přeruší
návaznost, i když koncový stav později překoná počáteční. První stav není odběr.

## Cena a bilance

Tarif má obchodní a ostatní Kč/MWh, stálé Kč/měsíc, platnost, DPH a roli.
Alternativní nabídka se neúčtuje jako smlouva. Mezery/překryvy cen nevytvářejí
náhodnou sazbu. Přechod potřebuje měřenou hranici; volitelný rovnoměrný odhad
podle dnů zůstává označený jako odhad.

Stálá platba se počítá právě jednou. Celý měsíc má plnou sazbu; neúplný
potřebuje potvrzený poměr dnů. Racionální mezisoučet nad Decimal vstupy
uchová přesnou polovinu haléře i při 31 dílech měsíce. Výstup Kč je Decimal
na dvě místa, poloviny od nuly. Objem se kvůli shodě haléřů nemění.

Při úplných podkladech je saldo počáteční kredit plus skutečné přiřazené
úhrady a kreditní korekce minus náklady, vratky a debetní korekce; převody
kreditu mají vlastní směr a protistranu. Plán a `assumed_paid` nejsou úhrada.
Částečné a vyšší úhrady jsou platné. Nejasné párování v1 importu vyžaduje
potvrzení, stejná částka a datum nejsou automaticky shodná transakce.

Faktura nahrazuje předběžný náklad svého uzavřeného období. Přijaté zálohy
z faktury nejsou další peníze. Vratka nemění původní výsledek faktury,
ale zbývající vypořádání. Opravný doklad má vlastní identitu a vazbu.
Průběžný náklad neúčtuje budoucí měsíce jako již spotřebované. Senzor uvádí
hranice vyhodnoceného období; neúplné podklady ponechají plné saldo neznámé.

## Prognózy

Snapshot MND uchovává oddělené MWh podle odečtů, minulého a budoucího odhadu.
Zdroj jsou čísla, nikdy CSS nebo výška sloupce. Období se nesčítají přes
překryvy a nový snapshot nesmaže starý. Porovnání s fakturou vyžaduje
shodné období a potvrzenou energetickou bázi; používá přímo dodavatelské MWh.
Rozdíl je prognóza minus skutečnost, procento má jmenovatel skutečnost.
Při skutečné nule je procento nedefinované, ne 0 %.

Vlastní odhad vyžaduje 365 pokrytých dnů včetně zimy, pak používá měsíční
denní průměry. Budoucí cena potřebuje pokryté doložené tarify a převody.
Metoda, čas, otisk a vstupy se archivují odděleně od měření.

## Archiv a restart

Store je `.storage/mnd_tariff_accounting.archive_<entry>`, originály jsou
v `.storage/mnd_tariff_accounting_documents/<entry>/<sha256>`, nikdy v `/local`.
UI potvrdí změnu až po I/O. Disková chyba nepublikuje novou revizi.
Cancellation dokončí začatý atomický commit. Poškozená nebo budoucí verze
se nenahradí prázdným archivem. Odebrání entry finanční archiv nemaže.

Vlastní archiv i config entry mají první schéma 1. C# `SchemaVersion=1`
je jiný formát s PascalCase, jeho původní pole se zachovávají. Windows cesty
v importu jsou metadata, ne pokyn k otevření souboru. Vlastní záloha má
`format=mnd-ha-place`, verzi a kontrolní hash; Decimal ukládá jako řetězce.
ZIP volitelně zahrnuje originály s ověřenými SHA-256. Obnova slučuje revize,
odmítá konflikty ID a nepřepíše odlišné místní nastavení starší zálohou.
Retence Recorderu nemaže vlastní archiv. Všechny finanční operace vyžadují
správce na serveru, explicitní účet i místo.

## Přesné časy a průběžné účetnictví

`temporal_accounting.py` používá UTC osu a kalendářní pravidla pásma HA.
Dva přesně známé odečty stejného dne mohou dát známou spotřebu i cenu.
Při změně sazby nebo koeficientu bez mezilehlého měření je nutné výslovně
povolit odhad. Odhad rozděluje podle skutečných sekund, ne podle počtu hodin
odhadnutého z data. Denní XLSX nemění na přesný fyzický okamžik.

Stálé platby se dělí počtem kalendářních dnů měsíce. Celý den má jednu
poměrnou část i při 23/25 hodinách. U neúplného dne je časový podíl paušálu
pouze odhad; bez povolení je saldo neúplné a známá variabilní část zůstává
oddělená. Nulový doložený paušál je známá nula a nevyžaduje vymyšlené pravidlo.

Průběžný konec určuje poslední doložené měření nebo potvrzená uzavřená
faktura, nejvýše konec vybraného období. Aktuální den se automaticky nedoplní
nulovou spotřebou. Úhrady se přiřazují celému zvolenému účetnímu období,
nikoli jen dosud změřené části měsíce. Datum skutečné platby se kontroluje
samostatně; budoucí úhrada není skutečnost. Vlastní prognóza smí použít jen
profil stejného registry ID a segmentu. Starý import nepřepíše novější
snapshot jen pořadím nahrání.

Opravená faktura přebírá platby a vratky svých předchozích verzí. Vrácený
přeplatek se při následné opravě na nedoplatek připočte ke skutečnému dluhu.
Původní výsledek faktury zůstává oddělen od zbývajícího vypořádání; nejasně
spárovaná platba ani převod bez opačné protistrany fakturu neuzavřou.

Účetní revize se zveřejní až po dokončení atomického zápisu do Store,
také při vypínání HA. Úložiště v read-only režimu transakci odmítne.
Tato ochrana využívá interní zapisovač Store, proto ji pro každou podporovanou
verzi HA samostatně ověřují připravené lifecycle testy.
