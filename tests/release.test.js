/* Testuje skutečný pomocník releasu s místními syntetickými soubory a falešným
 * GitHub klientem. Jakékoli mazání či publikování chybí i v seznamu metod. */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import {createRequire} from "node:module";
const {attachInstaller}=createRequire(import.meta.url)("../scripts/attach_release_installer.cjs");
const data=Buffer.from("synthetic installer"), digest="sha256:"+crypto.createHash("sha256").update(data).digest("hex");
const folder=fs.mkdtempSync(path.join(os.tmpdir(),"mnd-release-node-"));
fs.writeFileSync(path.join(folder,"mnd_tariff_accounting.zip"),data);fs.writeFileSync(path.join(folder,"release-notes.md"),"Synthetic notes");
const core={notice(){},summary:{addHeading(){return this;},addLink(){return this;},addRaw(){return this;},async write(){}}};
function client(releases){const calls=[];return {calls,github:{paginate:async()=>releases,rest:{repos:{listReleases(){},createRelease:async payload=>{calls.push(["create",payload]);return {data:{id:1,assets:[],draft:true,html_url:"https://example.invalid/release"}};},uploadReleaseAsset:async payload=>{calls.push(["upload",payload]);return {data:{state:"uploaded",size:data.length,digest}};}}}}};}
const run=(fixture,extra={})=>attachInstaller({github:fixture.github,context:{repo:{owner:"synthetic",repo:"mnd"}},core,tag:"v0.1.0",directory:folder,...extra});
test("nové vydání zůstává draftem a obsahuje instalátor",async()=>{
  const fixture=client([]);const result=await run(fixture);
  assert.equal(result.published,false);assert.equal(fixture.calls[0][1].draft,true);assert.equal(fixture.calls[1][0],"upload");
});
test("identický published asset se pouze ověří a nenahrává znovu",async()=>{
  const fixture=client([{tag_name:"v0.1.0",draft:false,assets:[{name:"mnd_tariff_accounting.zip",state:"uploaded",size:data.length,digest}]}]);
  const result=await run(fixture);assert.equal(result.published,true);assert.equal(fixture.calls.length,0);
});
test("published release bez instalátoru se odmítne změnit",async()=>{
  const fixture=client([{tag_name:"v0.1.0",draft:false,assets:[]}]);
  await assert.rejects(run(fixture),/Refusing/);assert.equal(fixture.calls.length,0);
});
test("neshodný obsah existujícího assetu se nenahradí",async()=>{
  const older=Buffer.from("different package");
  const fixture=client([{tag_name:"v0.1.0",draft:true,assets:[{name:"mnd_tariff_accounting.zip",state:"uploaded",size:older.length}]}]);
  await assert.rejects(run(fixture,{download:async()=>older,verify:()=>{throw new Error("content differs");}}),/content differs/);
  assert.equal(fixture.calls.length,0);
});
test.after(()=>{fs.unlinkSync(path.join(folder,"mnd_tariff_accounting.zip"));fs.unlinkSync(path.join(folder,"release-notes.md"));fs.rmdirSync(folder);});
