/* MND: přibalený panel a Lovelace karta bez externích frontend závislostí.
 * Částky se posílají jako řetězce. Oprávnění i validace jsou na serveru.
 * Každý formulář ukládá jednu revizi; neúspěch nezobrazuje jako úspěch.
 * Generátor načítá společnou backend šablonu, sám nevytváří novou kompozici.
 */
const DOMAIN = "mnd_tariff_accounting";
/* BRAND_ICON_START — generuje scripts/render_brand.cjs z brand/icon.svg. */
const BRAND_ICON = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 180 180\" fill=\"none\"> <g stroke=\"var(--mnd-mark,#2b6e33)\" stroke-width=\"13\" stroke-linejoin=\"round\" stroke-linecap=\"round\"> <path d=\"M121 54V34H137V69\"/> <path d=\"M32 81L90 29L148 81H139V145H41V81Z\"/> </g> <g fill=\"var(--mnd-mark,#2b6e33)\"> <rect x=\"103\" y=\"127\" width=\"12\" height=\"19\" rx=\"4\"/> <rect x=\"116\" y=\"115\" width=\"12\" height=\"31\" rx=\"4\"/> <rect x=\"129\" y=\"102\" width=\"12\" height=\"44\" rx=\"4\"/> </g> <path fill=\"var(--mnd-lime,#a8be32)\" d=\"M80 60C87 77 64 84 64 101C64 115 74 124 86 124C101 124 111 112 107 99C105 90 99 84 100 76C96 83 93 88 91 91C92 78 86 67 80 60Z\"/> <path fill=\"var(--mnd-mark,#2b6e33)\" d=\"M83 99C84 107 75 109 79 116C81 121 87 122 91 117C95 111 87 107 87 104L84 109Z\"/> </svg>";
/* BRAND_ICON_END */
const Base = globalThis.HTMLElement || class {};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const canonical = value => JSON.stringify(value && typeof value === "object" ?
  (Array.isArray(value) ? value.map(v => JSON.parse(canonical(v))) : Object.fromEntries(Object.keys(value).sort().map(k => [k, JSON.parse(canonical(value[k]))]))) : value);

export function mergeViews(current, views, {update=false}={}) {
  /* Jediné uložení přidává celou sadu. Cizí views a nastavení zůstanou stejné.
   * Kolize nejsou pokyn ke smazání, nahrazení ani slepému opakování zápisu. */
  if (!Array.isArray(current?.views) || current.strategy) throw new Error("overview_not_editable");
  if (new Set(views.map(v => v.path)).size !== views.length) throw new Error("duplicate_view_path");
  const collision = views.find(v => current.views.some(old => old.path === v.path));
  if (collision && !update) throw new Error("view_exists:" + collision.path);
  if(update){
    /* Nahrazujeme pouze vlastní kartu téhož účtu a místa. Cizí karty,
     * pořadí, view_layout a uživatelské vlastnosti pohledu zůstávají.
     * Nejednoznačná kolize se zastaví před jediným uložením. */
    const replacements=new Map(views.map(v=>[v.path,v]));
    const merged=current.views.map(old=>{
      const next=replacements.get(old.path);if(!next)return old;
      const card=next.cards?.[0];
      const own=old.cards?.filter(c=>c.type==="custom:mnd-accounting-card"&&c.entry_id===card?.entry_id&&c.place===card?.place)||[];
      if(own.length!==1)throw new Error("foreign_view_conflict:"+old.path);
      replacements.delete(old.path);
      return {...old,subview:next.subview??false,...(next.back_path?{back_path:next.back_path}:{}),
        cards:old.cards.map(c=>c===own[0]?{...c,...card,entities:{...c.entities,...card.entities}}:c)};
    });
    return {...current,views:[...merged,...replacements.values()]};
  }
  return {...current, views: [...current.views, ...views]};
}

export async function addViews(callWS, expected, views, options={}) {
  /* Náhled obsahuje aktuální Overview. Před zápisem kontrolujeme celou
   * konfiguraci znovu. Výpadek odpovědi vyřeší čtení, nikoli druhé přidání.
   * HA nativní save nemá CAS parametr: cizí změnu během samotného save
   * nelze zcela vyloučit; tato mez je popsána v dokumentaci. */
  const panels = await callWS({type:"get_panels"});
  if (panels.lovelace?.config?.mode !== "storage") throw new Error("overview_not_storage");
  const latest = await callWS({type:"lovelace/config"});
  if (canonical(latest) !== canonical(expected)) throw new Error("overview_changed");
  const merged = mergeViews(latest, views, options);
  try {
    await callWS({type:"lovelace/config/save", config:merged});
  } catch {
    const saved = await callWS({type:"lovelace/config"});
    if (canonical(saved) !== canonical(merged)) throw new Error("save_unconfirmed");
  }
  const verified = await callWS({type:"lovelace/config"});
  if (canonical(verified) !== canonical(merged)) throw new Error("save_changed_after_write");
  return {path: views[0].path};
}

/* Vlastní CSS je odvozené od veřejného Moje MND, nikoli jeho kopie.
 * Paleta, typografie a rozestupy viz docs/VZHLED_MND.md. Písmo Avenir se
 * využije jen pokud je místně dostupné; fonty a CSS MND se nestahují za běhu.
 * Tmavý režim určuje HA hass.themes.darkMode, nikoli nastavení OS. */
export const CSS = `
:host{--mnd-mark:#2b6e33;--mnd-green:#2b6e33;--mnd-lime:#a8be32;--mnd-surface:#fff;--mnd-bg:#f6f8f6;--mnd-text:#2e332e;--mnd-muted:#545c58;--mnd-border:#c0d1c0;--mnd-soft:#eef4e9;--mnd-danger:#b82025;--mnd-actual:#2b6e33;--mnd-estimate:#a8be32;--mnd-focus:#2b6e33;display:block;color:var(--mnd-text);font:15px/1.5 Avenir,"Avenir Next",Arial,sans-serif;background:var(--mnd-bg);color-scheme:light}
:host([dark]){--mnd-mark:#d7e9d2;--mnd-surface:#202a24;--mnd-bg:#17201b;--mnd-text:#f0f4f0;--mnd-muted:#c1ccc4;--mnd-border:#506957;--mnd-soft:#2b3e2b;--mnd-danger:#ffaaa8;--mnd-actual:#76bb7c;--mnd-estimate:#c1d85f;--mnd-focus:#a8be32;color-scheme:dark}
*{box-sizing:border-box}main{max-width:1320px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap;padding:4px 0 22px}.brand{display:flex;align-items:center;gap:14px}.brand strong{display:block;font-size:24px;color:var(--mnd-green);letter-spacing:-.7px}:host([dark]) .brand strong{color:var(--mnd-estimate)}.brand small{color:var(--mnd-muted);font-size:13px}.mark{height:48px;width:48px;display:grid;place-items:center;color:var(--mnd-green);background:var(--mnd-soft);border-radius:8px}.mark ha-icon{--mdc-icon-size:30px}.account-picker{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.account-picker label{margin:0;min-width:160px}
.hero{padding:26px 30px;margin:0 0 18px;border-radius:8px;background:linear-gradient(110deg,#2b6e33 30%,#1b5c22 75%,#a8be32 160%);color:#fff;position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-60px;top:-100px;width:260px;height:260px;border:36px solid #a8be3233;border-radius:50%;pointer-events:none}.hero .eyebrow{font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#e2ebcb;margin:0 0 6px}.hero h1{font-size:30px;line-height:1.3;margin:0 0 8px}.hero p{position:relative;z-index:1;max-width:850px;margin:0;color:#fff}.hero .hero-meta{margin-top:12px;font-size:13px;color:#e2ebcb}
h2{font-size:21px;line-height:1.35;margin:0 0 18px}h3{font-size:18px;margin:0 0 14px}p{margin:8px 0}.muted{color:var(--mnd-muted)}nav{display:flex;gap:8px;border-bottom:1px solid var(--mnd-border);margin:0 0 24px;overflow-x:auto;overscroll-behavior:contain}button,input,select,textarea{font:inherit}button{cursor:pointer;border:1px solid var(--mnd-border);background:var(--mnd-surface);color:var(--mnd-text);border-radius:8px;padding:10px 20px;font-weight:600;min-height:44px;transition:background .15s,border-color .15s}button:hover{border-color:var(--mnd-green);background:var(--mnd-soft)}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid var(--mnd-focus);outline-offset:3px}nav button,nav a{border:0;border-bottom:3px solid transparent;border-radius:0;background:transparent;padding:14px 16px;white-space:nowrap;color:var(--mnd-muted);font-weight:600;text-decoration:none;min-height:48px}nav .active{color:var(--mnd-text);border-bottom-color:var(--mnd-lime)}button.primary{background:var(--mnd-green);color:#fff;border-color:var(--mnd-green)}button.primary:hover{background:#1b5c22}button:disabled{opacity:.5;cursor:wait}a{color:var(--mnd-green)}:host([dark]) a{color:var(--mnd-estimate)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-bottom:24px}.card,section,form{border:1px solid var(--mnd-border);border-radius:8px;background:var(--mnd-surface);padding:24px;min-width:0;box-shadow:0 8px 26px #2e332e06}.card{position:relative;overflow:hidden;border-top:3px solid var(--mnd-green)}.card:nth-child(3n){border-top-color:var(--mnd-lime)}section{margin-bottom:22px}.value{font-size:30px;font-weight:600;letter-spacing:-.8px;margin-top:12px;color:var(--mnd-text)}.value small{font-size:16px;font-weight:400;letter-spacing:0}.label{font-size:14px;color:var(--mnd-muted)}.metric{cursor:pointer}.metric:hover{border-color:var(--mnd-green)}.notice{padding:16px 20px;background:var(--mnd-soft);border-left:4px solid var(--mnd-lime);border-radius:0 8px 8px 0;margin:18px 0}.error{border-left-color:var(--mnd-danger);color:var(--mnd-danger)}.forms{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:22px;align-items:start}label{display:block;margin:12px 0 6px;color:var(--mnd-muted);font-size:14px}input,select,textarea{width:100%;padding:11px 12px;border:1px solid var(--mnd-border);border-radius:4px;background:var(--mnd-surface);color:var(--mnd-text);min-height:46px;margin-top:4px}input[type=checkbox]{width:18px;height:18px;min-height:0;vertical-align:middle;margin:0 6px 2px 0;accent-color:var(--mnd-green)}textarea{font:12px/1.5 monospace;min-height:240px}form button{margin-top:18px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:14px 12px;border-bottom:1px solid var(--mnd-border);white-space:nowrap}th{color:var(--mnd-muted);background:var(--mnd-bg);font-weight:600}td input{min-width:130px}tbody tr:hover{background:var(--mnd-soft)}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row>*{flex:1;min-width:140px}.row button{flex:0 0 auto}.tag{display:inline-block;font-size:12px;font-weight:600;padding:5px 10px;border-radius:4px;background:var(--mnd-soft)}svg{width:100%;height:auto}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:13px}.dot{display:inline-block;width:12px;height:12px;margin-right:7px;background:var(--mnd-actual)}.dot.estimated{background:var(--mnd-estimate)}.dot.future{border:1px dashed var(--mnd-actual);background:transparent}.no-data{padding:40px 15px;text-align:center;color:var(--mnd-muted)}footer{font-size:12px;padding:8px 0 20px}.connection{font-size:13px;display:flex;gap:12px;flex-wrap:wrap}
@media(max-width:650px){main{padding:14px}header{gap:16px;padding-bottom:16px}.brand strong{font-size:21px}.account-picker{width:100%}.account-picker label{flex:1;min-width:140px}.hero{padding:22px 20px}.hero h1{font-size:25px}.value{font-size:27px}nav{margin-bottom:18px}nav button,nav a{padding:12px}section,.card,form{padding:18px}.grid{gap:12px;grid-template-columns:repeat(auto-fit,minmax(155px,1fr))}.hero:after{opacity:.5}th,td{padding:12px 10px}}
.billing-summary table{table-layout:fixed}.billing-summary td:first-child,.billing-summary th:first-child{width:64%;white-space:normal}.billing-summary td:last-child{font-weight:600;text-align:right;white-space:nowrap}.billing-summary .period{font-weight:600}.balance-value{font-size:34px;font-weight:700;letter-spacing:-.6px;margin:6px 0 22px}.billing-plot{width:100%;display:block;overflow:visible}.billing-plot text{font:19px Avenir,Arial,sans-serif;fill:var(--mnd-muted)}.billing-plot circle:focus,.billing-plot g:focus{outline:3px solid var(--mnd-focus);outline-offset:3px}.chart-legend{display:flex;justify-content:center;gap:12px 18px;flex-wrap:wrap;font-size:13px;margin:14px 0}.chart-legend span{display:inline-flex;align-items:center;gap:7px}.chart-legend i{display:inline-block;width:12px;height:12px;border-radius:50%}.axis-unit{font-size:13px;margin:0;color:var(--mnd-muted)}.metric.value{background:transparent;border:0;padding:0;text-align:left;min-height:44px;box-shadow:none;max-width:100%}.metric.value small{white-space:nowrap}.billing-summary .muted,.billing-chart .muted{font-size:13px;line-height:1.55}.billing-summary h3{margin:16px 0 4px}
@media(max-width:650px){.billing-plot text{font-size:22px}.billing-summary td,.billing-summary th{padding:12px 6px}.billing-summary td:last-child{font-size:15px}.balance-value{font-size:31px}.metric.value{font-size:25px}.grid .label{font-size:13px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}`;

