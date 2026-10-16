# Testování a vydání

Závazný zdroj pravidel: [GIT_POLITIKY_CEZ.md](../GIT_POLITIKY_CEZ.md).
Nový projekt má vlastní historii a větev `master_HA`; reference se nemění.

Před vydáním musí projít unit/Node/Ruff, skutečné Linux lifecycle testy,
HACS a Hassfest. Připravené workflow není úspěšná kontrola. Staged diff
a celý ZIP se prohlédnou kvůli soukromým údajům i nečekaným binárním souborům.
Verze manifestu, tagu a CS/EN changelogu musí souhlasit.

Resolver 16. 10. 2026 našel stable HA 2026.10.1, plugin 0.13.372 a Python 3.14.
Minimum bylo upraveno na 2026.3.1/plugin 0.13.317: plugin pro přesné 2026.3.0
nebyl nalezen. Metadata pro 2026.3.0 vyžadují Python >=3.14.2; sousední pluginy
cílí 2026.2.3 a potom 2026.3.1. Obě zvolené varianty již prošly 16 skutečnými
HA testy v Linuxu; Quality obsahuje také 100 doménových/protokolových testů
a 21 Node testů. Stejné kontroly jsou povinné i pro finální alpha revizi.

První balíček má verzi `0.1.0-alpha.1`, tag `v0.1.0-alpha.1` a zůstává
draftem s příznakem prerelease. Tento stav nepředstírá dokončené cloudové
mapování ani živé ověření MND. Zveřejnění draftu není automatická součást
build workflow; testovací ZIP lze předat místně bez instalace do HA.

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

Build potvrzuje obsah proti commitu, nikoli skutečné přihlášení, shodu
zákaznického vyúčtování nebo vzhled v provozním HA. Počet stažení není počet
instalací a integrace nemá telemetrii instalací.
