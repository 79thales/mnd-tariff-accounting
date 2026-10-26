# Přehledný editor a neznámé hodnoty

## Rozdělení úloh

Od beta.2 se editor otevírá jako tři skupiny: Měření a kotel, Platby a zálohy,
Ceny a vyúčtování. Jednotlivé úlohy jsou sbalené a mají stručný popis účelu.
Otevření nebo zavření nic neodesílá. Formulář zůstává v DOM, takže sbalení
nezahodí rozepsané hodnoty. Zápis nadále provádí až jeho tlačítko Uložit.

Při potvrzeném uložení se formuláře obnoví ze serveru; při konfliktu revize
platí dosavadní pravidla evidence. Otevřená úloha zůstane otevřená i po
obnově. Nativní rozbalovací prvky lze ovládat klávesnicí. Na malém displeji
se skupiny řadí pod sebe.

## Prokliky

Rozbalovací nápověda Neznámé údaje a nastavení je v přehledu, účetním detailu
a editoru, pokud chybí místní období nebo platný průtok. Obsahuje odkazy:

- Nastavit období otevře příslušné místo, rozbalí nastavení a zaměří začátek
  období. Hodnoty nepředvyplňuje a nic automaticky neukládá.
- Zkontrolovat zdroj průtoku otevře stejný formulář u výběru průtokového
  senzoru. Chybějící údaj se nenahrazuje nulou ani prodloužením platnosti.
- Zobrazit zálohy MND otevře dodavatelskou historii záloh.

Odkaz nese konkrétní účet a místo. Nový generátor i přibalená šablona mají
stejnou adresu editoru; starší uložené karty ji bezpečně sestaví ze svých
identit. Hlavní pohled, podstránky, navigace a kompozice 4 se zachovávají.

## Proč jsou některé entity neznámé

Dodavatelské zálohy a skutečné úhrady MND sleduje vlastní čtecí přehled.
Místní účetní kniha je samostatná evidence: bez jejího výslovně zadaného
období zůstávají její saldo, platby a vyhodnocená spotřeba neznámé. Stav
needs_configuration se týká této knihy, nikoli automaticky připojení MND
nebo ztráty jeho dodavatelských záloh. Zaplacené zálohy se nemají znovu
ručně opisovat a tím započítat dvakrát.

Potvrzený výsledek faktury vyžaduje příslušný potvrzený doklad. Nepřítomný
dodavatelský stav platby není důkaz nezaplacení. Průtok zůstane neznámý,
pokud má zdroj stav unavailable/unknown, neplatnou jednotku nebo starý report;
to není důkaz nulového odběru. Přesnou příčinu ukazují atributy kvality
a stav vybraného zdrojového senzoru.

## Licence

MIT licence v kořeni, v instalačním adresáři MND a v referenci ČEZ Dynamic
Tariff má shodný text i copyright. Beta.2 doplňuje viditelný odznak a odkaz
v README; rozsah oprávnění a podmínky licence nemění.