const TABS = {overview:"Přehled",readings:"Spotřeba",accounting:"Účetnictví",forecasts:"Prognózy",editor:"Editor",history:"Historie a doklady",dashboard:"Generate dashboard"};
const EN = {"Přehled":"Overview","Spotřeba":"Consumption","Účetnictví":"Accounting","Prognózy":"Forecasts","Editor":"Editor","Historie a doklady":"History and documents","Historie odečtů":"Reading history","Stav podkladů":"Data quality","Aktuální odvozený stav":"Current derived meter reading","Poslední odečet MND":"Last MND reading","Známé náklady":"Known costs","Skutečně zaplaceno":"Actual payments","Průběžné saldo":"Running balance","Spotřeba vyhodnoceného období":"Evaluated period consumption","Platby a předpisy":"Payments and prescriptions","Vyúčtování":"Invoices","Cenové úseky":"Tariff periods","Historie prognóz":"Forecast history","Uložený výhled MND":"Saved MND forecast","Období a zdroj měření":"Period and measurement source","Ruční fyzický odečet":"Manual physical reading","Platba / předpis / vratka":"Payment / prescription / refund","Smluvní cenový úsek":"Contract tariff period","Převod objemu na energii":"Volume to energy conversion","Potvrzení vyúčtování":"Confirm invoice","Souběžná kalibrace senzoru":"Synchronous sensor calibration","Uložit do evidence HA":"Save to HA records","Název místa":"Supply point name","Začátek období":"Period start","Konec období (výlučně)":"Period end (exclusive)","Počáteční kredit / dluh (Kč)":"Opening credit / debit (CZK)","Úplnost skutečných úhrad potvrzena":"Actual payment completeness confirmed","Povolit odhad rozdělení podle dnů":"Allow estimated allocation by days","Místní zdroj":"Local source","Kumulativní senzor m³":"Cumulative m³ sensor","Identita segmentu / plynoměru":"Segment / meter identity","Číslo plynoměru":"Meter number","Kumulativní stav (m³)":"Cumulative reading (m³)","Skutečný čas ISO 8601 včetně pásma":"Actual ISO 8601 time including offset","Poznámka":"Note","Druh":"Role","Částka Kč":"Amount CZK","Datum události":"Event date","Od (včetně)":"From (inclusive)","Do (bez tohoto dne)":"To (exclusive)","Název":"Name","Obchodní Kč/MWh":"Commodity CZK/MWh","Ostatní variabilní Kč/MWh":"Other variable CZK/MWh","Stálé Kč/měsíc":"Fixed CZK/month","Ceny zahrnují DPH":"Prices include VAT","DPH % u cen bez DPH":"VAT % for net prices","Všechny složky doloženy":"All components documented","Potvrzen poměr neúplného měsíce podle dnů":"Calendar-day proration confirmed","Role":"Role","Zdroj ceny":"Price evidence","Orientační koeficient (odhad)":"Indicative coefficient (estimate)","Faktura / zdroj koeficientu":"Invoice / conversion evidence","Číslo dokladu":"Invoice number","Celkové náklady Kč":"Total cost CZK","Výsledek Kč: + přeplatek / − nedoplatek":"Result CZK: + surplus / − deficit","Potvrzuji opsané údaje z dokladu":"I confirm the transcribed invoice values","Registrovaný účet":"Configured account","Vyberte účet":"Select account","Měsíční zálohy":"Monthly advances","Měsíc":"Month","Předpis Kč":"Prescribed CZK","Uhrazeno Kč":"Paid CZK","Datum skutečné úhrady":"Actual payment date","Uložit celé období":"Save the entire period","Obnovit MND":"Refresh MND","Pokračovat v historii MND":"Continue MND history","Pozastavit úlohu":"Pause task","Historie senzoru HA":"HA sensor history","Načíst historii senzoru":"Read sensor history","Záloha ZIP včetně dokladů":"ZIP backup including documents","Stáhnout účetní archiv JSON":"Download accounting JSON","Export odečtů CSV":"Export readings as CSV","Ověřit odchylku":"Evaluate forecast difference","Porovnat uložený výhled s fakturou":"Compare saved forecast with invoice","Potvrzuji shodné hranice a energetickou bázi":"I confirm matching boundaries and energy basis","Vlastní sezonní odhad":"Local seasonal forecast","Vypočítat sezonní odhad":"Calculate seasonal forecast","needs_configuration":"Configuration required","incomplete":"Incomplete","complete":"Complete","not_connected":"Not connected","anchor_time_unpaired":"The anchor has no synchronous sensor sample","calibration_required":"Calibration required","sensor_reset":"Sensor reset detected","sensor_gap":"Measurement continuity interrupted","state_at_date":"Manual reading at its recorded date","derived_state":"Derived from the anchor and valid sensor increments"};
/* Zdrojové popisy dokladů a uživatelské texty se nepřekládají. Překlad
 * mění pouze popisky aplikace, nikdy hodnoty options posílané serveru. */
