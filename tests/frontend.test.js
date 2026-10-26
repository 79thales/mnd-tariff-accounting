/* Skutečný DOM komponenty nad syntetickými účty. Nejde o vizuální ani živý HA test. */
import test from "node:test";
import assert from "node:assert/strict";
import {Window} from "happy-dom";
import {readFile} from "node:fs/promises";

const window = new Window({url:"http://localhost/mnd-tariff-accounting"});
for(const key of ["HTMLElement","customElements","document","CustomEvent","location"])globalThis[key]=window[key];
await import("../custom_components/mnd_tariff_accounting/frontend/mnd-panel.js");
const PLACE="27ZG000Z0000000X";
const detail=()=>({revision:7,place:{name:"Test",settings:{name:"Dům <test>",period_from:"2026-01-01",period_to:"2026-03-01"},readings:[],events:[],invoices:[],tariffs:[],snapshots:[],artifacts:[],audit:[]},result:{current_meter:null,paid_czk:"0",balance_czk:null,status:"incomplete"}});
async function surface({config,entries=[{id:"account-a",name:"Test"}],data=detail()}={}){
  const calls=[];
  const element=document.createElement(config?"mnd-accounting-card":"mnd-accounting-panel");
  if(config)element.setConfig(config);
  element.hass={themes:{darkMode:false},language:"cs",states:{},callWS:async msg=>{
    calls.push(structuredClone(msg));
    switch(msg.action){case "entries":return entries;case "summary":return {places:[{id:PLACE,name:"Test"}],job:{status:"idle"}};case "detail":return structuredClone(data);case "edit":return {saved:true};case "portal_profile":return {test:"<img src=x onerror=alert(1)>"};default:return {};}
  }};
  await element.load();return {element,calls};
}
test("MND přehled nepromění neznámé hodnoty na nulu a escapuje názvy",async()=>{
  const {element}=await surface({config:{entry_id:"account-a",place:PLACE,tab:"overview"}});
  assert.match(element.shadowRoot.querySelector('[data-live="flow"]').textContent,/—/);
  assert.match(element.shadowRoot.querySelector('[data-live="gas_today"]').textContent,/—/);
  element._detail.result.consumption={today:{value_m3:"0"},month:{value_m3:null}};
  element.updateLiveMetrics();
  assert.match(element.shadowRoot.querySelector('[data-live="gas_today"]').textContent,/^0/);
  assert.match(element.shadowRoot.querySelector('[data-live="gas_month"]').textContent,/—/);
  assert.equal(element.shadowRoot.querySelector("h1").textContent,"Test");
  assert.equal(element.shadowRoot.querySelector("test"),null);
  element.hass={...element._hass,themes:{darkMode:true}};
  assert.equal(element.hasAttribute("dark"),true);
});
test("šest generovaných pohledů sdílí MND kartu, vazby entit a úplnou navigaci",async()=>{
  const template=JSON.parse(await readFile(new URL("../custom_components/mnd_tariff_accounting/dashboard_template.json",import.meta.url),"utf8"));
  assert.equal(template.views.length,6);
  for(const view of template.views){
    assert.equal(view.panel,true);assert.equal(view.cards.length,1);
    const config=view.cards[0];assert.equal(config.type,"custom:mnd-accounting-card");assert.equal(config.navigation.length,5);
    const {element}=await surface({config:{...config,entry_id:"account-a",place:PLACE,entities:{current_flow_m3h:"sensor.renamed_flow"}}});
    assert.equal(element.shadowRoot.querySelectorAll("nav a").length,5);
    assert.equal(element.shadowRoot.querySelectorAll("nav [aria-current=page]").length,config.tab==="editor"?0:1);
    assert.equal(element.shadowRoot.querySelectorAll("form,input[type=file],#dashboard-preview").length,0);
    if(config.tab==="overview"){
      let entity; element.addEventListener("hass-more-info",event=>entity=event.detail.entityId);
      element.shadowRoot.querySelector("[data-entity]").click();assert.equal(entity,"sensor.renamed_flow");
    }
  }
});
test("více účtů se samo nesloučí ani nevybere první",async()=>{
  const {element,calls}=await surface({entries:[{id:"one",name:"One"},{id:"two",name:"Two"}]});
  assert.equal(element._entry,null);assert.equal(calls.some(c=>c.action==="detail"),false);
  assert.equal(element.shadowRoot.querySelectorAll("#entry option").length,3);
});
test("profil se načte teprve akcí a jeho HTML zůstane textem",async()=>{
  const data=detail();data.place.settings.portal={cp_id:1};
  const {element,calls}=await surface({data});element._tab="history";element.render();
  assert.equal(calls.some(c=>c.action==="portal_profile"),false);
  await element.shadowRoot.getElementById("portal-profile").onclick();
  assert.equal(calls.filter(c=>c.action==="portal_profile").length,1);
  assert.equal(element.shadowRoot.querySelector("pre img"),null);
  assert.match(element.shadowRoot.querySelector("pre").textContent,/<img/);
  assert.equal(element.shadowRoot.getElementById("file").accept,".xlsx,.json,.zip,.pdf");
});
test("celé období záloh se odesílá jednou transakcí, vyšší úhrada se neomezí",async()=>{
  const {element,calls}=await surface();element._tab="editor";element.render();
  const row=element.shadowRoot.querySelector('[data-month="2026-01"]');
  row.querySelector('[name="prescribed"]').value="500";row.querySelector('[name="paid"]').value="750";row.querySelector('[name="paid_on"]').value="2026-01-05";
  await element.shadowRoot.getElementById("save-advances").onclick();
  const edits=calls.filter(c=>c.action==="edit");assert.equal(edits.length,1);assert.equal(edits[0].payload.revision,7);
  assert.equal(edits[0].payload.record.rows[0].paid,"750");assert.equal(edits[0].payload.record.rows[1].paid,"");
});
test("PDF kandidáti zůstávají nepotvrzeným návrhem",async()=>{
  const {element,calls}=await surface();element._tab="history";
  element._importPreview={rows:0,rejected:0,warnings:[],proposal:{candidates:[{kind:"surplus",value:"100",unit:"Kč",context:"Syntetický přeplatek"}]}};
  element.render();assert.match(element.shadowRoot.textContent,/pouze návrh/);
  assert.equal(calls.some(c=>c.action==="edit"),false);
});
test("opožděná odpověď původního místa se po přepnutí odmítne",async()=>{
  const {element}=await surface();let finish;
  element._hass.callWS=()=>new Promise(resolve=>finish=resolve);
  const pending=element.command("portal_profile");element._place="27ZG000Z0000000Y";
  finish({private:"old place"});await assert.rejects(pending,/selection_changed/);
});
test("anglické zobrazení velkého desetinného čísla neztrácí desetinná místa přes Number",async()=>{
  const {element}=await surface();element.hass={...element._hass,language:"en"};
  assert.equal(element.number("100000000000000.125","m³"),"100,000,000,000,000.125 m³");
});
test.after(()=>window.happyDOM.abort());

