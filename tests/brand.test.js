/* Distribuční pravidla brand ikon: skutečné PNG, přesné rozměry a alfa. */
import test from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import sharp from "sharp";
for(const [file,size] of [["icon.png",256],["dark_icon.png",256],["icon@2x.png",512],["dark_icon@2x.png",512]]){
  test("brand "+file+" má správné rozměry a průhledné ochranné okraje",async()=>{
    const image=sharp(fileURLToPath(new URL("../custom_components/mnd_tariff_accounting/brand/"+file,import.meta.url)));
    const info=await image.metadata();assert.equal(info.format,"png");assert.equal(info.width,size);assert.equal(info.height,size);assert.equal(info.hasAlpha,true);
    const {data,info:raw}=await image.raw().toBuffer({resolveWithObject:true});
    assert.equal(data[raw.channels-1],0);assert.equal(data[data.length-1],0);
    assert.ok(data.some((value,index)=>index%raw.channels===raw.channels-1&&value===255));
  });
}
