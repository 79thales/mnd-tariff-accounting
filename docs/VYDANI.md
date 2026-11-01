# Testování a vydání

Závazný zdroj pravidel: [GIT_POLITIKY_CEZ.md](../GIT_POLITIKY_CEZ.md).
Nový projekt má vlastní historii a větev `master_HA`; reference se nemění.

Před vydáním musí projít unit/Node/Ruff, skutečné Linux lifecycle testy,
HACS a Hassfest. Připravené workflow není úspěšná kontrola. Staged diff
a celý ZIP se prohlédnou kvůli soukromým údajům i nečekaným binárním souborům.
Verze manifestu, tagu a CS/EN changelogu musí souhlasit.

Podle výslovné volby uživatele obsahují GitHub release notes pouze češtinu.
Zdrojový CHANGELOG zachovává český i anglický oddíl; generátor ze zvolené
verze vybere jen neprázdnou sekci **Čeština**. Anglický text do souboru
`release-notes.md` ani nového draftu nepřenáší. Chybějící český oddíl je chyba
sestavení. Tato volba nemění instalační runtime ani existující tagy a assety.

Resolver 16. 10. 2026 našel stable HA 2026.10.1, plugin 0.13.372 a Python 3.14.
Minimum bylo upraveno na 2026.3.1/plugin 0.13.317: plugin pro přesné 2026.3.0
nebyl nalezen. Metadata pro 2026.3.0 vyžadují Python >=3.14.2; sousední pluginy
cílí 2026.2.3 a potom 2026.3.1. Obě zvolené varianty již prošly 16 skutečnými
HA testy v Linuxu; Quality obsahuje také 100 doménových/protokolových testů
a 21 Node testů. Stejné kontroly jsou povinné i pro finální alpha revizi.

První balíček má verzi `0.1.0-alpha.1` a tag `v0.1.0-alpha.1`. Nejprve vznikl
jako draft; 16. 10. 2026 byl po kontrole zveřejněn jako testovací prerelease,
aby byl instalační ZIP dostupný pro HACS. Nejde o potvrzení dokončeného
cloudového mapování ani živého ověření MND. Workflow nadále vytváří pouze
draft, samostatná publikace nezměnila tag ani obsah původního assetu.

U `zip_release: true` nestačí zelená validace HACS a veřejný zdrojový kód.
Instalátor ve skrytém draftu není pro HACS ke stažení. Po publikaci ověřte
anonymní GET veřejného release API i download URL: HTTP 200, správný název
ZIP, velikost a SHA-256 přesného tagovaného buildu. Předběžné vydání se v HACS
vybírá po zapnutí beta verzí; commit výchozí větve nemá release ZIP.
Viz [zdroj stahování HACS](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py).

```text
python scripts/build_release.py --ref vX.Y.Z --expected-tag vX.Y.Z
```

Runtime i notes se čtou z Git stromu revize. ZIP má `manifest.json` a
`__init__.py` přímo v kořeni, časy z UTC commitu a žádné symlinky.
Název je `mnd_tariff_accounting.zip`; nebalí se pracovní adresář.

Workflow nejprve vyžaduje Quality/HACS/Hassfest a pak připraví balík a draft.
Existující asset ověří, nikdy ho nenahradí. Chybějící instalátor publikovaného
releasu je chyba kontroly. Oprava vyžaduje novou verzi, nikoli přepsání tagu.
Publikace draftu a nasazení do živého HA mají samostatné oprávnění.

## Release candidate 1.0.1 a katalog HACS

Uživatel pro přihlášení do katalogu zvolil `1.0.1-rc.1` a GPL-3.0-only.
Manifest a neměnný tag `v1.0.1-rc.1` musí souhlasit. Pomocník releasu pozná
příponu `-rc.1` a vytvoří **draft s `prerelease: true`**; nevydává stabilní
1.0.1. ZIP obsahuje plný `LICENSE` a `THIRD_PARTY_NOTICES.md` s původním
MIT oznámením převzatých částí. Kořenový a přibalený GPL text musí být shodné.

Přihlášení navazuje na přijatý PR ČEZ
[hacs/default#10242](https://github.com/hacs/default/pull/10242). Podle
[aktuálních podmínek HACS](https://www.hacs.xyz/docs/publish/include/)
je pořadí následující:

1. Ověřit přesný commit: Quality, HACS bez `ignore`, Hassfest a instalační ZIP.
2. Po úspěšných kontrolách vytvořit tag a draft s ověřeným instalátorem.
3. Po autorizaci zveřejnit kompletní draft jako prerelease a ověřit veřejné
   API i anonymní stažení. Zápis licence se na GitHubu musí rozpoznat jako GPL-3.0.
4. V osobním forku `79thales/default` založit novou větev z aktuálního
   `hacs/default:master`. Do souboru `integration` přidat jedinou položku
   `79thales/mnd-tariff-accounting` na abecedně správné místo.
5. Otevřít editovatelný PR do `hacs/default:master` s vyplněnou aktuální
   šablonou, odkazem na vydání a konkrétní úspěšné běhy HACS/Hassfest.
   Checkboxy označit až podle doložené skutečnosti; nevyžadovat review.

`hacs.json` obsahuje `country: CZ`, protože portál MND je určený pro Českou
republiku. Přijetí do katalogu závisí na HACS; release candidate ani odeslání
PR nejsou potvrzením přijetí nebo úplnosti všech historických živých testů.

Build potvrzuje obsah proti commitu, nikoli skutečné přihlášení, shodu
zákaznického vyúčtování nebo vzhled v provozním HA. Počet stažení není počet
instalací a integrace nemá telemetrii instalací.
