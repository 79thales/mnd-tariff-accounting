"""Udržuje stejné klíče překladů config flow, entit a akcí v CS/EN.

Spouští se jen při vývoji, ne v HA. Soubory jsou deterministické a neobsahují
zákaznické hodnoty. Změny názvů nemění unique_id ani archivované účetnictví.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components/mnd_tariff_accounting"
SENSORS = {
    "latest_mnd": ("Poslední odečet MND", "Last MND reading"),
    "latest_mnd_date": ("Datum odečtu MND", "MND reading date"),
    "current_meter": ("Odvozený stav plynoměru", "Derived meter reading"),
    "volume_m3": ("Spotřeba vyhodnoceného období", "Evaluated period consumption"),
    "energy_mwh": ("Energie vyhodnoceného období", "Evaluated period energy"),
    "known_cost_czk": ("Známé průběžné náklady", "Known running cost"),
    "paid_czk": ("Skutečně zaplaceno", "Actual payments"),
    "prescribed_czk": ("Předpis záloh", "Prescribed advances"),
    "assumed_paid_czk": ("Předpokládané úhrady", "Assumed payments"),
    "balance_czk": ("Průběžné saldo", "Running balance"),
    "surplus_czk": ("Průběžný přebytek", "Running surplus"),
    "deficit_czk": ("Průběžný deficit", "Running deficit"),
    "status": ("Kvalita účetnictví", "Accounting quality"),
    "cloud_status": ("Stav připojení MND", "MND connection status"),
    "current_deposit_czk": ("Předpis zálohy MND", "MND current advance"),
    "recommended_deposit_czk": ("Doporučená záloha MND", "MND recommended advance"),
    "mnd_assessment": ("Hodnocení záloh MND", "MND advance assessment"),
    "mnd_payment_status": ("Platební stav podle MND", "MND reported payment status"),
    "mnd_forecast_mwh": ("Celkový výhled MND", "MND expected period total"),
    "mnd_readings_mwh": ("Graf MND podle odečtů", "MND graph actual readings"),
    "mnd_past_estimate_mwh": ("Graf MND odhad minulosti", "MND graph estimated past"),
    "mnd_future_estimate_mwh": ("Graf MND odhad budoucnosti", "MND graph estimated future"),
    "invoice_result_czk": ("Potvrzený výsledek vyúčtování", "Confirmed invoice result"),
    "invoice_remaining_czk": ("Zbývá vypořádat vyúčtování", "Remaining invoice settlement"),
}


def build(language):
    cs = language == "cs"
    index = 0 if cs else 1
    return {
        "title": "MND Tariff & Accounting",
        "issues": {
            "cloud_unavailable": {
                "title": "Připojení MND vyžaduje pozornost"
                if cs
                else "MND connection needs attention",
                "description": "Důvod: {reason}. Poslední přijatá data zůstávají v archivu. Otevřete panel MND, zkontrolujte historii a případně obnovte přihlášení v nastavení integrace."
                if cs
                else "Reason: {reason}. Previously accepted data remain archived. Open the MND panel, check history and renew authentication in integration settings if needed.",
            }
        },
        "config": {
            "step": {
                "user": {
                    "title": "MND",
                    "menu_options": {
                        "import_profile": "Importní profil" if cs else "Import profile",
                        "cloud": "Připojit účet MND" if cs else "Connect MND account",
                    },
                },
                "import_profile": {
                    "title": "Importní profil" if cs else "Import profile",
                    "description": "Profil je místní identita. EIC zadávejte jako text; přístup k MND není vyžadován."
                    if cs
                    else "A local profile identity. Enter the EIC as text; MND access is not required.",
                    "data": {
                        "name": "Název" if cs else "Name",
                        "profile_id": "Jedinečný název profilu"
                        if cs
                        else "Unique profile identifier",
                        "supply_point": "EIC odběrného místa" if cs else "Supply point EIC",
                    },
                },
                "cloud": {
                    "title": "Přihlášení MND" if cs else "MND sign in",
                    "description": "Cloudový klient vychází z veřejného rozhraní portálu; živé ověření této verze ještě nebylo dokončeno. Bez uložení hesla je po restartu nutné nové přihlášení. Úložiště konfigurace HA není šifrovaný trezor."
                    if cs
                    else "The cloud client follows the public portal interface; live verification of this version is pending. Without password storage, sign in again after restart. HA configuration storage is not an encrypted vault.",
                    "data": {
                        "username": "Přihlašovací e-mail" if cs else "Login email",
                        "password": "Heslo" if cs else "Password",
                        "remember": "Uložit heslo do konfigurace HA"
                        if cs
                        else "Store password in HA configuration",
                    },
                },
                "places": {
                    "title": "Odběrná místa" if cs else "Supply points",
                    "data": {
                        "places": "Vybraná plynová místa" if cs else "Selected gas supply points"
                    },
                },
            },
            "error": {
                "invalid_supply_point": "Neplatný textový EIC." if cs else "Invalid text EIC.",
                "invalid_auth": "Přihlášení vyžaduje správné údaje nebo další ověření v portálu."
                if cs
                else "Correct credentials or additional portal verification required.",
                "cannot_connect": "Portál není dostupný nebo změnil datový kontrakt."
                if cs
                else "The portal is unavailable or its data contract changed.",
            },
            "abort": {
                "already_configured": "Tento účet/profil už existuje."
                if cs
                else "This account/profile is already configured.",
                "wrong_account": "Přihlášení patří jinému účtu."
                if cs
                else "The credentials belong to another account.",
                "reauth_successful": "Přihlášení obnoveno." if cs else "Authentication renewed.",
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": "Nastavení MND" if cs else "MND settings",
                    "description": "[Otevřít účetní panel a Generate dashboard]({panel_url}). Úpravy mění pouze místní evidenci v HA."
                    if cs
                    else "[Open accounting panel and Generate dashboard]({panel_url}). Changes affect local HA records only.",
                }
            }
        },
        "entity": {
            "sensor": {key: {"name": names[index]} for key, names in SENSORS.items()},
            "button": {
                "recompute": {"name": "Přepočítat účetnictví" if cs else "Recompute accounting"},
                "generate_dashboard": {"name": "Generate dashboard"},
            },
        },
    }


if __name__ == "__main__":
    (ROOT / "translations").mkdir(exist_ok=True)
    for lang in ("cs", "en"):
        text = json.dumps(build(lang), ensure_ascii=False, indent=2) + "\n"
        (ROOT / "translations" / f"{lang}.json").write_text(text, encoding="utf-8")
        if lang == "en":
            (ROOT / "strings.json").write_text(text, encoding="utf-8")
