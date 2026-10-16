/* Reprodukovatelný export nového nativního SVG do brand PNG pro HA.
 * Neupravuje rastrové koncepty. Zdroj je vlastní geometrie v brand/icon.svg.
 * sharp je vývojová závislost; runtime nemá síť ani závislost na rendereru.
 * Výstup: ikony 256/512 px a ignorovaný kontrolní list ve 32/64 px. */
const fs=require("node:fs/promises");
const path=require("node:path");
const sharp=require("sharp");
const root=path.resolve(__dirname,"..");
async function render(){
  const svg=await fs.readFile(path.join(root,"brand/icon.svg"),"utf8");
  // Stejný vlastní SVG zdroj pro záhlaví panelu i obě PNG varianty HA.
  // SVG není uživatelský upload; obsah se sestavuje jen při vývoji.
  const frontend=path.join(root,"custom_components/mnd_tariff_accounting/frontend/mnd-panel.js");
  const mark=svg.replace(/<!--[\s\S]*?-->/g,"").replaceAll("#2b6e33","var(--mnd-mark,#2b6e33)").replaceAll("#a8be32","var(--mnd-lime,#a8be32)").replace(/\s+/g," ").trim();
  const javascript=await fs.readFile(frontend,"utf8");
  if(!javascript.includes("/* BRAND_ICON_START"))throw new Error("Chybí hranice generované ikony panelu.");
  await fs.writeFile(frontend,javascript.replace(/\/\* BRAND_ICON_START[\s\S]*?\/\* BRAND_ICON_END \*\//,
    "/* BRAND_ICON_START — generuje scripts/render_brand.cjs z brand/icon.svg. */\nconst BRAND_ICON = "+JSON.stringify(mark)+";\n/* BRAND_ICON_END */"));
  const destination=path.join(root,"custom_components/mnd_tariff_accounting/brand");
  await fs.mkdir(destination,{recursive:true});
  const small=[];
  for(const dark of [false,true]){
    const source=dark?svg.replaceAll("#2b6e33","#d7e9d2"):svg;
    for(const size of [256,512]){
      const name=(dark?"dark_":"")+"icon"+(size===512?"@2x":"")+".png";
      await sharp(Buffer.from(source)).resize(size,size).png({compressionLevel:9,progressive:true}).toFile(path.join(destination,name));
    }
    for(const size of [32,64]){
      const icon=await sharp(Buffer.from(source)).resize(size,size).png().toBuffer();
      const tile=await sharp({create:{width:100,height:100,channels:4,background:dark?"#17201b":"#ffffff"}}).composite([{input:icon,left:(100-size)/2,top:(100-size)/2}]).png().toBuffer();
      small.push({input:tile,left:small.length*100,top:0});
    }
  }
  const previews=path.join(root,"output/brand");await fs.mkdir(previews,{recursive:true});
  await sharp({create:{width:400,height:100,channels:4,background:"#ffffff"}}).composite(small).png().toFile(path.join(previews,"sizes-32-64.png"));
}
render().catch(error=>{process.stderr.write(error.message+"\n");process.exitCode=1;});
