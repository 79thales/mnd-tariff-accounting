# MND — zadání oprav a zjednodušení pro Sol 6.1

Datum: 16. 10. 2026. Výchozí nasazená verze při diagnostice: `0.1.0-alpha.1`.

**Aktivace: uživatel následně 16. 10. 2026 zadal „Programuj ke zadání, vydej další verzi“. Tím povolil implementaci a vydání nové verze.**

Původní stav při přípravě: **pouze připravené zadání. Uživatel výslovně požaduje nyní nic neopravovat. Tento dokument ani přiložený prompt nejsou pokynem ke spuštění implementace, nasazení nebo restartu HA.**

## 1. Cíl a přednost nových požadavků

Uprav existující integraci MND tak, aby měla jednoduchý přehled v horní liště Home Assistantu a spolehlivě načítala zálohy, úhrady a vyúčtování z Moje MND. Veškerá administrace patří do konfigurace konkrétního odběrného místa.

Toto je dodatek k `ZADANI_MND_SOL_6_1.md`, nikoli nové založení projektu. Při rozporu v uspořádání UI mají následující nové požadavky uživatele přednost:

1. „Dashboard je na boku, má být nahoře.“
2. „Dashboard je hrozně složitý.“
3. „Veškerá administrace musí být v konfiguraci odběrného místa.“
4. Zálohy a předpisy v integraci jsou prázdné, přestože na `https://moje.mnd.cz/payments` existují.
5. V dashboardu chybí horní lišta HA, doložená srovnávacími snímky.
6. Portál nabízí Export historie záloh, Export přehledu vyúčtování a Detail jednotlivého vyúčtování; tyto podklady je potřeba zahrnout do opravy načítání.
7. „Napojení na aktuální průtok a spotřebu s porovnáním vůči odečtu a predikci.“ Propojit živé senzory HA, autoritativní odečty MND a archivované předpovědi pro stejné místo a odpovídající období.

Účetní správnost, priorita odečtů MND, oddělení skutečnosti a odhadů, archiv prognóz a pravidla vydávání z původního zadání zůstávají závazné.

## 2. Podklady a skutečně zjištěný stav

### 2.1 Snímky uživatele

První snímek zobrazuje samostatnou obrazovku MND v mobilní aplikaci. Systémová lišta iOS s časem a baterií je vidět. Pod ní chybí obvyklá **horní navigační lišta Home Assistantu** s tlačítkem nabídky a přepínáním záložek. Obsah začíná logem MND, výběrem účtu a odběrného místa, velkým zeleným úvodním blokem a vlastními záložkami MND.

Na stejném snímku je prázdný výběr odběrného místa, červené chybové hlášení obsahující pouze `3`, text „Načítání…“ a neznámá revize archivu. Význam čísla `3` není ověřen; nesmí se bez důkazu označit za konkrétní HTTP kód nebo příčinu selhání.

Druhý snímek ukazuje očekávané okolí dashboardu: běžnou lištu HA, vlevo tlačítko menu, vedle něj horní záložky jako Home, Baterie 2 a Klima, vpravo další ovládání. Pod touto lištou je obsah vybraného pohledu.

Výraz „stavová lišta“ zde podle srovnání znamená především tuto nativní navigaci HA. Nekreslit vlastní náhradu systémové lišty iOS ani napodobeninu menu HA do obsahu MND.

### 2.2 Dřívější přímá kontrola HA v tomto chatu

Následující stav byl zjištěn před přípravou tohoto dokumentu; při budoucí implementaci se musí znovu ověřit:

