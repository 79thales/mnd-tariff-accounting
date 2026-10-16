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
  const values=[...element.shadowRoot.querySelectorAll(".value")].map(e=>e.textContent);
  assert.match(values[0],/—/);assert.match(values[4],/^0/);assert.match(values[5],/—/);
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
    const {element}=await surface({config:{...config,entry_id:"account-a",place:PLACE,entities:{latest_mnd:"sensor.renamed_meter"}}});
    assert.equal(element.shadowRoot.querySelectorAll("nav a").length,5);
    assert.equal(element.shadowRoot.querySelectorAll("nav [aria-current=page]").length,config.tab==="editor"?0:1);
    assert.equal(element.shadowRoot.querySelectorAll("form,input[type=file],#dashboard-preview").length,0);
    if(config.tab==="overview"){
      let entity; element.addEventListener("hass-more-info",event=>entity=event.detail.entityId);
      element.shadowRoot.querySelector("[data-entity]").click();assert.equal(entity,"sensor.renamed_meter");
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