Object.assign(EN,{
  "Odběrné místo":"Supply point","Plyn · moje domácnost":"Gas · my home","Vaše energie pod kontrolou":"Your energy at a glance",
  "Spotřeba, zálohy a vyúčtování na jednom místě":"Consumption, advances and invoices in one place",
  "Odečet MND je kotvou pro navazující měření":"MND readings anchor subsequent measurements",
  "Komunitní integrace pro Home Assistant · revize archivu":"Community integration for Home Assistant · archive revision",
  "Kč":"CZK","neznámé":"unknown","nepřipojeno":"not connected","Datum odečtu MND:":"MND reading date:","Navazující měření:":"Subsequent measurement:",
  "Průběžné saldo je místní výpočet. Potvrzené vyúčtování a zbývající vypořádání najdete v Účetnictví.":"The running balance is calculated locally. Confirmed invoices and outstanding settlements are shown in Accounting.",
  "Spotřeba a prognózy MND":"MND consumption and forecasts","Dosud nebyl importován snapshot prognózy.":"No forecast snapshot has been imported yet.",
  "Přesný čas":"Exact time","Plynoměr":"Gas meter","Den":"Day","Zdroj":"Source","Metoda":"Method","Žádné uložené záznamy.":"No archived records.",
  "Předpis a předpokládaná platba nezvyšují skutečně zaplacenou částku.":"Prescribed and assumed payments do not increase actual payments.",
  "Datum":"Date","Ověření":"Verification","Doklad":"Document","Do výlučně":"To exclusive","Náklad Kč":"Cost CZK","Dokladové saldo Kč":"Invoice result CZK","Ostatní Kč/MWh":"Other CZK/MWh","Kč/měsíc":"CZK/month","Obchodní Kč/MWh":"Commodity CZK/MWh",
  "Starší předpověď zůstává uložená. Přesnost lze hodnotit až za shodné dokončené období a doložené měření.":"Earlier forecasts remain archived. Accuracy requires the same completed period and documented actual measurement.",
  "Používají se přímo MWh dodavatele; žádný převod m³ se nedopočítává. Potvrďte shodný význam a hranice období.":"Uses supplier-reported MWh directly. Confirm matching period boundaries and meaning; no m³ conversion is inferred.",
  "Období snapshotu":"Snapshot period","Faktura":"Invoice",
  "Zápisy jsou místní evidence v HA. Časy odečtů zadávejte s výslovným UTC posunem. Pole bez údaje ponechte prázdná.":"Changes affect local HA records. Enter reading times with an explicit UTC offset. Leave unknown fields empty.",
  "Prázdné pole zachová údaj. Předpis a skutečná úhrada se ukládají odděleně; vyšší úhrada je povolena.":"Empty fields preserve existing values. Prescribed and actual payments are separate; overpayments are allowed.",
  "Použít stejný předpis pro měsíce":"Use the same prescribed amount for all months","Nevybráno":"Not selected",
  "Segment (prázdné = číslo plynoměru)":"Segment (empty = meter number)","ID opravovaného odečtu (volitelné)":"Superseded reading ID (optional)",
  "ID faktury (volitelné)":"Invoice ID (optional)","ID protistrany převodu (volitelné)":"Counterpart transfer ID (optional)","ID nahrazovaného záznamu (volitelné)":"Superseded record ID (optional)",
  "ID nahrazované sazby (volitelné)":"Superseded tariff ID (optional)","ID nahrazovaného koeficientu (volitelné)":"Superseded conversion ID (optional)",
  "Fakturované m³ (volitelné)":"Invoiced m³ (optional)","Fakturované MWh (volitelné)":"Invoiced MWh (optional)","Přijaté zálohy na faktuře Kč (volitelné)":"Advances listed on invoice CZK (optional)",
  "ID přiloženého dokumentu (volitelné)":"Attached document ID (optional)","ID opravované faktury (volitelné)":"Superseded invoice ID (optional)","Segment / plynoměr":"Segment / gas meter",
  "Souběžný čas ISO 8601 s pásmem":"Synchronous ISO 8601 time with offset","Fyzický stav m³":"Physical reading m³","Stav senzoru m³ ve stejný okamžik":"Sensor reading m³ at the same instant",
  "Import odečtů, faktury a účetního archivu":"Import readings, invoice or accounting archive",
  "XLSX / JSON / ZIP nejvýše 64 MiB; PDF nejvýše 8 MiB. Před importem ověříme identitu vybraného místa.":"XLSX / JSON / ZIP up to 64 MiB; PDF up to 8 MiB. The selected supply point identity is checked before import.",
  "Soukromý export":"Private export","Doklady":"Documents","Audit":"Audit","Žádné uložené originály.":"No archived original documents.","Čas":"Time","Akce":"Action","Oblast":"Section",
  "Připojení a historie":"Connection and history","Stav úlohy:":"Task status:","Záloha a export":"Backup and export","Stáhnout zálohu ZIP":"Download ZIP backup",
  "Moje MND · smlouva a zákaznické údaje":"Moje MND · contract and customer details",
  "Profil a platební přehled se načtou až na vyžádání. Jejich zobrazení nevytváří skutečnou úhradu v účetnictví HA.":"Profile and payment overview are loaded on request. Displaying them does not create actual HA accounting payments.",
  "Zákaznický profil":"Customer profile","Platební přehled MND":"MND payment overview","Smluvní dokumenty":"Contract documents",
  "Dokument se ověří proti aktuálnímu seznamu MND a uloží jako soukromý originál.":"Documents are verified against the current MND list and archived privately.",
  "Odhlásit relaci MND":"Sign out of MND","Odhlásit a zapomenout uložený přístup":"Sign out and forget stored credentials","Přihlášení a nastavení integrace v HA":"Sign in and configure the HA integration",
  "Přidat do horní lišty Overview":"Add views to the Overview tab bar","Jednoduchý přehled a čtecí detaily. Uložení aktualizuje i již vytvořenou MND šablonu a zachová cizí karty. Záloha Overview se před uložením stáhne do vašeho zařízení.":"Main overview and five detail subviews. The preview uses actual registry entities.",
  "Vytvořit náhled":"Create preview","Náhled skutečných dat":"Preview actual data","Zkontrolovat soubor":"Check file","Potvrdit import tohoto souboru":"Confirm import of this file",
  "Částky z PDF jsou pouze návrh. Doklad nejprve uložte a účetní údaje samostatně potvrďte v Editoru.":"PDF amounts are only proposals. Save the document, then confirm accounting values separately in the Editor.",
  "Předpis zálohy MND":"MND current advance","Doporučená záloha MND":"MND recommended advance","Číslo smlouvy":"Contract number","Typ měření":"Measurement type","Roční spotřeba MND (MWh)":"MND annual consumption (MWh)","Převod kreditu do dalšího období":"Transfer credit to another period","Cílové období od":"Target period from","Cílové období do výlučně":"Target period to exclusive","Export odečtů pro interval":"Export readings for a period","Oba dny včetně, nejvýše 366 dní na jeden export. Originál se uloží spolu s odečty.":"Both dates inclusive, up to 366 days per export. Original file and readings are archived together.","Od":"From","Do včetně":"To inclusive","Stáhnout a přijmout odečty MND":"Download and import MND readings","Porovnat s fakturou":"Compare with invoice","Porovnat s dokončeným měřením":"Compare with completed measurement","Význam":"Meaning","Hodnota":"Value","Jednotka":"Unit","Kontext dokladu":"Document context","Podle odečtů":"Actual readings","Odhad minulosti":"Estimated past","Odhad budoucnosti":"Estimated future",
  "Aktuální průtok":"Current flow","Senzor aktuálního průtoku":"Current flow sensor","Platnost reportu průtoku (sekundy)":"Flow report validity (seconds)","Konfigurace odběrného místa":"Supply point configuration","Historie záloh MND":"MND advance history","Vyúčtování MND":"MND invoices","Skutečně zaúčtované úhrady dokladu":"Actual payments allocated to this document","Otevřít zařízení MND v Nastavení":"Open the MND device in Settings","← Zpět na zařízení MND":"← Back to MND device","Zkusit znovu":"Try again","Splatnost":"Due date","Zbývá Kč":"Outstanding CZK","Datum úhrady":"Payment date","Částečné podklady":"Partial evidence",
  "Stáhnout fragment views":"Download views fragment","Přidat do horní lišty":"Add to tab bar","Vypořádání faktur":"Invoice settlements","ID faktury":"Invoice ID","Původní výsledek Kč":"Original result CZK","Zbývá uhradit / vrátit Kč":"Outstanding payment / refund CZK","Vyšší vypořádání Kč":"Excess settlement CZK"
});
Object.assign(EN,{
  "Poměr stálých měsíčních plateb podle dnů je orientační. Rozhodující je originální vyúčtování.": "Fixed monthly charges are prorated by calendar days as an estimate. The original invoice is authoritative.",
  "Účetní období MND": "MND billing period",
  "Přehled čeká na načtení období a podkladů MND. Neznámé částky nejsou nulové.": "Waiting for the MND billing period and evidence. Unknown amounts are not zero.",
  "Výsledek originálního vyúčtování": "Original invoice result",
  "Odhad vyúčtování čeká na podklady": "Billing estimate awaits evidence",
  "Očekávaný přeplatek": "Expected surplus",
  "Očekávaný nedoplatek": "Expected deficit",
  "Skutečný odběr MND dosud": "MND actual consumption to date",
  "Odhad odběru celkem": "Estimated total consumption",
  "Známé náklady k odečtu": "Known costs at the reading",
  "Doložená část nákladů": "Documented portion of costs",
  "Odhad nákladů celkem": "Estimated total costs",
  "Uhrazené zálohy": "Paid advances",
  "Plán záloh celkem": "Total planned advances",
  "Za účetní období": "For the billing period",
  "Uhrazené zálohy jsou skutečné platby z MND, nikoli předepsané částky. Známé náklady jsou výpočet z doložené ceny a odběru; originální vyúčtování má přednost.": "Paid advances are actual MND payments, separate from prescriptions. Known costs use documented prices and consumption; original invoices take precedence.",
  "Spotřeba MND k odečtu": "MND consumption at the reading",
  "Novější měření HA je samostatně v měsíčních sloupcích.": "Newer HA measurements appear separately in the monthly bars.",
  "Náklady čekají na ověření originálního ceníku. Platby už jsou dostupné.": "Costs await verification of the original price list. Payments are available.",
  "Odhad používá prognózu MND a doložený ceník. Budoucí regulované ceny zatím vycházejí z posledních známých sazeb.": "The estimate uses the MND forecast and documented price list. Future regulated prices assume the latest known rates.",
  "Historie úhrad není úplná. Zobrazený součet obsahuje jen doložené platby.": "Payment history is incomplete. The sum includes documented payments only.",
  "Originální faktura má přednost. Zbytek nákladů zatím nelze bezpečně oddělit.": "The original invoice takes precedence. Remaining costs cannot yet be separated reliably.",
  "Období faktury přesahuje vybrané účetní období. Částku nerozdělujeme odhadem.": "The invoice crosses the selected billing period. Its amount is not prorated.",
  "Náklady a zálohy za účetní období": "Costs and advances for the billing period",
  "Odhad nákladů": "Estimated costs",
  "Zaplacené zálohy": "Paid advances",
  "Plán záloh": "Planned advances",
  "Dnes": "Today",
  "údaje chybí": "data missing",
  "Údaje chybí": "Data missing",
  "Čárkovaná spojnice ukazuje celkový výhled MND, nikoli doloženou měsíční předpověď. Platby mají skutečné datum úhrady. Předpis není platba.": "The dashed line illustrates the MND total forecast; it is not a documented monthly forecast. Payments use actual receipt dates. Prescriptions are separate.",
  "Měsíční odběr podle měření HA": "Monthly consumption measured by HA",
  "Úplný měsíc": "Complete month",
  "Neúplný měsíc": "Partial month",
  "úplný měsíc": "complete month",
  "neúplný měsíc": "partial month",
  "Oranžové sloupce obsahují pouze známou část měsíce. Chybějící data nejsou nulová spotřeba. Celkový odběr pro vyúčtování přebírá MND; jeho souhrn nemusí odpovídat součtu sloupců HA.": "Orange bars contain the known portion of each month. Missing data is not zero consumption. Billing uses the MND consumption total, which may differ from the HA bars.",
  "Naměřeno HA v období": "HA measurement in this period",
  "Odečet MND:": "MND reading:",
  "Průtok:": "Flow:",
  "aktuální": "current",
  "zastaralý report": "stale report",
  "nedostupný": "unavailable",
  "Historický senzor objemu nebo pulsů": "Historical volume or pulse sensor",
  "Objem jednoho pulsu (m³)": "Volume per pulse (m³)"
});
const number = (value, unit="",locale="cs-CZ") => value === null || value === undefined ? "—" : `${new Intl.NumberFormat(locale,{maximumFractionDigits:3}).format(value)} ${unit}`;
const table = (rows, columns) => `<div class="scroll"><table><thead><tr>${columns.map(([,label])=>`<th>${esc(label)}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(([key])=>`<td>${esc(r[key] ?? "—")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length}">Žádné uložené záznamy.</td></tr>`}</tbody></table></div>`;
const field = (name,label,type="text",options) => ({name,label,type,options});
const COMMON_PERIOD = [field("from","Od (včetně)","date"),field("to","Do (bez tohoto dne)","date")];
const FORMS = [
  {section:"settings",title:"Období a zdroj měření",fields:[field("name","Název místa"),field("period_from","Začátek období","date"),field("period_to","Konec období (výlučně)","date"),field("opening_credit","Počáteční kredit / dluh (Kč)","decimal"),field("payments_complete","Úplnost skutečných úhrad potvrzena","checkbox"),field("allow_linear","Povolit odhad rozdělení podle dnů","checkbox"),field("source_mode","Místní zdroj","select",["manual","sensor"]),field("source_entity","Kumulativní senzor m³","sensor"),field("flow_entity","Senzor aktuálního průtoku","flow"),field("flow_max_age","Platnost reportu průtoku (sekundy)","decimal"),field("history_source_entity","Historický senzor objemu nebo pulsů","history"),field("history_unit_m3","Objem jednoho pulsu (m³)","decimal"),field("segment","Identita segmentu / plynoměru")]},
  {section:"readings",title:"Ruční fyzický odečet",fields:[field("meter","Číslo plynoměru"),field("segment","Segment (prázdné = číslo plynoměru)"),field("value","Kumulativní stav (m³)","decimal"),field("observed_at","Skutečný čas ISO 8601 včetně pásma"),field("note","Poznámka"),field("supersedes","ID opravovaného odečtu (volitelné)")]},
  {section:"events",title:"Platba / předpis / vratka",fields:[field("role","Druh","select",["payment","prescribed","assumed_paid","refund","credit","debit","transfer_in","transfer_out"]),field("amount","Částka Kč","decimal"),field("date","Datum události","date"),...COMMON_PERIOD,field("invoice","ID faktury (volitelné)"),field("counterpart","ID protistrany převodu (volitelné)"),field("supersedes","ID nahrazovaného záznamu (volitelné)"),field("note","Poznámka")]},
  {section:"transfer",title:"Převod kreditu do dalšího období",fields:[field("amount","Částka Kč","decimal"),field("date","Datum události","date"),...COMMON_PERIOD,field("target_from","Cílové období od","date"),field("target_to","Cílové období do výlučně","date"),field("invoice","ID faktury (volitelné)"),field("note","Poznámka")]},
  {section:"tariffs",title:"Smluvní cenový úsek",fields:[field("name","Název"),...COMMON_PERIOD,field("commodity","Obchodní Kč/MWh","decimal"),field("other","Ostatní variabilní Kč/MWh","decimal"),field("fixed","Stálé Kč/měsíc","decimal"),field("includes_vat","Ceny zahrnují DPH","checkbox"),field("vat_percent","DPH % u cen bez DPH","decimal"),field("all_components_known","Všechny složky doloženy","checkbox"),field("prorate_fixed","Potvrzen poměr neúplného měsíce podle dnů","checkbox"),field("role","Role","select",["current","subsequent","alternative"]),field("evidence","Zdroj ceny"),field("supersedes","ID nahrazované sazby (volitelné)")]},
  {section:"conversions",title:"Převod objemu na energii",fields:[...COMMON_PERIOD,field("kwh_per_m3","kWh/m³","decimal"),field("estimated","Orientační koeficient (odhad)","checkbox"),field("evidence","Faktura / zdroj koeficientu"),field("supersedes","ID nahrazovaného koeficientu (volitelné)")]},
  {section:"invoices",title:"Potvrzení vyúčtování",fields:[field("number","Číslo dokladu"),...COMMON_PERIOD,field("cost","Celkové náklady Kč","decimal"),field("result","Výsledek Kč: + přeplatek / − nedoplatek","decimal"),field("volume_m3","Fakturované m³ (volitelné)","decimal"),field("energy_mwh","Fakturované MWh (volitelné)","decimal"),field("included_advances","Přijaté zálohy na faktuře Kč (volitelné)","decimal"),field("artifact","ID přiloženého dokumentu (volitelné)"),field("supersedes","ID opravované faktury (volitelné)"),field("confirmed","Potvrzuji opsané údaje z dokladu","checkbox")]},
  {section:"calibration",title:"Souběžná kalibrace senzoru",fields:[field("segment","Segment / plynoměr"),field("at","Souběžný čas ISO 8601 s pásmem"),field("physical","Fyzický stav m³","decimal"),field("sensor","Stav senzoru m³ ve stejný okamžik","decimal"),field("note","Poznámka")]}
];

class MndSurface extends Base {
  constructor(){super();this._admin=false;if(this.attachShadow)this.attachShadow({mode:"open"});this._tab="overview";this._message="";this._busy=false;this._request=0;}
  set hass(value){this._hass=value;this.toggleAttribute?.("dark",Boolean(value?.themes?.darkMode));if(!this._loaded && this.isConnected)this.load();}
  connectedCallback(){if(this._hass && !this._loaded)this.load();if(!this._timer)this._timer=setInterval(()=>{if(!this._busy&&this._tab!=="editor"&&!this.shadowRoot.activeElement)this.load();},30000);}
  disconnectedCallback(){this._request++;this._loaded=false;clearInterval(this._timer);this._timer=null;}
  number(value,unit=""){return number(value,(this._hass?.language||"cs").startsWith("en")&&unit==="Kč"?"CZK":unit,(this._hass?.language||"cs").startsWith("en")?"en-GB":"cs-CZ");}
  async command(action,payload={}){
    /* Odpověď původního místa se po přepnutí nesmí vložit do nového formuláře.
     * Odeslaná mutace stále patří původnímu explicitnímu entry/place. */
    const entry=this._entry,place=this._place;
    let timer;let result;try{result=await Promise.race([this._hass.callWS({type:DOMAIN+"/command",action,entry_id:entry,place,payload}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error("request_timeout")),45000);})]);}finally{clearTimeout(timer);}
    if(action!=="entries"&&(entry!==this._entry||place!==this._place))throw new Error("selection_changed");
    return result;
  }
  async load({force=false}={}){
    if(!this._hass || (this._loading&&!force))return;
    const request=++this._request;this._loading=request;
    try{
      const entries=await this.command("entries");if(request!==this._request)return;
      const query=new URLSearchParams(globalThis.location?.search);
      this._entries=entries;this._entry=this._config?.entry_id || this._entry || query.get("entry_id") || (entries.length===1?entries[0].id:null);
      if(!this._entry){this._loaded=true;this._message=entries.length?"Vyberte účet":"Nejprve přidejte integraci v Nastavení → Zařízení a služby.";this.render();return;}
      const summary=await this.command("summary");if(request!==this._request)return;
      this._summary=summary;this._place=this._config?.place || this._place || query.get("place") || summary.places[0]?.id;
      if(!this._queryApplied){this._tab=this._config?.tab || query.get("tab") || this._tab;this._queryApplied=true;}
      if(this._place)this._detail=await this.command("detail");if(request!==this._request)return;
      this._loaded=true;this._failed=false;this._message="";this.render();
    }catch(error){if(request!==this._request)return;this._failed=true;this._loaded=true;this._message=this.errorText(error);this.render();}
    finally{if(this._loading===request)this._loading=false;}
  }
  errorText(error){
    /* Číslo z odmítnutého WS požadavku samo nevysvětluje chybu. Nezobrazujeme
     * surovou odpověď ani zákaznické hodnoty; opakování zůstává dostupné. */
    const code=String(error?.code||error?.message||"request_failed");
    const labels={request_timeout:"Požadavek překročil časový limit.",entry_not_loaded:"Integrace není načtena. Ověřte její stav v Nastavení.",portal_auth_required:"Přihlášení MND vypršelo. Obnovte je v konfiguraci místa.",selection_changed:"Výběr odběrného místa se změnil.",portal_http_400:"MND odmítlo parametry požadavku.",portal_unavailable:"Portál MND není dostupný."};
    return labels[code]||"Požadavek se nepodařilo dokončit. Zkuste jej opakovat. ("+(/^[a-zA-Z0-9_]{1,80}$/.test(code)?code:"request_failed")+")";
  }
  async run(action){if(this._busy)return;this._busy=true;this._failed=false;this._message="";try{await action();}catch(error){this._failed=true;this._message=this.errorText(error);}finally{this._busy=false;this.render();}}
  formMarkup(form){const settings=this._detail?.place.settings || {};return `<form data-section="${form.section}"><h3>${form.title}</h3>${form.fields.map(f=>{
    const value=(form.section==="settings"||f.name==="segment")?settings[f.name]:(form.section==="invoices"&&f.name==="artifact"?this._invoiceArtifact:"");let input;
    if(f.type==="checkbox")input=`<input name="${f.name}" type="checkbox" ${value?"checked":""}> ${esc(f.label)}`;
    else if(f.type==="select")input=`${esc(f.label)}<select name="${f.name}">${f.options.map(o=>`<option value="${o}" ${value===o?"selected":""}>${esc(o)}</option>`).join("")}</select>`;
    else if(f.type==="flow")input=`${esc(f.label)}<select name="${f.name}"><option value="">Nevybráno</option>${Object.values(this._hass.states||{}).filter(s=>["m³/h","m3/h","L/min","l/min","L/h","l/h","m³/s","m3/s"].includes(s.attributes.unit_of_measurement)).map(s=>`<option value="${esc(s.entity_id)}" ${value===s.entity_id?"selected":""}>${esc(s.attributes.friendly_name||s.entity_id)}</option>`).join("")}</select>`;
    else if(["sensor","history"].includes(f.type))input=`${esc(f.label)}<select name="${f.name}"><option value="">Nevybráno</option>${Object.values(this._hass.states || {}).filter(s=>(f.type==="history"?["m³","m3","pulse","pulses","imp"]:["m³","m3"]).includes(s.attributes.unit_of_measurement)&&["total","total_increasing"].includes(s.attributes.state_class)).map(s=>`<option value="${esc(s.entity_id)}" ${value===s.entity_id?"selected":""}>${esc(s.attributes.friendly_name || s.entity_id)}</option>`).join("")}</select>`;
    else input=`${esc(f.label)}<input name="${f.name}" type="${f.type==="date"?"date":"text"}" ${f.type==="decimal"?'inputmode="decimal"':""} value="${esc(value)}">`;
    return `<label>${input}</label>`;}).join("")}<button class="primary" type="submit">Uložit do evidence HA</button></form>`;}
  text(value){return (this._hass?.language||"cs").startsWith("en")?(EN[value]||value):value;}
  dateText(value,time=false){
    if(!value)return "—";
    const d=new Date(String(value).includes("T")?value:String(value)+"T12:00:00Z");
    if(!Number.isFinite(d.getTime()))return "—";
    return new Intl.DateTimeFormat((this._hass?.language||"cs").startsWith("en")?"en-GB":"cs-CZ",{
      day:"numeric",month:"numeric",year:"numeric",...(time?{hour:"2-digit",minute:"2-digit"}:{}),
      ...(this._hass?.config?.time_zone?{timeZone:this._hass.config.time_zone}:{})
    }).format(d);
  }
  billingSummary(){
    const b=this._detail?.result.billing;
    if(!b?.from)return `<section><h2>Účetní období MND</h2><p>Přehled čeká na načtení období a podkladů MND. Neznámé částky nejsou nulové.</p></section>`;
    const balance=b.forecast_balance_czk;
    const label=b.confirmed_invoice?"Výsledek originálního vyúčtování":balance==null?"Odhad vyúčtování čeká na podklady":Number(balance)>=0?"Očekávaný přeplatek":"Očekávaný nedoplatek";
    const rows=[["Skutečný odběr MND dosud",b.actual_mwh,"MWh"],["Odhad odběru celkem",b.forecast_mwh,"MWh"],[b.known_cost_complete?"Známé náklady k odečtu":"Doložená část nákladů",b.known_cost_czk,"Kč"],["Odhad nákladů celkem",b.forecast_cost_czk,"Kč"],["Uhrazené zálohy",b.paid_czk,"Kč"],["Plán záloh celkem",b.planned_czk,"Kč"]];
    return `<section class="billing-summary"><h2>Účetní období MND</h2><p class="period">${this.dateText(b.from)} → ${this.dateText(b.to)}</p><h3>${label}</h3>${balance==null?"":`<p class="balance-value">${this.number(String(balance).replace(/^-/ ,""),"Kč")}</p>`}<table><thead><tr><th>Za účetní období</th><th>Hodnota</th></tr></thead><tbody>${rows.map(([name,value,unit])=>`<tr><td><span>${name}</span></td><td>${this.number(value,unit)}</td></tr>`).join("")}</tbody></table><p class="muted">Uhrazené zálohy jsou skutečné platby z MND, nikoli předepsané částky. Známé náklady jsou výpočet z doložené ceny a odběru; originální vyúčtování má přednost.</p><p class="muted"><span>Spotřeba MND k odečtu</span> ${this.dateText(b.actual_through)}. <span>Novější měření HA je samostatně v měsíčních sloupcích.</span></p>${b.invoice_count&&!b.known_cost_complete?`<p class="notice">Originální faktura má přednost. Zbytek nákladů zatím nelze bezpečně oddělit.</p>`:""}${b.warnings?.includes("invoice_boundary_mismatch")?`<p class="notice">Období faktury přesahuje vybrané účetní období. Částku nerozdělujeme odhadem.</p>`:""}${b.warnings?.includes("verified_price_missing")?`<p class="notice">Náklady čekají na ověření originálního ceníku. Platby už jsou dostupné.</p>`:""}${b.warnings?.includes("fixed_calendar_proration_assumed")?`<p class="muted">Poměr stálých měsíčních plateb podle dnů je orientační. Rozhodující je originální vyúčtování.</p>`:""}${b.warnings?.includes("future_regulated_price_assumed")?`<p class="muted">Odhad používá prognózu MND a doložený ceník. Budoucí regulované ceny zatím vycházejí z posledních známých sazeb.</p>`:""}${b.warnings?.includes("payments_partial")?`<p class="notice">Historie úhrad není úplná. Zobrazený součet obsahuje jen doložené platby.</p>`:""}</section>`;
  }
  cashChart(){
    /* Peněžní hodnoty se zde pouze promítají na pixely. Účetní aritmetika
     * a zaokrouhlení zůstávají v Decimal na serveru. Každý bod nese přesný
     * řetězec Kč v popisku. Neznámá série se nikdy nekreslí jako nula. */
    const b=this._detail?.result.billing;
    if(!b?.from||!b?.to)return "";
    const numeric=v=>v==null||v===""||!Number.isFinite(Number(v))?null:Number(v);
    const first=Date.parse(b.from+"T00:00:00Z"),last=Date.parse(b.to+"T00:00:00Z");
    if(!(last>first))return "";
    const definitions=[["known_cost","Známé náklady","#ec941b",false],["forecast_cost","Odhad nákladů","#2a976c",false],["paid","Zaplacené zálohy","#6669ad",true],["planned","Plán záloh","#a0a1c2",true]];
    const groups=definitions.map(([key,label,color,step])=>({key,label,color,step,points:(b.series?.[key]||[]).filter(p=>numeric(p.value)!==null&&Number.isFinite(Date.parse(p.date))).map(p=>({...p,n:numeric(p.value)}))}));
    const maximum=Math.max(1,...groups.flatMap(g=>g.points.map(p=>p.n)))*1.12;
    const x=d=>84+Math.max(0,Math.min(1,(Date.parse(d)-first)/(last-first)))*486;
    const y=n=>234-n/maximum*198;
    const axes=Array.from({length:5},(_,i)=>{const value=maximum*i/4,py=y(value);return `<line x1="84" x2="570" y1="${py}" y2="${py}" stroke="var(--mnd-border)" stroke-dasharray="3 4"/><text x="76" y="${py+6}" text-anchor="end">${esc(new Intl.NumberFormat("cs-CZ",{maximumFractionDigits:0,notation:maximum>10000?"compact":"standard"}).format(value))}</text>`;}).join("");
    const dates=Array.from({length:6},(_,i)=>new Date(first+(last-first)*i/5).toISOString().slice(0,10));
    const labels=dates.map(d=>`<text x="${x(d)}" y="266" text-anchor="middle">${esc(d.slice(5,7)+"/"+d.slice(2,4))}</text>`).join("");
    const series=groups.map(g=>{
      let path="";
      for(const [i,p] of g.points.entries())path+=i?(g.step?` H${x(p.date)} V${y(p.n)}`:` L${x(p.date)} ${y(p.n)}`):`M${x(p.date)} ${y(p.n)}`;
      const dashed=g.key==="forecast_cost"?"7 6":g.key==="planned"?"3 7":"";
      return `${g.points.length>1?`<path d="${path}" fill="none" stroke="${g.color}" stroke-width="3" ${dashed?`stroke-dasharray="${dashed}"`:""}/>`:""}${g.points.map(p=>`<circle cx="${x(p.date)}" cy="${y(p.n)}" r="4.5" fill="${g.color}" tabindex="0" role="img" aria-label="${esc(this.text(g.label)+": "+this.dateText(p.date)+", "+this.number(p.value,"Kč"))}"><title>${esc(this.text(g.label)+": "+this.dateText(p.date)+" · "+this.number(p.value,"Kč"))}</title></circle>`).join("")}`;
    }).join("");
    const today=x(b.today),marker=`<line x1="${today}" x2="${today}" y1="22" y2="234" stroke="#1396ac" stroke-dasharray="4 4"/><text x="${today}" y="16" text-anchor="middle" fill="#1396ac">Dnes</text>`;
    return `<section class="billing-chart"><h2>Náklady a zálohy za účetní období</h2><p class="axis-unit">Kč</p><svg class="billing-plot" viewBox="0 0 600 288" role="img" aria-label="Náklady a zálohy za účetní období">${axes}${series}${marker}${labels}</svg><div class="chart-legend">${groups.map(g=>`<span><i style="background:${g.color}"></i>${this.text(g.label)}${g.points.length?"":" · "+this.text("údaje chybí")}</span>`).join("")}</div><p class="muted">Čárkovaná spojnice ukazuje celkový výhled MND, nikoli doloženou měsíční předpověď. Platby mají skutečné datum úhrady. Předpis není platba.</p></section>`;
  }
  monthlyChart(){
    const rows=this._detail?.result.billing?.months||[];
    if(!rows.length)return "";
    const values=rows.filter(r=>r.m3!=null&&Number.isFinite(Number(r.m3))).map(r=>Number(r.m3));
    const maximum=Math.max(1,...values)*1.12,step=486/rows.length;
    const y=v=>230-v/maximum*192;
    const axes=Array.from({length:5},(_,i)=>{const value=maximum*i/4,py=y(value);return `<line x1="84" x2="570" y1="${py}" y2="${py}" stroke="var(--mnd-border)" stroke-dasharray="3 4"/><text x="76" y="${py+6}" text-anchor="end">${esc(new Intl.NumberFormat("cs-CZ",{maximumFractionDigits:1}).format(value))}</text>`;}).join("");
    const bars=rows.map((r,i)=>{const px=84+i*step+step*.16,known=r.m3!=null&&Number.isFinite(Number(r.m3)),value=known?Number(r.m3):null;
      const label=r.month.slice(5,7)+"/"+r.month.slice(2,4),description=label+": "+(known?this.number(r.m3,"m³"):this.text("Údaje chybí"))+" · "+this.text(r.complete?"úplný měsíc":"neúplný měsíc");
      return `<g tabindex="0" role="img" aria-label="${esc(description)}"><title>${esc(description)}</title>${known?`<rect x="${px}" y="${y(value)}" width="${step*.68}" height="${Math.max(2,230-y(value))}" fill="${r.complete?"var(--mnd-actual)":"#ec941b"}" rx="2"/>`:`<text x="${px+step*.34}" y="218" text-anchor="middle">—</text>`}</g><text x="${px+step*.34}" y="260" text-anchor="middle">${label}</text>`;
    }).join("");
    return `<section class="billing-chart"><h2>Měsíční odběr podle měření HA</h2><p class="axis-unit">m³</p><svg class="billing-plot" viewBox="0 0 600 280" role="img" aria-label="Měsíční odběr podle měření HA">${axes}${bars}</svg><div class="chart-legend"><span><i style="background:var(--mnd-actual)"></i>Úplný měsíc</span><span><i style="background:#ec941b"></i>Neúplný měsíc</span><span>— <span>Údaje chybí</span></span></div><p class="muted">Oranžové sloupce obsahují pouze známou část měsíce. Chybějící data nejsou nulová spotřeba. Celkový odběr pro vyúčtování přebírá MND; jeho souhrn nemusí odpovídat součtu sloupců HA.</p></section>`;
  }
  overview(){
    const r=this._detail?.result||{},b=r.billing;
    if(!b?.from||(b.source==="configured"&&!this._detail?.place.portal_evidence?.advances))return this.legacyOverview();
    const cards=[["Aktuální průtok",r.current_flow_m3h,"m³/h","current_flow_m3h"],["Naměřeno HA v období",b.known_volume_m3,"m³","billing_volume_m3"],["Poslední odečet MND",r.latest_mnd,"m³","latest_mnd"],["Předpis zálohy MND",r.current_deposit_czk,"Kč","current_deposit_czk"]];
    return `<div class="grid">${cards.map(([label,value,unit,key])=>`<div class="card"><div class="label">${label}</div>${this._config?.entities?.[key]?`<button class="value metric" data-entity="${esc(this._config.entities[key])}" aria-label="${esc(label)}">${this.number(value)} <small>${unit}</small></button>`:`<div class="value">${this.number(value)} <small>${unit}</small></div>`}</div>`).join("")}</div><p class="muted">Odečet MND: ${this.dateText(r.latest_mnd_date)} · Průtok: ${esc(({current:"aktuální",stale:"zastaralý report",unavailable:"nedostupný"})[r.flow_status]||"nepřipojeno")}.</p>${this.billingSummary()}${this.cashChart()}${this.monthlyChart()}`;
  }
  legacyOverview(){
    const r=this._detail?.result||{};
    const cards=[["Aktuální průtok",r.current_flow_m3h,"m³/h","current_flow_m3h"],["Spotřeba vyhodnoceného období",r.volume_m3,"m³","volume_m3"],["Poslední odečet MND",r.latest_mnd,"m³","latest_mnd"],["Předpis zálohy MND",r.current_deposit_czk,"Kč","current_deposit_czk"],["Skutečně zaplaceno",r.paid_czk,"Kč","paid_czk"],["Známé náklady",r.known_cost_czk,"Kč","known_cost_czk"]];
    return `<div class="grid">${cards.map(([label,v,u,key])=>`<div class="card"><div class="label">${label}</div>${this._config?.entities?.[key]?`<button class="value metric" data-entity="${esc(this._config.entities[key])}" aria-label="${esc(label)}">${this.number(v)} <small>${u}</small></button>`:`<div class="value">${this.number(v)} <small>${u}</small></div>`}</div>`).join("")}</div><p class="muted">Datum odečtu MND: ${esc(r.latest_mnd_date||"neznámé")} · Průtok: ${esc(({current:"aktuální",stale:"zastaralý report",unavailable:"nedostupný",incompatible_unit:"nepodporovaná jednotka"})[r.flow_status]||"nepřipojeno")} ${esc(r.flow_at||"")}</p>${r.current_meter!=null?`<p>Aktuální odvozený stav: ${this.number(r.current_meter,"m³")}</p>`:""}<p class="muted">${r.evaluated_from?`${esc(r.evaluated_from)} → ${esc(r.evaluated_to)}`:"Období a zdroje nastavte v konfiguraci odběrného místa."}</p>${this.chart()}`;
  }
  financeMarkup(){
    const evidence=this._detail?.place.portal_evidence||{};
    const advances=evidence.advances;
    const invoices=evidence.invoices;
    const section=(data,kind,title)=>`<section><h2>${title}</h2>${data?`<p class="muted">Aktualizováno: ${esc(data.acquired_at)} · ${data.list_complete&&data.details_complete&&data.details_refreshed_all!==false?"Seznam a detaily načteny":"Částečné podklady"}</p>${table(data.rows||[],kind==="advances"?[["due","Splatnost"],["prescribed","Předpis Kč"],["paid","Uhrazeno Kč"],["remaining","Zbývá Kč"],["state","Stav"]]:[["number","Doklad"],["from","Od"],["to_inclusive","Do včetně"],["invoice_result","Výsledek dle MND Kč"],["remaining","Zbývá dle MND Kč"],["state","Stav"]])}${(data.rows||[]).map(row=>`<button data-finance-kind="${kind}" data-finance-id="${esc(row.id)}">Detail ${esc(row.number)}</button>`).join(" ")}${this._admin?`<p><button data-finance-export="${kind}">Export ${kind==="advances"?"historie záloh":"přehledu vyúčtování"}</button></p>`:""}`:`<p>${evidence.errors?.[kind]?"Načtení MND selhalo. Poslední dostupné údaje zůstávají zachovány.":"Dosud nenačteno z MND."}</p>`}</section>`;
    const selected=this._financeDetail;
    return section(advances,"advances","Historie záloh MND")+(this._admin?`<section><h3>Přiřazení do místní evidence</h3><p>Potvrzením přiřadíte předpisy splatné ve zvoleném účetním období a jejich skutečné úhrady do tohoto období. Ruční duplicitní platby nejprve zkontrolujte. Úplnost historie se nepotvrzuje automaticky.</p><label><input id="confirm-finance" type="checkbox"> Potvrzuji přiřazení a kontrolu ručních duplicit</label><button id="accept-advances">Převzít předpisy a úhrady do období</button></section>`:"")+section(invoices,"invoices","Vyúčtování MND")+(selected?`<section><h2>Detail ${esc(selected.number)}</h2><p>${esc(selected.from||"")} → ${esc(selected.to_inclusive||"")} · ${esc(selected.state||"")}</p><p>Předpis Kč: ${this.number(selected.prescribed)} · Uhrazeno Kč: ${this.number(selected.paid)} · Zbývá dle MND Kč: ${this.number(selected.remaining)}</p><h3>Skutečně zaúčtované úhrady dokladu</h3>${selected.payments_known?table(selected.payments,[["date","Datum úhrady"],["amount","Kč"]]):"Detail úhrad dosud nebyl načten."}${selected.kind==="invoices"?`<button id="invoice-pdf">Stáhnout vyúčtování PDF</button>`:""}<p class="muted">Úhrady jsou přiřazené k tomuto dokladu; předpis není skutečná platba. Výsledek a stav vypořádání jsou údaje dodavatele.</p></section>`:"");
  }
  chart(){const snapshots=this._detail?.place.snapshots || [];const selected=snapshots[this._snapshotIndex ?? snapshots.length-1];const rows=selected?.periods || [];
    if(!rows.length)return '<section><h2>Spotřeba a prognózy MND</h2><div class="no-data">Dosud nebyl importován snapshot prognózy.</div></section>';
    const values=rows.map(p=>[p.ReadingsMwh,p.PastEstimateMwh,p.FutureEstimateMwh].map(v=>v===null||v===undefined?null:Number(v)));
    const maximum=Math.max(1,...values.map(v=>v.reduce((s,x)=>s+(x||0),0)));
    return `<section><h2>Uložený výhled MND</h2><p class="muted">Snapshot: ${esc(selected.retrieved_at)} · MWh. Neznámé díly nejsou nuly.</p><svg viewBox="0 0 700 250" role="img" aria-label="Spotřeba podle odečtů, odhad minulosti a odhad budoucnosti"><line x1="20" y1="210" x2="680" y2="210" stroke="currentColor" opacity=".3"/>${values.map((v,i)=>{let y=210;const width=600/Math.max(1,values.length);return v.map((value,j)=>{if(value===null)return "";const h=value/maximum*170;y-=h;return `<rect x="${30+i*width}" y="${y}" width="${Math.min(width-15,95)}" height="${h}" fill="${["var(--mnd-actual)","var(--mnd-estimate)","none"][j]}" stroke="${j===2?"var(--mnd-actual)":"none"}" ${j===2?'stroke-dasharray="4 3"':""}><title>${esc(TABS.forecasts)}: ${esc(rows[i].From)} až ${esc(rows[i].To)}; ${["odečty","odhad minulosti","odhad budoucnosti"][j]} ${value} MWh</title></rect>`;}).join("")+`<text x="${30+i*width}" y="232" fill="currentColor" font-size="11">${esc(rows[i].From || "?")}</text>`;}).join("")}</svg><div class="legend"><span><i class="dot"></i>Podle odečtů</span><span><i class="dot estimated"></i>Odhad minulosti</span><span><i class="dot future"></i>Odhad budoucnosti</span></div></section>`;
  }
  advancesMarkup(){
    const p=this._detail?.place;const settings=p?.settings || {};
    if(!settings.period_from||!settings.period_to)return "";
    const replaced=new Set(p.events.map(e=>e.supersedes).filter(Boolean));
    const active=p.events.filter(e=>!replaced.has(e.id)&&e.source==="monthly_grid");
    let month=settings.period_from.slice(0,7);const rows=[];
    while(month+"-01"<settings.period_to && rows.length<120){
      const events=active.filter(e=>e.month===month);const plan=events.find(e=>e.role==="prescribed");const paid=events.find(e=>e.role==="payment");
      rows.push(`<tr data-month="${month}"><td>${month}</td><td><input name="prescribed" aria-label="Předpis ${month}" inputmode="decimal" value="${esc(plan?.amount)}"></td><td><input name="paid" aria-label="Úhrada ${month}" inputmode="decimal" value="${esc(paid?.amount)}"></td><td><input name="paid_on" type="date" value="${esc(paid?.date)}"></td></tr>`);
      const [year,m]=month.split("-").map(Number);month=m===12?`${year+1}-01`:`${year}-${String(m+1).padStart(2,"0")}`;
    }
    return `<section><h2>Měsíční zálohy</h2><p class="muted">Prázdné pole zachová údaj. Předpis a skutečná úhrada se ukládají odděleně; vyšší úhrada je povolena.</p><label><input type="checkbox" id="same-plan"> Použít stejný předpis pro měsíce</label><input id="common-plan" inputmode="decimal" aria-label="Společný předpis Kč"><div class="scroll"><table><thead><tr><th>Měsíc</th><th>Předpis Kč</th><th>Uhrazeno Kč</th><th>Datum skutečné úhrady</th></tr></thead><tbody>${rows.join("")}</tbody></table></div><button id="save-advances" class="primary">Uložit celé období</button></section>`;
  }
  extraMarkup(){
    if(!this._detail||!this._admin)return "";
    if(this._tab==="history")return `<section><h2>Připojení a historie</h2><button id="cloud-refresh">Obnovit MND</button> <button id="history-start">Pokračovat v historii MND</button> <button id="history-cancel">Pozastavit úlohu</button><p class="muted"><span>Stav úlohy:</span> ${esc(this._summary?.job?.status || "idle")} · ${esc(this._summary?.job?.reason || "")}</p><h3>Historie senzoru HA</h3><div class="row"><input id="recorder-from" type="date" value="${esc(this._detail.place.settings.period_from)}"><input id="recorder-to" type="date" value="${esc(this._detail.place.settings.period_to)}"></div><button id="recorder-history">Načíst historii senzoru</button></section><section><h2>Záloha a export</h2><label><input id="backup-documents" type="checkbox"> Záloha ZIP včetně dokladů</label><button id="backup">Stáhnout zálohu ZIP</button> <button id="csv">Export odečtů CSV</button></section>`;
    if(this._tab==="forecasts")return `<section><h2>Porovnat uložený výhled s fakturou</h2><p class="muted">Používají se přímo MWh dodavatele; žádný převod m³ se nedopočítává. Potvrďte shodný význam a hranice období.</p><label>Období snapshotu<select id="comparison-period">${(this._detail.place.snapshots[this._snapshotIndex??this._detail.place.snapshots.length-1]?.periods||[]).map((p,i)=>`<option value="${i}">${esc(p.From)} – ${esc(p.To)}</option>`).join("")}</select></label><label>Faktura<select id="comparison-invoice">${this._detail.place.invoices.map(i=>`<option value="${esc(i.id)}">${esc(i.number)} · ${esc(i.from)} – ${esc(i.to)}</option>`).join("")}</select></label><label><input id="confirm-period" type="checkbox"> Potvrzuji shodné hranice a energetickou bázi</label><button id="compare">Porovnat s fakturou</button> <button id="compare-measurement">Porovnat s dokončeným měřením</button>${this._comparison?`<div class="notice">Odchylka výhledu minus skutečnost: ${this.number(this._comparison.difference,"MWh")} · ${this.number(this._comparison.percentage,"%")}</div>`:""}</section><section><h2>Vlastní sezonní odhad</h2><div class="row"><input id="forecast-from" type="date"><input id="forecast-to" type="date"></div><button id="local-forecast">Vypočítat sezonní odhad</button>${this._localForecast?`<p>${this._localForecast.complete?this.number(this._localForecast.value,"m³"):esc(this._localForecast.reason)}</p><p>Odhad zbývajících nákladů: ${this.number(this._localForecast.remaining_cost_czk,"Kč")}</p><p>Odhad výsledku období: ${this.number(this._localForecast.forecast_balance_czk,"Kč")}</p><p>Místní návrh měsíční zálohy: ${this.number(this._localForecast.recommended_advance_czk,"Kč")}</p><p class="muted">${esc((this._localForecast.price_warnings||[]).join(", "))}</p>`:""}</section>`;
    if(this._tab==="accounting"&&this._detail.settlements?.length)return `<section><h2>Vypořádání faktur</h2>${table(this._detail.settlements,[["id","ID faktury"],["result","Původní výsledek Kč"],["remaining","Zbývá uhradit / vrátit Kč"],["over_settled","Vyšší vypořádání Kč"]])}</section>`;
    return "";
  }
  portalMarkup(){
    if(!this._admin||this._tab!=="history"||!this._detail?.place.settings.portal)return "";
    const docs=this._detail.place.portal_evidence?.documents || [];const technical=this._detail.place.technical || {};
    return `<section><h2>Moje MND · smlouva a zákaznické údaje</h2>${table([technical],[["identity","EIC"],["contract","Číslo smlouvy"],["distributor","Distributor"],["meter","Číslo plynoměru"],["measurement","Typ měření"],["annual_mwh","Roční spotřeba MND (MWh)"]])}<p class="muted">Profil a platební přehled se načtou až na vyžádání. Jejich zobrazení nevytváří skutečnou úhradu v účetnictví HA.</p><div class="row"><button id="portal-profile">Zákaznický profil</button><button id="portal-payments">Platební přehled MND</button></div>${this._portalData?`<h3>${esc(this._portalKind)}</h3><pre class="scroll">${esc(JSON.stringify(this._portalData,null,2))}</pre>`:""}<h3>Export odečtů pro interval</h3><p class="muted">Oba dny včetně, nejvýše 366 dní na jeden export. Originál se uloží spolu s odečty.</p><div class="row"><label>Od<input id="export-from" type="date"></label><label>Do včetně<input id="export-to" type="date"></label></div><button id="readings-export">Stáhnout a přijmout odečty MND</button><h3>Smluvní dokumenty</h3>${Array.isArray(docs)?docs.map(d=>`<p><button data-document="${esc(d.DOCID)}">${esc(d.DOC_NAME || d.TYPE || "Dokument")}</button></p>`).join(""):""}<p class="muted">Dokument se ověří proti aktuálnímu seznamu MND a uloží jako soukromý originál.</p><div class="row"><button id="cloud-logout">Odhlásit relaci MND</button><button id="cloud-forget">Odhlásit a zapomenout uložený přístup</button></div><p><a href="/config/integrations/integration/mnd_tariff_accounting">Přihlášení a nastavení integrace v HA</a></p></section>`;
  }
  body(){const p=this._detail?.place;if(!p)return this._failed?"":`<p class="muted">${this._entry&&!this._place?"Odběrné místo není dostupné. Ověřte konfiguraci zařízení.":"Načítání…"}</p>`;
    if(!this._admin){
      if(this._tab==="editor"||this._config?.admin_link)return `<section><h2>Konfigurace odběrného místa</h2><a href="${esc(this._detail.device_url||"/config/devices")}">Otevřít zařízení MND v Nastavení</a></section>`;
      if(this._tab==="history")return this.financeMarkup();
      if(this._tab==="accounting")return this.billingSummary()+this.cashChart()+this.financeMarkup();
      if(this._tab==="forecasts")return this.chart()+`<section><h2>Ověřená porovnání prognóz</h2>${table(p.comparisons||[],[["from","Od"],["to","Do"],["difference","Odchylka MWh"],["percentage","Odchylka %"]])}<p>Porovnání vyžaduje dokončené shodné období a doloženou energetickou bázi. Průběžná spotřeba není chyba celoroční predikce.</p></section>`;
      if(this._tab==="readings")return this.monthlyChart()+`<section><h2>Historie odečtů</h2>${table(p.readings,[["date","Den"],["value","m³"],["source","Zdroj"],["method","Metoda"]])}</section><section><h2>Porovnání senzoru s odečtem MND</h2>${table(this._detail.result.meter_comparisons||[],[["date","Den"],["expected","Senzor m³"],["actual","MND m³"],["difference","Rozdíl m³"],["percentage","Rozdíl %"],["reason","Stav porovnání"]])}</section>`;
    }
    switch(this._tab){
      case "overview":return this.overview();
      case "readings":return `<section><h2>Historie odečtů</h2>${table(p.readings,[["date","Den"],["observed_at","Přesný čas"],["value","m³"],["meter","Plynoměr"],["source","Zdroj"],["method","Metoda"],["status","Status"],["id","ID pro opravu"]])}</section>`;
      case "accounting":return this.financeMarkup()+`<section><h2>Platby a předpisy</h2><p class="muted">Předpis a předpokládaná platba nezvyšují skutečně zaplacenou částku.</p>${table(p.events,[["date","Datum"],["role","Role"],["amount","Kč"],["verification","Ověření"],["id","ID"]])}</section><section><h2>Vyúčtování</h2>${table(p.invoices,[["number","Doklad"],["from","Od"],["to","Do výlučně"],["cost","Náklad Kč"],["result","Dokladové saldo Kč"],["id","ID"]])}</section><section><h2>Cenové úseky</h2>${table(p.tariffs,[["name","Tarif"],["from","Od"],["to","Do výlučně"],["commodity","Obchodní Kč/MWh"],["other","Ostatní Kč/MWh"],["fixed","Kč/měsíc"],["role","Role"],["id","ID"]])}</section>`;
      case "forecasts":return `<section><h2>Historie prognóz</h2><select id="snapshot">${p.snapshots.map((s,i)=>`<option value="${i}" ${i===(this._snapshotIndex??p.snapshots.length-1)?"selected":""}>${esc(s.retrieved_at)}</option>`).join("")}</select><p class="muted">Starší předpověď zůstává uložená. Přesnost lze hodnotit až za shodné dokončené období a doložené měření.</p></section>${this.chart()}`;
      case "editor":return `<div class="notice">Zápisy jsou místní evidence v HA. Časy odečtů zadávejte s výslovným UTC posunem. Pole bez údaje ponechte prázdná.</div>${this.advancesMarkup()}<div class="forms">${FORMS.map(f=>this.formMarkup(f)).join("")}</div>`;
      case "history":return `<section><h2>Import odečtů, faktury a účetního archivu</h2><p>XLSX / JSON / ZIP nejvýše 64 MiB; PDF nejvýše 8 MiB. Před importem ověříme identitu vybraného místa.</p><input type="file" id="file" accept=".xlsx,.json,.zip,.pdf"><button id="preview-import">Zkontrolovat soubor</button>${this._importPreview?`<div class="notice">Řádků: ${esc(this._importPreview.rows)}; odmítnutých: ${esc(this._importPreview.rejected)}<br>${esc(this._importPreview.warnings.join(", "))}</div>${this._importPreview.proposal?`<p>Částky z PDF jsou pouze návrh. Doklad nejprve uložte a účetní údaje samostatně potvrďte v Editoru.</p>${table(this._importPreview.proposal.candidates,[["kind","Význam"],["value","Hodnota"],["unit","Jednotka"],["context","Kontext dokladu"]])}`:""}<button id="commit-import" class="primary">Potvrdit import tohoto souboru</button>`:""}</section><section><h2>Soukromý export</h2><button id="export">Stáhnout účetní archiv JSON</button></section><section><h2>Doklady</h2>${p.artifacts.map(a=>`<p><button data-artifact="${esc(a.id)}">Stáhnout ${esc(a.filename)}</button> <span class="muted">${esc(a.acquired_at)}</span></p>`).join("") || "Žádné uložené originály."}</section><section><h2>Audit</h2>${table(p.audit.slice(-100),[["received_at","Čas"],["action","Akce"],["section","Oblast"],["id","ID"]])}</section>`;
      case "dashboard":return `<section><h2>Přidat do horní lišty Overview</h2><p>Jednoduchý přehled a čtecí detaily. Uložení aktualizuje i již vytvořenou MND šablonu a zachová cizí karty. Záloha Overview se před uložením stáhne do vašeho zařízení.</p><label>Název<input id="view-title" value="MND"></label><label>Cesta<input id="view-path" value="mnd"></label><button id="dashboard-preview">Vytvořit náhled</button>${this._preview?`<p class="muted">Chybějící entity: ${esc(this._preview.missing_entities.join(", ") || "žádné")}</p><h3>Náhled skutečných dat</h3><div id="dashboard-visual"></div><textarea readonly>${esc(JSON.stringify(this._preview.config,null,2))}</textarea><button id="dashboard-export">Stáhnout fragment views</button><button id="dashboard-save" class="primary" ${this._preview.missing_entities.length?"disabled":""}>Uložit MND v horní liště</button>`:""}</section>`;
      default:return "";
    }
  }
  navigation(){
    /* Karta používá stejný vzhled jako panel. V generovaném Overview jsou
     * odkazy skutečné HA cesty; panel přepíná interní obsah bez zápisu. */
    if(!this._admin&&this._config?.navigation)return `<nav aria-label="MND">${this._config.navigation.map(item=>`<a href="${esc(item.path)}" ${item.tab===this._tab?'class="active" aria-current="page"':""}>${esc(TABS[item.tab]||item.tab)}</a>`).join("")}</nav>`;
    return this._config?"":`<nav aria-label="MND">${Object.entries(TABS).filter(([key])=>["editor","accounting","history","forecasts","dashboard"].includes(key)).map(([key,title])=>`<button data-tab="${key}" class="${key===this._tab?"active":""}" ${key===this._tab?'aria-current="page"':""}>${title}</button>`).join("")}</nav>`;
  }
  render(){if(!this.shadowRoot)return;const p=this._detail?.place;
    this.shadowRoot.innerHTML=`<style>${CSS}