- HA běžel na verzi `2026.10.1`; manifest MND uváděl `0.1.0-alpha.1`.
- Overview obsahoval hlavní view `/lovelace/mnd` a pět detailních subviews: spotřeba, účetnictví, prognózy, editor a historie.
- Současně byl registrován vlastní panel `/mnd-tariff-accounting` s názvem MND v levém menu. Samotná existence horního view tedy nezabránila otevření jiné obrazovky z postranního menu.
- Při pozdější čtecí kontrole byla připojena jedna konfigurace MND. Odpovědi pro odečty, spotřebu, technický detail, aktuální zálohu a smluvní dokumenty byly v archivu dostupné; stav relace byl `connected`.
- Účetní seznamy `events` a `invoices` byly prázdné. To nedokazuje, že zákazník nemá platby nebo faktury.
- Akce `portal_payments` skončila chybou `portal_request_failed`. Přesná příčina zatím není doložena.
- Současný automatický refresh načítá odečty, spotřebu, detail, zálohový ukazatel a smluvní dokumenty. Platební přehled se volá zvlášť na vyžádání a není dokončené jeho automatické převzetí do účetní evidence.

Starší `IMPLEMENTACE.md` obsahuje časově starší údaje o neprovedených živých kontrolách. Při opravě odliš historické záznamy od novějších zjištění; nepřepisuj minulý výsledek tak, jako by tehdy proběhly další testy.

### 2.3 Tlačítka portálu dodaná uživatelem

| Oblast portálu | Ovládání | Účel pro budoucí ověření |
| --- | --- | --- |
| Historie záloh | `button`, text `Export`, třídy `with-icon icon-right fw-demi btn btn-secondary` | Zjistit skutečný export historie záloh, rozsah, formát a význam sloupců. |
| Přehled vyúčtování | Stejný text `Export` a stejné třídy | Zjistit samostatný export přehledu faktur; nezaměnit s historií záloh. |
| Jednotlivé vyúčtování | `button`, text `Detail`, třídy `fw-demi btn btn-secondary btn-sm` | Zjistit detail konkrétní faktury, období, částky, vypořádání a dostupné doklady. |

Samotné HTML tlačítek nedokládá endpoint, formát souboru, úplnost exportu ani účetní význam řádků. Při případném ovládání UI rozlišuj tlačítka podle příslušné sekce a faktury; nepoužívej první globální shodu textu Export nebo Detail.

## 3. Požadované uspořádání UI

### 3.1 Přehled v horní liště HA

- Hlavní vstup uživatele je záložka **MND v existujícím Overview `/lovelace`**. Zůstává vidět nativní horní lišta HA s menu a přepínáním ostatních pohledů, stejně jako na srovnávacím snímku.
- Odstraň duplicitní běžný vstup „MND“ v levém menu. Pokud je pro konfiguraci potřebná samostatná technická cesta panelu, nesmí se vydávat za hlavní dashboard a musí být dostupná přes konfiguraci místa.
- Zkontroluj skutečnou trasu otevření z mobilní aplikace i z webu. Neřeš chybějící lištu pouhým posunutím obsahu pomocí CSS.
- Respektuj bezpečné okraje obrazovky iOS, výřez, orientaci a obvyklé scrollování HA. Obsah ani tlačítka nesmějí být zakrytá.

### 3.2 Jednoduchý běžný dashboard

Hlavní přehled má rychle odpovědět na běžné otázky: kolik plynu se spotřebovalo, jaký je poslední ověřený stav a kdy byl zjištěn, jaká je předepsaná záloha, kolik bylo skutečně uhrazeno a jak vychází náklady nebo odhad zúčtování.

- Použij několik přehledných údajů a jeden srozumitelný graf; velký reklamní úvodní blok zmenši nebo odstraň, aby na mobilu nezabíral většinu prvního zobrazení.
- Na hlavním pohledu nech pouze údaje relevantní pro vybrané místo, stručný stav aktualizace a odkazy na čtecí detaily.
- Zachovej MND odvozené barvy a srozumitelnou typografii. Používej české názvy a jednotky m³, MWh a Kč podle skutečného významu dat.
- Výběr jiného místa je běžná navigace; nastavení zdrojů, účtu či účetnictví je administrace.
- Čtecí detaily spotřeby, historie záloh, vyúčtování a prognóz mohou být v subviews. Z hlavního view se do nich uživatel musí dostat a musí se umět vrátit.
- Předpis, skutečná úhrada, odhad výsledku období a potvrzený výsledek faktury musí být jasně odlišené. Chybějící údaj zobraz jako neznámý s důvodem.
- Žádné surové JSON odpovědi, interní ID, revize archivu nebo technické formuláře v běžném přehledu. Technický detail patří do administrace/diagnostiky.

