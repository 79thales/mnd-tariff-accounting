# Kandidáti brand obrázků z 16. 10. 2026

Vytvořeno vestavěným imagegen, beze změny zkopírováno do projektu.

- `brand-concept/icon-light-candidate.png`
- `brand-concept/icon-dark-candidate.png`

Oba obrázky mají průhledné pozadí. Kontrola velkého rasteru odhalila zrnění a nečistoty kolem hran; proto nejsou označeny za hotové distribuční brand assets a nebyly vloženy do runtime. Produkční sada je samostatně vytvořená čistá vektorová geometrie v `brand/icon.svg`, exportovaná skriptem `scripts/render_brand.cjs`. Návrhové PNG nebyly upravovány ani použity jako distribuční asset. Barvy UI již vycházejí z ověřené palety Moje MND, nikoli z tohoto rasteru.

## Prompt světlé varianty

Use case: logo-brand. Make one production app icon for an independent community gas-accounting Home Assistant integration. Reference image is identity reference only; redraw the same house, flame and three ascending bars from scratch as perfectly clean geometric flat vector-like shapes. The prior raster has unwanted grain around the flame; remove ALL of that grain in this new rendering. Use exactly solid MND-like green #2b6e33 for a thick rounded house outline and chart bars, and solid lime #a8be32 for one simple stylized flame. No texture, gradient, speckle, halo, highlights, glow, shadow or 3D. No words. Geometric shape edges must be smooth antialiased edges only. Center on a fully transparent square canvas with 15 percent padding on every side. Broad shapes readable at 32 pixels. Do not copy the official MND wordmark or Home Assistant symbol. This is the light-background icon. Return one image only.

## Prompt tmavé varianty

Use case: logo-brand. Create a NEW clean flat pictogram app icon suitable for dark mode. Simple thick pale mint green #D7E9D2 outline of a rounded house, containing a solid lime green #A8BE32 gas flame and three ascending mint chart bars integrated into lower right baseline of house. The independent community app is MND Tariff & Accounting for Home Assistant. Square icon, large simple bold shapes, smooth edges, exactly two solid flat colors, fully transparent background. No text, no dark backing plate, no texture, no gradients, no shadows, no speckles, no glow, no hairlines. Design as if it were a mathematically clean SVG pictogram exported to PNG. Center complete house inside 15 percent transparent padding all around. Visually consistent gas/house/accounting identity. Not official MND wordmark or Home Assistant logo. One standalone icon only.