main{padding:16px;padding-top:max(16px,env(safe-area-inset-top));padding-bottom:max(16px,env(safe-area-inset-bottom))}header{padding-bottom:12px}.brand strong{font-size:20px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.card{min-width:0}.card .value{overflow-wrap:anywhere}.value{font-size:25px}.mark{width:36px;height:36px}nav{margin-bottom:16px}h1{font-size:20px;margin:0}</style><main>${this._admin?`<p><a href="${esc(this._detail?.device_url||"/config/devices")}">← Zpět na zařízení MND</a></p>`:""}<header><div class="brand"><div class="mark" aria-hidden="true">${BRAND_ICON}</div><div><strong>MND</strong><h1>${esc(this._admin?"Konfigurace odběrného místa":(p?.name||this._config?.title||"Přehled"))}</h1></div></div>${this._admin&&!this._place?`<div class="account-picker"><label>Registrovaný účet<select id="entry"><option value="">Vyberte účet</option>${(this._entries||[]).map(e=>`<option value="${esc(e.id)}" ${e.id===this._entry?"selected":""}>${esc(e.name)}</option>`).join("")}</select></label><label>Odběrné místo<select id="place">${(this._summary?.places||[]).map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select></label></div>`:""}</header>${this.navigation()}${this._message?`<div role="status" class="notice ${this._failed?"error":""}">${esc(this._message)}${this._failed?'<p><button id="retry-load">Zkusit znovu</button></p>':""}</div>`:""}${this.body()}${this.extraMarkup()}${this.portalMarkup()}${this._admin?`<footer class="muted">Revize archivu ${esc(this._detail?.revision??"—")}</footer>`:""}</main>`;
    this.shadowRoot.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>{this._tab=b.dataset.tab;this.render();});
    this.shadowRoot.querySelectorAll("[data-entity]").forEach(b=>b.onclick=()=>this.dispatchEvent(new CustomEvent("hass-more-info",{bubbles:true,composed:true,detail:{entityId:b.dataset.entity}})));
    const visual=this.shadowRoot.getElementById("dashboard-visual");if(visual){const card=document.createElement("mnd-accounting-card");card.setConfig(this._preview.config.views[0].cards[0]);card.setAttribute("inert","");card.hass=this._hass;visual.append(card);}
    const on=(id,handler)=>{const element=this.shadowRoot.getElementById(id);if(element)element.onclick=()=>this.run(handler);};
    on("retry-load",()=>this.load({force:true}));
    on("accept-advances",async()=>{await this.command("accept_advances",{confirm:this.shadowRoot.getElementById("confirm-finance").checked,revision:this._detail.revision});this._detail=await this.command("detail");});
    this.shadowRoot.querySelectorAll("[data-finance-id]").forEach(b=>b.onclick=()=>{this._financeDetail=this._detail.place.portal_evidence[b.dataset.financeKind].rows.find(r=>r.id===b.dataset.financeId);this.render();});
    const fetchDocument=async(action,payload)=>{const saved=await this.command(action,payload);const response=await this._hass.fetchWithAuth(`/api/${DOMAIN}/artifact/${encodeURIComponent(this._entry)}/${encodeURIComponent(this._place)}/${saved.artifact}`);if(!response.ok)throw new Error("document_download_failed");this.download(await response.blob(),saved.filename,"application/octet-stream");};
    on("invoice-pdf",()=>fetchDocument("invoice_pdf",{document_id:this._financeDetail.id}));
    this.shadowRoot.querySelectorAll("[data-finance-export]").forEach(b=>b.onclick=()=>this.run(()=>fetchDocument("finance_export",{kind:b.dataset.financeExport})));
    const place=this.shadowRoot.getElementById("place");if(place)place.onchange=()=>{this._place=place.value;this._financeDetail=null;this._portalData=null;this._importPreview=null;this._importFile=null;this._invoiceArtifact=null;this._comparison=null;this._localForecast=null;this._snapshotIndex=null;this._preview=null;this._detail=null;this._loaded=false;this.render();this.load({force:true});};
    const entry=this.shadowRoot.getElementById("entry");if(entry)entry.onchange=()=>{this._entry=entry.value;this._financeDetail=null;this._portalData=null;this._importPreview=null;this._importFile=null;this._invoiceArtifact=null;this._comparison=null;this._localForecast=null;this._snapshotIndex=null;this._place=null;this._detail=null;this._summary=null;this._preview=null;this._detail=null;this._loaded=false;this.render();this.load({force:true});};
    const snapshot=this.shadowRoot.getElementById("snapshot");if(snapshot)snapshot.onchange=()=>{this._snapshotIndex=Number(snapshot.value);this.render();};
    this.shadowRoot.querySelectorAll("form").forEach(form=>form.onsubmit=event=>{event.preventDefault();this.run(async()=>{
      const section=form.dataset.section;const definition=FORMS.find(f=>f.section===section);const record={};
      for(const f of definition.fields){const input=form.elements.namedItem(f.name);if(f.type==="checkbox")record[f.name]=input.checked;else if(f.type==="flow")record[f.name]=input.value;else if(input.value.trim()!=="")record[f.name]=input.value.trim();else if((f.type==="decimal"&&f.name!=="flow_max_age") || (section==="settings"&&f.name==="opening_credit"))record[f.name]=null;}
      if(!["settings","calibration"].includes(section))record.id=globalThis.crypto.randomUUID();
      await this.command("edit",{section,record,revision:this._detail.revision});this._detail=await this.command("detail");this._message="Záznam byl uložen.";
    });});
    on("preview-import",async()=>{const file=this.shadowRoot.getElementById("file").files[0];if(!file)throw new Error("Vyberte soubor.");this._importFile=file;this._importPreview=await this.upload(file,true);});
    on("commit-import",async()=>{const saved=await this.upload(this._importFile,false);this._invoiceArtifact=saved.artifact;this._importPreview=null;this._importFile=null;this._detail=await this.command("detail");this._message="Import byl uložen.";});
    on("export",async()=>this.download(JSON.stringify(await this.command("export"),null,2),"mnd-archive.json","application/json"));
    this.shadowRoot.querySelectorAll("[data-artifact]").forEach(b=>b.onclick=()=>this.run(async()=>{const response=await this._hass.fetchWithAuth(`/api/${DOMAIN}/artifact/${encodeURIComponent(this._entry)}/${encodeURIComponent(this._place)}/${b.dataset.artifact}`);if(!response.ok)throw new Error("Doklad nelze stáhnout.");this.download(await response.blob(),"mnd-document","application/octet-stream");}));
    on("dashboard-preview",async()=>{this._preview=await this.command("dashboard",{title:this.shadowRoot.getElementById("view-title").value,path:this.shadowRoot.getElementById("view-path").value});this._overview=await this._hass.callWS({type:"lovelace/config"}).catch(()=>null);});
    on("dashboard-export",async()=>this.download(JSON.stringify(this._preview.config,null,2),"mnd-views.yaml","application/yaml"));
    on("dashboard-save",async()=>{if(!this._overview)throw new Error("Overview nelze upravit; použijte export fragmentu.");this.download(JSON.stringify(this._overview,null,2),"mnd-overview-pred-upravou.json","application/json");await addViews(msg=>this._hass.callWS(msg),this._overview,this._preview.config.views,{update:true});this._message="Pohledy byly přidány a uložený výsledek ověřen.";this._preview=null;});
    const common=this.shadowRoot.getElementById("common-plan");if(common)common.oninput=()=>{if(this.shadowRoot.getElementById("same-plan").checked)this.shadowRoot.querySelectorAll('[data-month] input[name="prescribed"]').forEach(input=>input.value=common.value);};
    on("save-advances",async()=>{const rows=[...this.shadowRoot.querySelectorAll("[data-month]")].map(row=>({month:row.dataset.month,prescribed:row.querySelector('[name="prescribed"]').value,paid:row.querySelector('[name="paid"]').value,paid_on:row.querySelector('[name="paid_on"]').value}));await this.command("edit",{section:"advance_grid",record:{id:crypto.randomUUID(),rows},revision:this._detail.revision});this._detail=await this.command("detail");});
    on("readings-export",async()=>{await this.command("readings_export",{start:this.shadowRoot.getElementById("export-from").value,end:this.shadowRoot.getElementById("export-to").value});this._detail=await this.command("detail");this._message="Odečty i originál byly uloženy.";});
    on("portal-profile",async()=>{this._portalData=await this.command("portal_profile");this._portalKind="Zákaznický profil MND";});
    on("portal-payments",async()=>{this._portalData=await this.command("portal_payments",{offset:0});this._portalKind="Platební přehled MND";});
    this.shadowRoot.querySelectorAll("[data-document]").forEach(b=>b.onclick=()=>this.run(async()=>{await this.command("portal_document",{document_id:b.dataset.document});this._detail=await this.command("detail");this._message="Originál dokumentu je uložen v soukromém archivu.";}));
    for(const [id,forget] of [["cloud-logout",false],["cloud-forget",true]])on(id,async()=>{await this.command("cloud_logout",{forget});this._portalData=null;this._message="Relace MND byla odhlášena. Účetní archiv zůstává dostupný.";});
    on("cloud-refresh",async()=>{const result=await this.command("cloud_refresh");this._message=result.status;this._detail=await this.command("detail");});
    on("history-start",async()=>{await this.command("history_start");this._summary=await this.command("summary");});
    on("history-cancel",async()=>{await this.command("history_cancel");this._summary=await this.command("summary");});
    on("recorder-history",async()=>{await this.command("recorder_history",{start:this.shadowRoot.getElementById("recorder-from").value,end:this.shadowRoot.getElementById("recorder-to").value});this._summary=await this.command("summary");});
    on("compare-measurement",async()=>{this._comparison=await this.command("compare_measurement",{snapshot:this._snapshotIndex??this._detail.place.snapshots.length-1,period:Number(this.shadowRoot.getElementById("comparison-period").value),confirm_period:this.shadowRoot.getElementById("confirm-period").checked});});
    on("compare",async()=>{this._comparison=await this.command("compare_forecast",{snapshot:this._snapshotIndex??this._detail.place.snapshots.length-1,period:Number(this.shadowRoot.getElementById("comparison-period").value),invoice:this.shadowRoot.getElementById("comparison-invoice").value,confirm_period:this.shadowRoot.getElementById("confirm-period").checked});});
    on("local-forecast",async()=>{this._localForecast=await this.command("local_forecast",{start:this.shadowRoot.getElementById("forecast-from").value,end:this.shadowRoot.getElementById("forecast-to").value});});
    on("backup",async()=>{const include=this.shadowRoot.getElementById("backup-documents").checked;const response=await this._hass.fetchWithAuth(`/api/${DOMAIN}/backup/${encodeURIComponent(this._entry)}/${encodeURIComponent(this._place)}?documents=${include?1:0}`);if(!response.ok)throw new Error("Zálohu nelze vytvořit; ověřte dostupnost originálů.");this.download(await response.blob(),"mnd-private-backup.zip","application/zip");});
    on("csv",async()=>{const result=await this.command("csv");this.download(result.content,"mnd-readings.csv","text/csv;charset=utf-8");});
    if((this._hass?.language || "cs").startsWith("en")){const walk=node=>{for(const child of node.childNodes){if(child.nodeType===3&&node.tagName!=="TD"){const key=child.textContent.trim();if(EN[key])child.textContent=child.textContent.replace(key,EN[key]);else for(const [cs,en] of [["Neznámé díly nejsou nuly.","Unknown components are not zero."],["Řádků:","Rows:"],["odmítnutých:","rejected:"],["Chybějící entity:","Missing entities:"],["žádné","none"],["Odchylka výhledu minus skutečnost:","Forecast minus actual:"],["Odhad zbývajících nákladů:","Estimated remaining cost:"],["Odhad výsledku období:","Estimated period outcome:"],["Místní návrh měsíční zálohy:","Local suggested monthly advance:"],["Stáhnout ","Download "]])child.textContent=child.textContent.replace(cs,en);}else if(child.nodeType===1&&child.tagName!=="STYLE"&&child.tagName!=="TEXTAREA"&&child.tagName!=="PRE")walk(child);}};walk(this.shadowRoot);}
  }
  async upload(file,preview){if(file.size>64*1024*1024)throw new Error("Soubor je větší než 64 MiB.");const response=await this._hass.fetchWithAuth(`/api/${DOMAIN}/import/${encodeURIComponent(this._entry)}/${encodeURIComponent(this._place)}?filename=${encodeURIComponent(file.name)}&preview=${preview?1:0}`,{method:"POST",body:file});const result=await response.json();if(!response.ok)throw new Error(result.error || "Import selhal.");return result;}
  download(value,name,type){const blob=value instanceof Blob?value:new Blob([value],{type});const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
class MndPanel extends MndSurface {constructor(){super();this._admin=true;this._tab="editor";}}
class MndCard extends MndSurface {
  setConfig(config){
    if(!config.entry_id||!config.place)throw new Error("entry_id and place required");
    const changed=this._config?.entry_id!==config.entry_id||this._config?.place!==config.place;
    this._config=config;this._tab=config.tab||"overview";
    if(changed){this._request++;this._loaded=false;this._detail=null;this._financeDetail=null;this._entry=config.entry_id;this._place=config.place;if(this._hass&&this.isConnected)this.load({force:true});}
  }
  getCardSize(){return 6;}
}
if(globalThis.customElements){if(!customElements.get("mnd-accounting-panel"))customElements.define("mnd-accounting-panel",MndPanel);if(!customElements.get("mnd-accounting-card"))customElements.define("mnd-accounting-card",MndCard);}
