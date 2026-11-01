import test from "node:test";
import assert from "node:assert/strict";
import {accountingCard,addViews,mergeViews} from "../custom_components/mnd_tariff_accounting/frontend/mnd-panel.js";

test("obal migruje přímou kartu a opakovaná aktualizace zachová místní entity",()=>{
  const card={type:"custom:mnd-accounting-card",entry_id:"synthetic",place:"synthetic",entities:{local:"sensor.synthetic"}};
  const next=[{path:"mnd",cards:[{type:"vertical-stack",cards:[{...card,entities:{new:"sensor.new"}}]}]}];
  const current={views:[{path:"mnd",cards:[card,{type:"markdown",content:"Poznámka"}]}]};
  const first=mergeViews(current,next,{update:true});
  const second=mergeViews(first,next,{update:true});
  assert.deepEqual(first,second);
  assert.equal(first.views[0].cards[0].type,"vertical-stack");
  assert.deepEqual(accountingCard(first.views[0].cards[0]).entities,{local:"sensor.synthetic",new:"sensor.new"});
  assert.deepEqual(first.views[0].cards[1],current.views[0].cards[1]);
  const ambiguous={views:[{path:"mnd",cards:[{type:"vertical-stack",cards:[card,card]}]}]};
  assert.throws(()=>mergeViews(ambiguous,next,{update:true}),/foreign_view_conflict/);
});

test("přidání zachová celý cizí pohled a konfiguraci",()=>{
  const current={title:"Home",theme:"local",views:[{path:"home",cards:[{type:"custom:local"}]}]};
  const before=structuredClone(current);
  const result=mergeViews(current,[{path:"mnd",cards:[]},{path:"mnd-detail",subview:true}]);
  assert.deepEqual(current,before);assert.deepEqual(result.views[0],before.views[0]);assert.equal(result.theme,"local");assert.equal(result.views.length,3);
});
test("kolize se nepřepíše a duplicitní cesty se odmítnou",()=>{
  assert.throws(()=>mergeViews({views:[{path:"mnd"}]},[{path:"mnd"}]),/view_exists/);
  assert.throws(()=>mergeViews({views:[]},[{path:"mnd"},{path:"mnd"}]),/duplicate_view_path/);
});
test("změna po náhledu zastaví zápis",async()=>{
  let writes=0;const call=async msg=>{if(msg.type==="get_panels")return {lovelace:{config:{mode:"storage"}}};if(msg.type==="lovelace/config")return {views:[{path:"changed"}]};writes++;};
  await assert.rejects(addViews(call,{views:[]},[{path:"mnd"}]),/overview_changed/);assert.equal(writes,0);
});
test("ztracená odpověď se ověří čtením bez druhého zápisu",async()=>{
  let current={views:[]};let writes=0;
  const call=async msg=>{if(msg.type==="get_panels")return {lovelace:{config:{mode:"storage"}}};if(msg.type==="lovelace/config")return structuredClone(current);current=msg.config;writes++;throw new Error("response lost");};
  await addViews(call,{views:[]},[{path:"mnd"}]);assert.equal(writes,1);assert.equal(current.views.length,1);
});
test("YAML a automatický Overview mají pouze export",async()=>{
  await assert.rejects(addViews(async()=>({lovelace:{config:{mode:"yaml"}}}),{views:[]},[{path:"mnd"}]),/overview_not_storage/);
  assert.throws(()=>mergeViews({views:[],strategy:{type:"original-states"}},[{path:"mnd"}]),/overview_not_editable/);
});

test("aktualizace staré šablony zachová cizí karty, místní název a pořadí",()=>{
  const card={type:"custom:mnd-accounting-card",entry_id:"one",place:"p",tab:"editor",local_setting:42};
  const current={theme:"local",views:[{path:"home",cards:[]},{path:"mnd",title:"Můj název",cards:[card,{type:"markdown",content:"Místní poznámka"}]}]};
  const next=[{path:"mnd",cards:[{...card,tab:"overview",layout_version:2}]}];
  const result=mergeViews(current,next,{update:true});
  assert.deepEqual(result.views[0],current.views[0]);assert.equal(result.views[1].title,"Můj název");
  assert.deepEqual(result.views[1].cards[1],current.views[1].cards[1]);assert.equal(result.views[1].cards[0].tab,"overview");
  assert.equal(current.views[1].cards[0].tab,"editor");assert.equal(result.theme,"local");
  assert.throws(()=>mergeViews(current,[{path:"mnd",cards:[{...card,entry_id:"other"}]}],{update:true}),/foreign_view_conflict/);
});