### 3.3 Veškerá administrace v konfiguraci odběrného místa

Uživatel dalším snímkem výslovně určil umístění administrace: **detail zařízení MND pro konkrétní odběrné místo v Nastavení → Zařízení a služby → Zařízení**. Jde o obrazovku s bloky „Zařízení – informace“, „Ovládací prvky“ a „Senzory“, kde jsou dnes akce Generate dashboard a Recompute accounting. Toto je závazný výchozí bod správy, nikoli pouze obecná stránka integrace nebo samostatný dashboard.

Na této stránce zpřístupni konfiguraci daného odběrného místa a jeho administrační akce. Rozsáhlejší formuláře lze otevřít odtud do konfiguračního dialogu nebo navazující obrazovky s návratem na stejné zařízení; musí již mít vybrané správné místo a účet. Uživatel nemá kvůli správě hledat boční panel ani znovu vybírat místo v obecném administračním dashboardu. Konkrétní nativní mechanismus ověř proti podporovaným verzím HA; neslibuj libovolné vložení vlastního formuláře přímo do systémového detailu zařízení, pokud je HA nepodporuje. Názvy a popisy vlastních ovládacích prvků lokalizuj do češtiny.

Do konfigurace místa přesuň zejména:

- Zdroj spotřeby, vazbu na existující senzor, kalibraci a správu měřidla.
- Ruční odečty, období, ceny, přepočtové koeficienty a počáteční zůstatek.
- Editaci záloh, skutečných úhrad, faktur, vratek a oprav účetních záznamů.
- Přihlášení/obnovu přihlášení, odhlášení, uložení či zapomenutí přístupu; vysvětli, které akce ovlivňují celý účet s více místy.
- Ruční synchronizaci, historický import a jeho průběh, zrušení nebo pokračování.
- Import/export účetního archivu, soukromé zálohy, obnovu a technickou diagnostiku.
- Generování, náhled a aktualizaci dashboardu.

Běžný dashboard nesmí trvale vykreslovat editor, importní formuláře, konfiguraci cloudu nebo generátor pod každou stránkou. Zobrazení a stažení vlastního fakturačního dokladu může zůstat čtecí funkcí detailu vyúčtování. Veškeré zápisy musí dále ověřovat oprávnění na serveru.

### 3.4 Doplnění z hlasového rozhovoru a snímků ČEZ dne 16. 10. 2026

Uživatel požaduje podobně srozumitelný přehled jako účetnictví ČEZ Dynamic Tariff.
Tři nově dodané mobilní snímky jsou vzorem kompozice a významu grafů; osobní
částky, identifikátory a samotné snímky se do veřejného projektu nepřenášejí.
Vzhled zůstává odvozený od MND. Nepřebírej elektrické tarify, HDO ani entity ČEZ.

- Hlavní stránka má ukázat hlavní ukazatele, aktuální průtok a spotřebu,
  spotřebu za srovnatelnou část loňského období a vývoj odběru plynu.
  Ostatní tabulky, doklady, úplné grafy a rozbory patří do čtecích detailů.
  Administrace nadále patří do konfigurace konkrétního odběrného místa.
- Umožni srovnání aktuálního období, topné a netopné sezóny s předchozím
  rokem. Definici sezón zobraz a nastavuj pouze v konfiguraci místa;
  přesné hranice dosud uživatel neurčil. Neprezentuj svévolně zvolené měsíce
  jako skutečně zjištěný začátek vytápění. Srovnávej shodné časové rozsahy,
  včetně dosavadní části rozběhnuté sezóny; zohledni sezónu přes přelom roku,
  přestupný den a místní čas Europe/Prague.