test("chyba s číselným kódem ukončí spinner a opakování obnoví data",async()=>{
  const {element}=await surface({config:{entry_id:"account-a",place:PLACE}});
  const original=element._hass.callWS;
  element._detail=null;element._hass.callWS=async()=>{throw {code:3};};
  await element.load({force:true});
  assert.match(element.shadowRoot.textContent,/nepodařilo/);
  assert.doesNotMatch(element.shadowRoot.textContent,/Načítání…/);
  assert.ok(element.shadowRoot.getElementById("retry-load"));
  element._hass.callWS=original;await element.load({force:true});
  assert.equal(element._failed,false);assert.equal(element.shadowRoot.getElementById("retry-load"),null);
});

test("čtecí zálohy zobrazí částečnou úhradu a detail bez administračních formulářů",async()=>{
  const data=detail();data.place.portal_evidence={advances:{rows:[{id:"1",number:"1",kind:"advances",prescribed:"1000",paid:"250",remaining:"750",payments_known:true,payments:[{date:"2026-01-05",amount:"250"}]}]}};
  const {element}=await surface({config:{entry_id:"account-a",place:PLACE,tab:"accounting"},data});
  assert.match(element.shadowRoot.textContent,/1000/);assert.match(element.shadowRoot.textContent,/250/);
  element.shadowRoot.querySelector("[data-finance-id]").click();
  assert.match(element.shadowRoot.textContent,/2026-01-05/);
  assert.equal(element.shadowRoot.getElementById("accept-advances"),null);
  assert.equal(element.shadowRoot.querySelector("[data-finance-export]"),null);
});

