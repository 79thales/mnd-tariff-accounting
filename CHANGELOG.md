# Changelog

## 0.1.0-alpha.1 — vývojová verze

### Čeština

- První Python implementace importů XLSX/C# v1, auditní evidence, měření,
  záloh, plateb a faktur; účetní engine rozlišuje neznámé údaje a nuly.
- Soukromá záloha s originály, historie prognóz, nativní HA konfigurace,
  panel a společný generátor/šablona hlavního view a pěti detailů.
- Cloudový klient podle veřejného JS MND; živý test účtu, úplné automatické
  smluvní ceny a živá mapa platebního stavu zatím nejsou dokončeny.
- Quality, HACS a Hassfest ověřeny, 100 Python a 21 Node testů úspěšně;
  16 skutečných HA testů na 2026.3.1 i 2026.10.1 v Linuxu.
- Vzhled odvozený od Moje MND, vlastní vektorová značka a světlé/tmavé téma.
- Účtování přesných časových hranic včetně DST a zachování vypořádání faktury
  při její pozdější opravě; historická prognóza se porovnává jen s doloženou skutečností.

### English

- Initial Python XLSX/C# v1 imports, audit records, metering, advances,
  payments and invoices; unknown inputs remain distinct from confirmed zeros.
- Private backups with originals, forecast snapshots, native HA configuration,
  panel and a shared dashboard generator/template with five detail subviews.
- Cloud client follows the public MND JavaScript contract. Live account
  validation, complete automatic contract pricing and live payment-status
  mapping are pending.
- Quality, HACS and Hassfest passed: 100 Python and 21 Node tests, plus
  16 real HA tests on each of 2026.3.1 and 2026.10.1 under Linux.
- Moje MND inspired interface, original vector mark and light/dark themes.
- Exact timestamp accounting including DST and invoice settlement continuity
  across corrections; forecast comparisons require documented actual values.