- Graf **Měsíční odběr podle měření HA** má mít sloupce, jednotku a zřetelně
  odlišený úplný a neúplný měsíc. Chybějící měsíc není nulová spotřeba.
  Pouhý souhrnný odečet MND neposkytuje měsíční rozpis; bez důkazu ho
  nerozděluj do měřených sloupců. Vysvětli případný rozdíl mezi součtem HA
  sloupců a fakturačním součtem potvrzeným MND.
- Graf **Náklady a zálohy za zúčtovací období** má na společné časové ose
  rozlišit známé náklady, odhad nákladů, zaplacené zálohy a plán záloh.
  Použij srozumitelnou legendu, odlišné čáry/bodování a značku Dnes.
  Skutečné platby jsou schodový průběh podle doloženého data úhrady;
  plánovaný předpis nesmí navyšovat zaplaceno. Budoucí odhad má odlišné
  zobrazení a začíná na doložené hranici, ne zpětně v již změřené historii.
- Přehled vyúčtování má ukázat období, očekávaný přeplatek/nedoplatek,
  skutečný odběr dosud, odhad odběru celkem, náklady dosud, odhad nákladů
  celkem, zaplacené zálohy a plán záloh celkem. Uveď datum poslední MND
  kotvy, návaznost HA měření a zdroj či nedostatek podkladů odhadu.
  Částku přeplatku nepočítej z neúplných nákladů nebo nepotvrzených plateb
  tak, aby působila jako potvrzené vyúčtování.
- Před návrhem sezónního/ročního odhadu načti reprezentativní historii
  a ověř její pokrytí, jednotky, reset měřidla a časové hranice. Objem v m³
  a energii v kWh/MWh drž odděleně, dokud není doložen platný přepočet.
  Nedostatek historie zobraz jako chybějící podklad, nikoli jako nulový rok
  nebo rovnou čáru odhadu. Uchovej původní prognózu pro pozdější porovnání.
- Změna musí současně upravit vykreslení, Generate dashboard, přibalenou
  šablonu i existující MND views. Mobilní grafy musí zůstat čitelné a ponechat
  nativní horní navigaci HA. Volba období smí být čtecím filtrem; nesmí
  nepozorovaně přepisovat účetní období nebo nastavení místa.

Toto doplnění zachycuje nový požadavek během dokončování alpha.2. Není
prohlášením, že alpha.2 již obsahuje všechny uvedené grafy a roční/sezónní
srovnání. Alpha.2 má jednodušší graf spotřeby a prognóz; uvedené rozšíření
se musí ověřit samostatně a vydat v nové verzi bez přepisování alpha.2.

## 4. Oprava záloh, úhrad a vyúčtování

### 4.1 Nejdříve doložit datový tok

1. Ověř problém přes existující relaci MND v HA a přes skutečnou strukturu portálu. Nevyžaduj heslo v chatu a nepřebírej stará tajemství z jiných projektů.
2. Rozliš načítání aktuální doporučené zálohy, historie předpisů, skutečných plateb a faktur. Jeden ukazatel zálohy nenahrazuje účetní knihu.
3. V aktuálním veřejném klientovi ověř volání pro `/advances`, `/payments`, `/invoices` a jejich detaily/exporty. Tyto názvy byly nalezeny ve veřejném JS; nejsou automaticky zárukou funkčního smluvního API.
4. Prověř parametry účtu a místa, filtry období, řazení, stránkování a příslušné identifikátory. Veřejný klient obsahuje u plateb také `payPeriod`, `filter` a `order`, zatímco současný klient integrace je neposílá. Je to vodítko k ověření, nikoli potvrzená příčina chyby.
5. Ověř, zda uložený `customer_id` odpovídá skutečnému účtu/místu a není prázdný. Identifikátory z odpovědí nesmí smíchat jiné místo nebo účet.
6. U exportů zjisti skutečný formát, sloupce, jednotky, časové hranice, filtry a úplnost. Teprve z doložených podkladů navrhni mapování.

