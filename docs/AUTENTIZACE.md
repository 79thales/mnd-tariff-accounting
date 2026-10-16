# Přenos portálu Moje MND

16. 10. 2026 byly bez přihlášení načteny veřejné HTML `/login`, `/config.json`
a jeho veřejné JS chunky. Konfigurace uvádí baseUrl `https://moje.mnd.cz`.
SHA zdrojů lze lokálně reprodukovat nástrojem `scripts/probe_portal.py`.
Převzaté veřejné JS nejsou součástí runtime ani verzovaných zdrojů.

Veřejný `_app-d4693e13afff6e1f.js` dokládá následující kontrakty:

| Operace | Doložený požadavek |
| --- | --- |
| Login | POST `/api/SignInToInternetAccount`, JSON `UserName`, `Password`; UI čte `InaToken`, `Partners` |
| Partneři | GET `/api/partners`, hlavička `inaToken`; UI čte `PARTNER_ID` |
| Místa | GET `/api/consumptionPlaces`, `partnerId`, hlavička `Inatoken`; UI čte `CP_ID`, `CONT_ID` |
| Detail | GET `/api/consumptionPlace`, `cpId`, `contractId` |
| Odečty | GET `/api/readings`, `cpId`, `contractId`, `years=3` (počet let, nikoli seznam) |
| Spotřeba | GET `/api/consumptions`, stejné parametry |
| Smluvní doklady | GET `/api/contractDocs`, `cpId`, `contractId` |
| Profil | GET `/api/inaOtherDetail`, `partnerId` |
| Platby | GET `/api/payments`, `partnerId`, `custaId`, `caccId=170`, `cpId`, `maxRowCount`, `skipRowCount` |
| Export odečtů | POST `/api/Documents/ReadingsExport`, JSON `CP_ID`, `CONT_ID`, `OD`, `DO`, `PERIOD="R"`; data `yyyy-MM-dd 00:00:00` / `yyyy-MM-dd 23:59:00` |
| Soubor | GET `/data/Documents/GetByGuid?docGuid=…`, GUID z předchozí autorizované operace, bez přenesení tokenu do souborového požadavku |
| Cenový doklad | POST `/api/Documents/ContractDocByPrice`, parametry `cpId`, `contractId`, `priceId`, `coeId` nebo `cadcoeId`; UI čte `DocumentGuid`, `FileName` |
| Odhlášení | Veřejné UI vymaže sessionStorage a vlastní stav; serverové zneplatnění tokenu nebylo doloženo |

Tyto údaje dokazují existenci kontraktu v publikovaném klientovi. Nedokazují
úspěšné přihlášení z HA, platnost datového schématu účtu ani absenci MFA.
Na reálný účet se při tomto průzkumu nepřihlašovalo. Přístupy ze starých
příloh nebyly čteny. Klient neimplementuje neověřený univerzální download
podle uživatelské URL ani automatické účetní zaúčtování neznámé odpovědi.

Token zůstává v paměti klienta, chyby obsahují pouze reason code. Pokud
uživatel zvolí cloudový režim, HA standardně ukládá jeho konfigurační údaje
do vlastního úložiště; to není šifrovaný trezor. Záloha HA musí být chráněna.
Při odmítnutí přístupu se nepokračuje stejným heslem ve smyčce. 429 má
odstup podle Retry-After, přechodné GET chyby nejvýše tři pokusy, login jeden.