test("účetní detaily a spotřeba zachovají periodu, finanční graf i měsíční řadu",async()=>{
  const data=detail();data.result.billing={from:'2026-03-31',to:'2027-04-08',today:'2026-10-16',actual_through:'2026-10-11',actual_mwh:'1.23',forecast_mwh:'5',known_cost_czk:null,paid_czk:'0',planned_czk:'2000',forecast_balance_czk:null,known_cost_complete:false,warnings:[],series:{known_cost:[],forecast_cost:[],paid:[{date:'2026-03-31',value:'0'}],planned:[{date:'2027-01-15',value:'2000'}]},months:[{month:'2026-04',m3:'2',complete:true},{month:'2026-05',m3:'1',complete:false},{month:'2026-06',m3:null,complete:false}]};
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'accounting'},data});
  const root=element.shadowRoot;
  assert.match(root.querySelector('.period').textContent,/31\. 3\. 2026.*8\. 4\. 2027/);
  assert.equal(root.querySelectorAll('svg.billing-plot').length,1);
  assert.match(root.querySelector('.billing-summary table').textContent,/Doložená část nákladů—/);
  assert.match(root.querySelector('.billing-summary table').textContent,/Uhrazené zálohy0 Kč/);
  assert.match(root.textContent,/Dnes/);assert.match(root.textContent,/Předpis není platba/);
  assert.equal(root.querySelectorAll('form,input').length,0);
  element.hass={...element._hass,language:'en'};element.render();
  assert.match(root.textContent,/MND billing period/);assert.match(root.textContent,/Estimated total consumption/);
  element._tab='readings';element.render();
  assert.equal(root.querySelectorAll('svg.billing-plot rect').length,2);
});

const state=(entity_id,value,unit,extra={})=>({entity_id,state:value,last_updated:new Date().toISOString(),attributes:{unit_of_measurement:unit,...extra}});
const boilerDetail=()=>{
  const data=detail();
  Object.assign(data.place.settings,{boiler_enabled:true,boiler_power_entity:'sensor.synthetic_power',boiler_energy_entity:'sensor.synthetic_energy',flow_entity:'sensor.synthetic_flow'});
  return data;
};

test("hlavní přehled obsahuje tři bloky a nejvýše jeden graf",async()=>{
  const data=detail();data.result.consumption={days:[{date:'2026-10-26',value_m3:'0',complete:false}]};
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE},data});
  assert.deepEqual([...element.shadowRoot.querySelectorAll('h2')].map(n=>n.textContent),['Právě teď','Spotřeba','Vyúčtování','Plyn za posledních sedm dní']);
  assert.equal(element.shadowRoot.querySelectorAll('svg.billing-plot').length,1);
  const overview=element.shadowRoot.querySelector('.overview-grid');
  assert.equal(overview.children.length,3);
  assert.ok([...overview.children].every(n=>n.tagName==='SECTION'));
  assert.equal(overview.nextElementSibling.classList.contains('weekly-consumption'),true);
  assert.equal(element.shadowRoot.querySelectorAll('.billing-summary table').length,0);
  assert.doesNotMatch(element.shadowRoot.textContent,/Elektrický příkon kotle/);
});

test("kompaktní wrapper patří pouze přehledu, ne účetnictví či administraci",async()=>{
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'accounting'}});
  assert.equal(element.shadowRoot.querySelector('.overview-grid'),null);
  const {element:admin}=await surface();
  assert.equal(admin.shadowRoot.querySelector('.overview-grid'),null);
  assert.ok(admin.shadowRoot.querySelector('form[data-section="boiler"]'));
});

test("živý příkon a průtok se aktualizují bez dotazu, ztráty fokusu a formuláře",async()=>{
  const {element,calls}=await surface({config:{entry_id:'account-a',place:PLACE},data:boilerDetail()});
  document.body.append(element);
  const button=element.shadowRoot.querySelector('[data-entity="sensor.synthetic_power"]');button.focus();
  const count=calls.length;
  element.hass={...element._hass,states:{'sensor.synthetic_power':state('sensor.synthetic_power','0.094','kW'),'sensor.synthetic_flow':state('sensor.synthetic_flow','1.291','m³/h')}};
  assert.equal(calls.length,count);
  assert.equal(element.shadowRoot.activeElement,button);
  assert.match(button.textContent,/94 W/);
  assert.match(element.shadowRoot.querySelector('[data-live="flow"]').textContent,/1,291/);
  element.remove();
});