Protokolové chyby mají mít neosobní kód a srozumitelné vysvětlení v administraci. Přístupy, zákaznické identity, finanční hodnoty a celé odpovědi nesmějí do logů, veřejných fixtures nebo release ZIP.

### 4.2 Přijetí do evidence

- Doplň spolehlivé načtení dostupné historie předpisů a úhrad a přehledu vyúčtování včetně detailů potřebných pro účetnictví.
- Účetní význam řádku musí vycházet z doloženého schématu/stavu. Neoznačuj předpis za uhrazenou platbu jen podle částky nebo data splatnosti.
- Zachovej částku, měnu, relevantní data, zdroj, identitu místa, stabilní identitu dokladu/události a čas získání. Pokud není známo datum skutečné úhrady nebo přiřazení k období, ponech nejistotu výslovnou.
- Podporuj částečné a vícečetné úhrady, neuhrazené předpisy, přeplatky, nedoplatky a doložené vratky podle původního zadání.
- Opakované načtení, překrývající se exporty ani kombinace přehledu a detailu nesmějí zdvojit platbu nebo fakturu. Použij stabilní identity a auditovatelnou revizi při opravě zdroje.
- Faktura, úhrada záloh a vypořádání přeplatku/nedoplatku nejsou jedna událost. Zabraň jejich dvojímu započtení.
- Nezávislá chyba jednoho zdroje nesmaže dříve platná data jiného zdroje. Ulož stav pokrytí, poslední úspěšné aktualizace a důvod částečnosti.
- Celou historii neoznačuj za úplnou podle jedné stránky nebo jednoho úspěšného exportu. Rozliš skutečně prázdný výsledek, selhání a dosud nenačtená data.
- Prověř dopad na existující ruční evidenci/importy. Migrace nesmí přepsat ručně potvrzené záznamy ani je nepozorovaně zdvojit.

## 5. Živý průtok, spotřeba a porovnání s odečtem a predikcí

### 5.1 Nastavení zdrojů pro každé odběrné místo

- V konfiguraci místa umožni vybrat existující HA senzor aktuálního průtoku a samostatně kumulativní senzor spotřebovaného objemu. Skutečné entity zatím nebyly pro tento požadavek určeny; nehádej je a nepředvyplňuj cizí entity.
- Rozliš fyzikální veličiny: průtok je například v m³/h nebo l/min, kumulativní spotřeba v m³. Ověř jednotku, význam senzoru, stavovou třídu, dostupnost a historii. Průtok nesmí být považován za stav plynoměru.
- Doložené objemové/průtokové jednotky lze převést přesným převodem; podporované převody výslovně popiš a otestuj. Energetické kWh/MWh přepočítej z objemu pouze s doloženou energetickou bází a koeficientem platným pro dané období.
- Preferuj přírůstky skutečného kumulativního senzoru pro spotřebu. Pokud existuje pouze průtok, případná časová integrace musí být samostatně vysvětlená odvozená hodnota s doloženým pokrytím; nesmí se tvářit jako fyzický odečet a mezery se nesmějí automaticky vyplňovat nulou.
- Nastavení senzoru, kalibrace, měřidla, jednotek a přepočtu patří výhradně do konfigurace místa. Dashboard zobrazuje výsledky a jejich původ.

### 5.2 Návaznost na odečet MND

- Pro příslušné místo, měřidlo a okamžik má potvrzený odečet MND přednost. Aktuální odvozený stav plynoměru = stav v kotvě + validní přírůstek kumulativního senzoru od téže kotvy.
- Kotva potřebuje časově odpovídající hodnotu místního senzoru. Pokud není dostupná, nepoužívej dnešní hodnotu jako historický počátek; vyžádej kalibraci nebo přiznej nejistotu časového přiřazení.
- Při novém odečtu MND porovnej lokálně očekávaný stav se skutečným odečtem pro stejnou hranici. Ukaž rozdíl v m³, případně v procentech s vysvětleným základem; procento při nulovém základu zůstane nedefinované.
- Nový nebo opravený odečet vytvoří auditovatelnou korekci kotvy. Uchovej původní odchylku i původ dat; korekce nesmí přidat spotřebu podruhé ani přepsat zdrojový HA senzor.
- Resety, výměny plynoměru, přejmenování entity a změny jednotek nesmějí vytvořit zápornou nebo násobnou spotřebu. Zachovej měřicí segmenty a vazbu podle registru entity.

