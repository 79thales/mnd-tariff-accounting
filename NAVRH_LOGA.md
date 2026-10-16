# Návrh loga — MND Tariff & Accounting for Home Assistant

## Koncept „Dům, plyn a účetní přehled“

Zelený obrys domu propojuje centrální plamen se třemi sloupci spotřeby/účetnictví. Symbol představuje domácnost, plyn a přehled nad náklady; název aplikace je případně vedle ikony, nikoli uvnitř malé značky.

Návrh je originální značka komunitní integrace. Nekopíruje wordmark MND ani znak Home Assistantu a nevyjadřuje oficiální partnerství. Inspirací je čitelnost energetického přehledu a zelená barevnost, nikoli úprava oficiálního loga.

Soubor: [mnd-tariff-accounting-concept.png](brand-concept/mnd-tariff-accounting-concept.png). Jde o **rastrový koncept**, ne o hotovou sadu brand assets pro release.

- Tmavě zelená pro konstrukci domu: navržená paleta `#245544`.
- Limetková pro plamen/energii: navržená paleta `#A7C42A`.
- Průhledné pozadí; jednoduchá čtvercová značka bez drobného textu.
- Plné dlouhé jméno: **MND Tariff & Accounting for Home Assistant**.
- Krátký popisek v horní liště dashboardu: **MND** nebo uživatelem zvolený název místa.

Paleta představuje návrhové hodnoty. Generovaný raster může obsahovat další odstíny a jemné nerovnosti; přesnou barevnost a čisté hrany musí finální grafická příprava sjednotit. Neprohlašuj tento soubor za technicky ověřený distribuční asset.

## Dokončení při implementaci

Připrav produkční ikonu, variantu pro tmavé pozadí a podle potřeby vodorovné logo s názvem. Vyzkoušej zobrazení ve 32/64 px i v dialogu konfigurace HA. U tmavého tématu může být nutné zesvětlení obrysu, aby nezanikl. Ověř průhlednost, ochrannou zónu a absence nechtěného pozadí. Barva musí být doplněna významem tvaru, nikoli být jediným rozlišením.

Finální soubory patří do `custom_components/mnd_tariff_accounting/brand/`, minimálně `icon.png`; další varianty a rozměry ověř podle aktuálních pravidel HA/HACS. Tento runtime adresář se v přípravě nevytváří. Zdrojová/editovatelná grafika může být později ve zvláštním `brand/` adresáři; její použití musí být popsáno.

Od HA 2026.3 lze brand obrázky custom integrace balit místně; pro detaily použij [oficiální dokumentaci brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/). Případné podání do centrálního brands repozitáře není součástí této přípravy.

## Původ návrhu

Vytvořeno 15. 10. 2026 vestavěným nástrojem imagegen, bez předlohy a s průhledným pozadím. Do cílové složky zkopírován beze změny; původní výstup nástroje zachován. Nebyl psán SVG ani jiný aplikační kód.

Použitý prompt:

> Create a polished minimalist app icon concept for an independent community Home Assistant integration named 'MND Tariff & Accounting for Home Assistant'. Output one single centered icon only, no text or letters anywhere, transparent background. A bold rounded geometric house outline in deep forest green #245544 encloses one elegant lime green gas flame #A7C42A. Integrate three small ascending rounded ledger/chart bars subtly into the lower right of the house, as a coherent part of the mark, not a separate floating badge. Use only two solid colors, crisp flat vector-like graphic shapes, generous negative space, balanced optical weight, slightly rounded corners. Make it clean and legible at 32px, with thick structural strokes and no tiny details, no gradients, no shadows, no glass or 3D, no mockup, no border square or backdrop. Original brand identity, do not reproduce the official MND wordmark or the Home Assistant logo. Square canvas, icon occupies around 78 percent of canvas with transparent padding on every side. Professional restrained Czech energy accounting tool.

## Produkční podoba z 16. 10. 2026

Runtime nyní obsahuje `brand/icon.png`, `icon@2x.png`, `dark_icon.png` a
`dark_icon@2x.png`, přesně 256/512 px s alfa kanálem. Zdroj je vlastní
editovatelná geometrie v `brand/icon.svg`, nikoli převzaté logo MND nebo HA.
Zelená je sjednocena s veřejným portálem na `#2b6e33`, limetková `#a8be32`;
tmavá varianta používá světlý obrys `#d7e9d2`. Pozadí je průhledné.

Reprodukovatelný vývojový export: `node scripts/render_brand.cjs` po instalaci
uzamčených Node závislostí. Renderer současně aktualizuje vložené SVG panelu,
takže značka na dashboardu vychází ze stejného zdroje jako PNG integrace.
Vizuálně byl zkontrolován export a kontrolní list ve 32/64 px na světlé i
tmavé ploše (`output/brand/sizes-32-64.png`). Jde o kontrolu souborů,
nikoli dosud neprovedenou kontrolu konfiguračního dialogu v běžícím HA.

Původní imagegen varianty zůstaly jako koncepty, bez retuše původních PNG.
Jejich přesné prompty, použitý vestavěný nástroj a uložené cesty jsou v
[BRAND_KANDIDATI.md](docs/BRAND_KANDIDATI.md). Finální SVG/PNG jsou nový
nativní grafický asset projektu, exportovaný knihovnou sharp. Rozměry a
průhlednost ověřují testy `tests/brand.test.js` podle pravidel HA Brands.
