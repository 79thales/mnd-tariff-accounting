# Changelog

## 0.1.0 — vývojová verze

### Čeština

- První Python implementace importů XLSX/C# v1, auditní evidence, měření,
  záloh, plateb a faktur; účetní engine rozlišuje neznámé údaje a nuly.
- Soukromá záloha s originály, historie prognóz, nativní HA konfigurace,
  panel a společný generátor/šablona hlavního view a pěti detailů.
- Cloudový klient podle veřejného JS MND; úspěšný živý test nové integrace
  ani kompatibilita celé HA matice zatím nebyly potvrzeny.
- Vzhled odvozený od Moje MND, vlastní vektorová značka a světlé/tmavé téma.
- Účtování přesných časových hranic včetně DST a zachování vypořádání faktury
  při její pozdější opravě; historická prognóza se porovnává jen s doloženou skutečností.

### English

- Initial Python XLSX/C# v1 imports, audit records, metering, advances,
  payments and invoices; unknown inputs remain distinct from confirmed zeros.
- Private backups with originals, forecast snapshots, native HA configuration,
  panel and a shared dashboard generator/template with five detail subviews.
- Cloud client follows the public MND JavaScript contract. Live validation
  of the new integration and the full HA compatibility matrix are pending.
- Moje MND inspired interface, original vector mark and light/dark themes.
- Exact timestamp accounting including DST and invoice settlement continuity
  across corrections; forecast comparisons require documented actual values.