### 5.3 Porovnání spotřeby s predikcí

- V jednoduchém přehledu zobraz aktuální průtok s jednotkou, čas/čerstvost měření, skutečně doloženou spotřebu za vybrané období a poslední odečet MND s datem. Aktuální stav odvozený ze senzoru označ jako odvozený.
- V čtecím detailu ukaž srozumitelný graf skutečnosti a předpovědi a absolutní odchylku; procentní odchylku pouze tam, kde má platný nenulový základ. Technické ladění a kalibrace sem nepatří.
- Rozliš porovnání s odečtem (měřená skutečnost) a s predikcí (odhad). Pro srovnání používej shodné časové hranice, časové pásmo a jednotky/energetickou bázi.
- Skutečnou spotřebu dosavadní části období neporovnávej jako chybu proti celé budoucí roční predikci. Pokud MND poskytuje pouze celkovou předpověď období, zobraz ji jako výhled; průběžné srovnání vyžaduje doložený průběh nebo výslovně označený model.
- Uchovej prognózy MND včetně času získání. Později porovnávej skutečnost s předpovědí uloženou před koncem hodnoceného období; nově přepsaná predikce nesmí zpětně vylepšit její historickou přesnost.
- Před návrhem vlastní prognózy načti relevantní reprezentativní historii. Ověř pokrytí, jednotky, sezonnost a časové pásmo; pokud nestačí, uveď přesně chybějící podklady a nevyráběj falešně přesný výsledek.
- Nedostupný senzor, zastaralý report nebo mezera historie nejsou nulový průtok ani nulová spotřeba. Pravidlo čerstvosti musí odpovídat skutečnému chování zdroje, včetně senzorů reportujících jen při změně.
- Pokud uživatel senzor nepřipojí, zachovej funkční režim ručních odečtů a dat MND. Průtok zůstane nedostupný, nikoli odhadnutý bez podkladů.

## 6. Chyba „3“, načítání a odolnost průvodce

- Reprodukuj stav z prvního snímku a zjisti, odkud číslo `3` přichází. Zkontroluj čtení účtů, míst a detailu a obsluhu chyby frontend/backend. Neodhaduj příčinu z jediného snímku.
- Každé načítání musí skončit zobrazením dat, srozumitelnou prázdnou obrazovkou nebo chybou s možností opakování. Nesmí současně zůstávat nekonečné „Načítání…“ a nečitelný číselný kód.
- Při změně místa/účtu nedovol, aby starší síťová odpověď přepsala novější výběr nebo aby se ukázala data jiného místa.
- Při ztrátě relace zachovej archiv a odkaž uživatele na obnovení přihlášení v konfiguraci místa/účtu.
- Prověř také dřívější scénář: při prvním přihlášení spadla mobilní aplikace a následné pokusy skončily „Nastavení již probíhá“. V tomto chatu už proběhl uživatelem schválený restart HA. Budoucí oprava má ošetřit návrat k rozpracovanému nastavení a chyby po přihlášení; nesmí bez rozmyslu vypnout ochranu proti duplicitním účtům nebo rušit jiné průvodce.

## 7. Generátor, šablona a zachování existujícího Overview

- Stejnou výslednou kompozici implementuj v živém návrhu, funkci Generate dashboard, `dashboard_template.json` a dokumentaci.
- Ověř existující `/lovelace/mnd` před generováním; nevytvářej druhý dashboard kvůli tomu, že uživatel otevřel boční panel.
- Připrav bezpečný postup aktualizace existujících MND views. Zachovej cizí pohledy, pořadí a místní úpravy. Před případným nasazením připrav zálohu a kontrolu souběžné změny, po zápisu načti skutečně uloženou konfiguraci.
- Zachovej hlavní view a čtecí detailní subviews. Dosavadní editor přesunutý do konfigurace nesmí zůstat jako druhá správa v dashboardu; staré navigační odkazy musí mít jednoznačnou náhradu.
- Komentáře a popisy musejí odpovídat skutečnému chování. U storage Lovelace výslovně respektuj, že JSON API neuchovává YAML komentáře; popisy uchovej v podporovaných polích a zdrojové šabloně/dokumentaci a ověř jejich uloženou podobu.

