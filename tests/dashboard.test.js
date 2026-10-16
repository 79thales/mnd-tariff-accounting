import test from "node:test";
import assert from "node:assert/strict";
import {addViews,mergeViews} from "../custom_components/mnd_tariff_accounting/frontend/mnd-panel.js";

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