test("stará či neplatná živá hodnota zůstane nedostupná a skutečná nula se zobrazí",async()=>{
  const {element}=await surface({data:boilerDetail()});element._tab='overview';element.render();
  element.hass={...element._hass,states:{'sensor.synthetic_power':{...state('sensor.synthetic_power','94','W'),last_updated:'2020-01-01T00:00:00Z'}}};
  assert.match(element.shadowRoot.querySelector('[data-live="boiler_power"]').textContent,/—/);
  assert.match(element.shadowRoot.querySelector('[data-live="boiler_status"]').textContent,/zastaralý/);
  element.hass={...element._hass,states:{'sensor.synthetic_power':state('sensor.synthetic_power','0','W')}};
  assert.match(element.shadowRoot.querySelector('[data-live="boiler_power"]').textContent,/^0 W/);
});

test("bezezměnový report ze serveru prodlouží platnost jen shodné hodnotě",async()=>{
  const data=boilerDetail();data.result.boiler={power:{value:'94',quality:'current',reported_at:new Date().toISOString()}};
  const {element}=await surface({data});
  element.hass={...element._hass,states:{'sensor.synthetic_power':{...state('sensor.synthetic_power','94','W'),last_updated:'2020-01-01T00:00:00Z'}}};
  assert.equal(element.liveMetrics().power.value,94);
  element.hass={...element._hass,states:{'sensor.synthetic_power':{...state('sensor.synthetic_power','95','W'),last_updated:'2020-01-01T00:00:00Z'}}};
  assert.equal(element.liveMetrics().power.value,null);
});

test("administrace nabídne kompatibilní zdroje a náhled před uložením",async()=>{
  const {element,calls}=await surface({data:boilerDetail()});
  element.hass={...element._hass,states:{'sensor.synthetic_power':state('sensor.synthetic_power','94','W'),'sensor.synthetic_energy':state('sensor.synthetic_energy','20','Wh',{state_class:'total_increasing'}),'sensor.synthetic_gas':state('sensor.synthetic_gas','100','m³')}};
  element.render();const form=element.shadowRoot.querySelector('form[data-section="boiler"]');
  assert.equal(form.querySelector('[name=boiler_enabled]').checked,true);
  assert.equal(form.querySelector('[name=boiler_energy_entity] option[value="sensor.synthetic_gas"]'),null);
  assert.match(form.querySelector('[data-boiler-preview]').textContent,/94 W/);
  await form.onsubmit({preventDefault(){}});
  // run je asynchronní obal; necháme dokončit potvrzený edit/detail.
  await new Promise(resolve=>setImmediate(resolve));
  const edit=calls.find(c=>c.action==='edit');
  assert.equal(edit.payload.section,'boiler');assert.equal(edit.payload.record.id,undefined);
  assert.equal(edit.payload.record.boiler_power_entity,'sensor.synthetic_power');
});

test("výpadek zdroje zachová volbu a nedovolí ztrátu rozepsaného formuláře",async()=>{
  const {element}=await surface({data:boilerDetail()});
  const input=element.shadowRoot.querySelector('form[data-section="settings"] input[name=name]');input.value='Rozpracováno';
  element.hass={...element._hass,states:{}};
  assert.equal(input.value,'Rozpracováno');
  assert.ok(element.shadowRoot.querySelector('[name=boiler_power_entity] option[value="sensor.synthetic_power"]'));
});

test("obnova na pozadí dotazuje jen detail a fokus nezastaví příkon",async()=>{
  const {element,calls}=await surface({config:{entry_id:'account-a',place:PLACE},data:boilerDetail()});
  document.body.append(element);element.shadowRoot.querySelector('[data-entity]').focus();
  const count=calls.length;
  await element.load({background:true});
  assert.deepEqual(calls.slice(count).map(c=>c.action),['detail']);
  assert.ok(element.shadowRoot.activeElement);element.remove();
});

test("chyba obnovy na pozadí zachová fokus a zotavení odstraní upozornění",async()=>{
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE},data:boilerDetail()});
  document.body.append(element);
  const button=element.shadowRoot.querySelector('[data-entity]');button.focus();
  const original=element._hass.callWS;
  element._hass.callWS=async()=>{throw new Error('request_timeout');};
  await element.load({background:true});
  assert.equal(element.shadowRoot.activeElement,button);
  assert.match(element.shadowRoot.getElementById('background-load-error').textContent,/časový limit/);
  element._hass.callWS=original;
  await element.load({background:true});
  assert.equal(element.shadowRoot.activeElement,button);
  assert.equal(element.shadowRoot.getElementById('background-load-error'),null);
  element.remove();
});