## 8. Akceptační scénáře

| ID | Požadovaný výsledek |
| --- | --- |
| U01 | Otevření MND v mobilní aplikaci i webu zachová nativní horní lištu HA a přístup k ostatním záložkám. |
| U02 | Hlavní MND je v horní liště existujícího Overview; běžný duplicitní vstup v levém menu není potřeba. |
| U03 | První mobilní obrazovka poskytuje užitečný přehled bez dlouhého úvodního banneru a administračních formulářů. |
| U04 | Veškerá administrace je dostupná z konfigurace jasně označeného odběrného místa; účtové operace mají popsaný dopad. |
| U05 | Čtecí detaily spotřeby, záloh, faktur a prognóz mají funkční navigaci zpět. |
| U06 | Světlý/tmavý režim, úzký mobil, výřez iOS a orientace neukryjí navigaci nebo ovládání. |
| U07 | Chyba požadavku nevykreslí samotné `3` ani nekonečné načítání; opakování se může zotavit. |
| U08 | Pozdní odpověď po změně místa nepřepíše nový výběr a nezobrazí cizí data. |
| D01 | Historie předpisů je dostupná pro stejné místo a rozsah jako ověřený portálový přehled/export. |
| D02 | Skutečné úhrady jsou od předpisů oddělené; částečná úhrada a více plateb k jednomu předpisu se započtou správně. |
| D03 | Přehled a Detail jednotlivých faktur zachovají identitu dokladu, období, částky a doložené vypořádání. |
| D04 | Obě tlačítka Export jsou rozlišena podle sekce a zpracují správné podklady. |
| D05 | Opakovaný refresh/export a kombinace exportu s detailem nevytváří duplicity. |
| D06 | Změněný nebo opravený doklad vytvoří auditovatelnou změnu; ruční evidence zůstává dohledatelná. |
| D07 | Výpadek, prázdná stránka, částečná historie a skutečně nulová hodnota jsou odlišitelné. |
| D08 | Více míst/účtů, stránkování a filtry nepromíchají data ani tiše nevynechají pokračování. |
| D09 | Vratka a vypořádání faktury nezdvojí zálohy nebo úhrady; saldo při neúplných podkladech není vydáváno za úplné. |
| L01 | Průtok a kumulativní spotřebu lze nastavit samostatně pro každé místo; jednotky a podporované převody jsou ověřené. |
| L02 | Živý přehled zobrazuje průtok a spotřebu s čerstvostí a původem; neplatné či chybějící údaje nejsou nula. |
| L03 | Nový odečet MND se porovná se stavem odvozeným ze stejné časové kotvy a opraví návaznost bez dvojí spotřeby. |
| L04 | Chybějící historická kotva, reset, mezera, výměna měřidla a přejmenování senzoru mají správné a vysvětlené chování. |
| L05 | Porovnání skutečnosti s predikcí používá stejný interval a bázi; roční výhled není přímo porovnán s neúplnou částí roku. |
| L06 | Starší prognóza se uchová a její přesnost se vyhodnotí vůči pozdější skutečnosti; nulový základ nevyrobí procentní chybu. |
| L07 | Převod m³ na energii bez doloženého koeficientu a výpočet odhadu bez dostatečné historie zůstanou výslovně neověřené. |
| R01 | Restart/reload zachová archiv a nové mapování lze bezpečně použít nad existující alpha evidencí. |
| R02 | Přerušené přihlášení a opakovaný průvodce mají srozumitelné zotavení bez duplicitního účtu. |
| G01 | Nově generovaný dashboard a přibalená šablona odpovídají zjednodušenému návrhu. |
| G02 | Aktualizace stávajících MND views zachová ostatní Overview a ověří uložený výsledek. |
| V01 | Hlavní přehled obsahuje hlavní ukazatele a srovnatelnou loňskou spotřebu; podrobnosti mají čtecí subviews. |
| V02 | Měsíční sloupce odlišují úplný/neúplný měsíc a mezeru; měsíční měření HA se nezamění se souhrnným odečtem MND. |
| V03 | Časový graf nákladů a záloh rozlišuje čtyři série, značku Dnes, skutečné datum úhrady a oddělenou budoucí predikci. |
| V04 | Přehled přeplatku a šest souhrnných hodnot zachovají rozdíl mezi doloženou skutečností, plánem a odhadem; chybějící podklady nejsou nula. |
| V05 | Roční, topné a netopné srovnání používá uvedené hranice a stejnou dosavadní část období; přelom roku a přestupný den nezkreslí výsledek. |
| V06 | Nové grafy jsou stejné v generátoru, šabloně i aktualizovaném Overview a čitelné na úzkém mobilu s navigací HA. |
| S01 | Neoprávněný uživatel nemůže zapisovat nebo stahovat soukromé dokumenty pouhým skrytím/obejitím UI. |
| S02 | Testy a release neobsahují skutečné zákaznické hodnoty, přístupy, screenshoty ani exporty. |