test("nativní historie má jediný souběžný mount a dostává aktuální hass",async()=>{
  let release,calls=0,created=0;
  globalThis.loadCardHelpers=()=>{calls++;return new Promise(resolve=>release=resolve);};
  let element;
  try{
    ({element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'readings'},data:boilerDetail()}));
    document.body.append(element);
    await element.mountHistory();
    assert.equal(calls,1);
    release({createCardElement:config=>{created++;assert.equal(config.type,'history-graph');return document.createElement('div');}});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(created,1);
    const card=element._historyCard;
    assert.ok(card);
    const fresh={...element._hass,states:{'sensor.synthetic_power':state('sensor.synthetic_power','95','W')}};
    element.hass=fresh;
    assert.equal(card.hass,fresh);
  }finally{element?.remove();delete globalThis.loadCardHelpers;}
});

test("opožděná nativní historie se po změně podstránky nevloží",async()=>{
  let release,created=0;
  globalThis.loadCardHelpers=()=>new Promise(resolve=>release=resolve);
  let element;
  try{
    ({element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'readings'},data:boilerDetail()}));
    document.body.append(element);
    element._tab='overview';element.render();
    release({createCardElement:()=>{created++;return document.createElement('div');}});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(created,0);
    assert.equal(element._historyCard,null);
    assert.equal(element.shadowRoot.getElementById('boiler-history'),null);
  }finally{element?.remove();delete globalThis.loadCardHelpers;}
});

test("elektřina zůstává v detailu spotřeby a chybějící historie není nula",async()=>{
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'readings'},data:boilerDetail()});
  assert.match(element.shadowRoot.textContent,/Elektřina dnes/);
  assert.match(element.shadowRoot.textContent,/Známá část; data do/);
  assert.match(element.shadowRoot.textContent,/— kWh|—/);
  assert.equal(element.shadowRoot.querySelectorAll('form').length,0);
  assert.ok(element.shadowRoot.querySelector('#boiler-history a[href^="/history?"]'));
});

test("vypnuté měření kotle ponechá pouze plynový graf bez elektrických popisků",async()=>{
  const data=boilerDetail();data.place.settings.boiler_enabled=false;
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE,tab:'readings'},data});
  assert.match(element.shadowRoot.textContent,/Průtok plynu – 24 hodin/);
  assert.doesNotMatch(element.shadowRoot.textContent,/Elektrická spotřeba kotle|Elektrický příkon kotle|Požadavek termostatu|provoz kotle/);
  const href=element.shadowRoot.querySelector('#boiler-history a').getAttribute('href');
  assert.match(decodeURIComponent(href),/sensor.synthetic_flow/);
  assert.doesNotMatch(decodeURIComponent(href),/synthetic_power|synthetic_energy/);
});

test("anglický kompaktní přehled a validace kotle používají anglické popisky",async()=>{
  const {element}=await surface({config:{entry_id:'account-a',place:PLACE},data:boilerDetail()});
  element.hass={...element._hass,language:'en'};element.render();
  assert.match(element.shadowRoot.textContent,/Right now/);
  assert.match(element.shadowRoot.textContent,/Boiler electric power/);
  assert.doesNotMatch(element.shadowRoot.textContent,/Elektrický příkon kotle/);
  assert.equal(element.errorText(new Error('boiler_power_required')),'Select the boiler electric power sensor.');
});

test("historický pulsní zdroj je dostupný pouze v konfiguraci zařízení",async()=>{
  const {element}=await surface();
  element._hass.states={'sensor.pulses':{entity_id:'sensor.pulses',state:'100',attributes:{unit_of_measurement:'pulse',state_class:'total_increasing'}}};
  element._tab='editor';element.render();
  assert.ok(element.shadowRoot.querySelector('[name=history_source_entity] option[value="sensor.pulses"]'));
  assert.ok(element.shadowRoot.querySelector('[name=history_unit_m3]'));
  assert.equal(element.shadowRoot.querySelector('[name=source_entity] option[value="sensor.pulses"]'),null);
});