Počet dříve zelených testů není důkaz splnění těchto nových scénářů. Doplň smysluplné regrese pro ověřené chyby; mobilní vzhled ověř skutečným zobrazením, nikoli pouze DOM testem. Testuj deklarované minimum HA i aktuální stable zjištěný při budoucím testování, s přesně odpovídajícím pluginem.

## 9. Pracovní postup a předání při pozdější implementaci

1. Přečti `AGENTS.md`, toto zadání, původní funkční zadání, `GIT_POLITIKY_CEZ.md`, `IMPLEMENTACE.md` a aktuální kód. Zkontroluj stav pracovního stromu.
2. Připrav reprodukci a doložené mapování plateb/exportů; odděl zjištěná fakta od dosud neověřených předpokladů.
3. Uprav přehled, konfiguraci místa, chyby načítání, napojení živých senzorů a datový tok včetně migrací a sdíleného generátoru/šablony. Před srovnáváním a prognózou ověř relevantní historii.
4. Proveď odpovídající doménové, frontendové a HA testy; aktualizuj českou dokumentaci, matici výsledků a český/anglický changelog.
5. Pokud se bude vydávat, použij novou verzi, neměnný nový tag a ověřený ZIP z tagu. Respektuj Quality, HACS, Hassfest a nejprve kompletní draft. Starou alpha ani její asset nepřepisuj.
6. Před nasazením vyhodnoť aktuální uživatelskou autorizaci a předlož konkrétní ověřený výsledek. Toto zadání samo neopravňuje k aktualizaci, restartu, zveřejnění nebo zápisu do živého HA.
7. Závěrem dolož změněné chování, testy, migraci, mobilní vzhled a známá omezení. Nedokončené načítání plateb neskrývej za úspěšný import jiného typu dat.

Pracovní kořen: `H:\01.programovani\MND Tariff & Accounting for Home Assistant\`. Reference `H:\01.programovani\webdownloader\` a `H:\01.programovani\cez-dynamic-tariff\` jsou pouze ke čtení. Pro HA nejprve použij dostupný přímý konektor; pro nepokryté operace existující přímé API podle pravidel HA. Token nikdy nevypisuj ani neukládej do zdrojů.

## 10. Stav této přípravy

Při přípravě tohoto zadání byly pouze přečteny místní projektové dokumenty a vytvořeno zadání s krátkým předávacím promptem. Runtime integrace, dashboard v HA, zákaznická evidence, Git tagy a vydání se tímto krokem nemění. Screenshoty a zákaznické exporty nejsou kopírovány do veřejných zdrojů.
