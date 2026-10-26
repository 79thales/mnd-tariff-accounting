"""Vytvoří pouze místní náhled skutečné komponenty se syntetickými údaji.

Nevyžaduje běžící HA, nečte konfiguraci ani zákaznické podklady, žádný server
nespouští. Rozhraní WS je pro náhled výslovně pouze čtecí. Účetní hodnoty
vycházejí ze stejné projekce a dashboard ze stejného generátoru jako runtime.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.mnd_tariff_accounting.core.archive import new_place  # noqa: E402
from custom_components.mnd_tariff_accounting.core.boiler import consumption_summary  # noqa: E402
from custom_components.mnd_tariff_accounting.core.projection import evaluate_place  # noqa: E402
from custom_components.mnd_tariff_accounting.dashboard import build_views  # noqa: E402

PLACE = "27ZG000Z0000000X"


def main():
    """Zapíše tři veřejné demo soubory do ignorovaného output/preview."""
    output = ROOT / "output/preview"
    output.mkdir(parents=True, exist_ok=True)
    place = new_place("Syntetická domácnost")
    place["settings"] = {
        "name": "Syntetická domácnost",
        "period_from": "2026-01-01",
        "period_to": "2027-01-01",
        "opening_credit": "100",
        "payments_complete": True,
        "source_mode": "manual",
        "segment": "DEMO-01",
    }
    place["readings"] = [
        {
            "id": key,
            "place": PLACE,
            "meter": "DEMO-01",
            "segment": "DEMO-01",
            "date": date,
            "value": value,
            "source": "mnd",
            "method": "Samoodečtem",
            "status": "Syntetický doklad",
        }
        for key, date, value in [
            ("demo-start", "2026-01-01", "1000"),
            ("demo-end", "2026-10-01", "1080"),
        ]
    ]
    place["tariffs"] = [
        {
            "id": "demo-price",
            "from": "2026-01-01",
            "to": "2027-01-01",
            "name": "Syntetický tarif",
            "commodity": "1250",
            "other": "0",
            "fixed": "0",
            "includes_vat": True,
            "all_components_known": True,
            "prorate_fixed": True,
        }
    ]
    place["conversions"] = [
        {
            "id": "demo-factor",
            "from": "2026-01-01",
            "to": "2027-01-01",
            "kwh_per_m3": "10",
            "evidence": "Syntetický test",
        }
    ]
    place["events"] = [
        {
            "id": "demo-payment",
            "role": "payment",
            "amount": "1200",
            "date": "2026-01-05",
            "from": "2026-01-01",
            "to": "2027-01-01",
            "verification": "synthetic",
        }
    ]
    place["snapshots"] = [
        {
            "retrieved_at": "2026-10-16T08:00:00Z",
            "periods": [
                {
                    "From": "2026-01-01",
                    "To": "2027-01-01",
                    "ReadingsMwh": "0.8",
                    "PastEstimateMwh": "0.3",
                    "FutureEstimateMwh": "1.2",
                    "PortalTotalMwh": "2.3",
                }
            ],
        }
    ]
    place["portal_evidence"] = {"deposit": {"ADV_VALUE": "250", "ADV_BALANCE": "200"}}
    result = evaluate_place(
        PLACE, place, "Europe/Prague", datetime(2026, 10, 16, tzinfo=timezone.utc)
    )
    # Provozní demo je výhradně syntetické a používá skutečné vykreslovací
    # cesty. Žádná domácí entita ani přístup se do náhledu nekopíruje.
    now = datetime.now(timezone.utc)
    place["settings"].update(
        {
            "history_registry_id": "demo-history",
            "flow_entity": "sensor.synthetic_flow",
            "boiler_enabled": True,
            "boiler_power_entity": "sensor.synthetic_boiler_power",
            "boiler_energy_entity": "sensor.synthetic_boiler_energy",
            "boiler_demand_entity": "binary_sensor.synthetic_boiler_demand",
        }
    )
    place["daily_profile"] = [
        {
            "date": (now.date() - timedelta(days=6 - i)).isoformat(),
            "entity": "demo-history",
            "segment": "DEMO-01",
            "m3": str(value) if i < 6 else None,
            "known_m3": str(value),
            "complete": i < 6,
            "observed_to": now.isoformat() if i == 6 else None,
        }
        for i, value in enumerate([1.4, 1.9, 2.1, 1.6, 2.4, 1.8, 0.3])
    ]
    result["consumption"] = consumption_summary(place, now, "Europe/Prague")
    result["boiler"] = {
        "electricity": {
            "today": {
                "value_kwh": "0.21",
                "known_hours": 3,
                "expected_closed_hours": 3,
                "observed_to": now.timestamp(),
            },
            "month": {
                "value_kwh": "4.6",
                "known_hours": 52,
                "expected_closed_hours": 60,
                "observed_to": now.timestamp(),
            },
        }
    }
    keys = [
        "current_flow_m3h",
        "current_deposit_czk",
        "latest_mnd",
        "latest_mnd_date",
        "current_meter",
        "status",
        "volume_m3",
        "known_cost_czk",
        "paid_czk",
        "balance_czk",
    ]
    views = build_views(
        "MND · syntetický náhled",
        "mnd-demo",
        {key: "sensor.synthetic_" + key for key in keys},
        "demo-entry",
        PLACE,
    )
    content = {
        "detail": {"place": place, "result": result, "revision": 1, "settlements": []},
        "views": views,
        "place": PLACE,
    }
    (output / "demo.json").write_text(
        json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    shutil.copyfile(
        ROOT / "custom_components/mnd_tariff_accounting/frontend/mnd-panel.js",
        output / "mnd-panel.js",
    )
    (output / "index.html").write_text(
        """<!doctype html>
<html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MND – vývojový náhled</title>
<style>body{margin:0;background:#f6f8f6;font:15px Arial}.demo{padding:14px 28px;background:#fff4c7;color:#403816;display:flex;gap:16px;align-items:center;flex-wrap:wrap}.demo button,.demo select{font:inherit;padding:8px}.demo strong{flex:1}</style>
<div class="demo"><strong>VÝVOJOVÝ NÁHLED · pouze syntetická data · nejde o běžící Home Assistant</strong><button id="theme">Světlé / tmavé</button><select id="language"><option value="cs">Čeština</option><option value="en">English</option></select><select id="view"><option value="overview">Přehled</option><option value="readings">Spotřeba</option><option value="accounting">Účetnictví</option><option value="editor">Administrace</option></select><label><input id="boiler" type="checkbox" checked>Kotel</label></div>
<mnd-accounting-card></mnd-accounting-card>
<script type="module">
import './mnd-panel.js';
const demo=await (await fetch('./demo.json')).json();
let panel=document.querySelector('mnd-accounting-card');
const stamp=new Date().toISOString();
const state=(entity_id,value,unit,extra={})=>({entity_id,state:value,last_updated:stamp,attributes:{unit_of_measurement:unit,...extra}});
const hass={config:{time_zone:'Europe/Prague'},language:'cs',themes:{darkMode:false},states:{
 'sensor.synthetic_flow':state('sensor.synthetic_flow','1.291','m³/h'),
 'sensor.synthetic_boiler_power':state('sensor.synthetic_boiler_power','94','W'),
 'sensor.synthetic_boiler_energy':state('sensor.synthetic_boiler_energy','20','Wh',{state_class:'total_increasing'}),
 'binary_sensor.synthetic_boiler_demand':state('binary_sensor.synthetic_boiler_demand','on','')
},callWS:async msg=>{
 switch(msg.action){
 case 'entries':return [{id:'demo-entry',name:'Syntetický účet'}];
 case 'summary':return {places:[{id:demo.place,name:'Syntetická domácnost'}],job:{status:'idle'}};
 case 'detail':return structuredClone(demo.detail);
 case 'dashboard':return structuredClone(demo.views);
 default:throw new Error('Náhled je pouze pro čtení. / Read-only preview.');
 }
}};
panel.setConfig(demo.views.config.views[0].cards[0]);panel.hass=hass;
document.getElementById('theme').onclick=()=>{hass.themes={darkMode:!hass.themes.darkMode};panel.hass=hass;panel.render();};
document.getElementById('language').onchange=event=>{hass.language=event.target.value;panel.hass=hass;panel.render();};
function show(tab){
 const previous=panel;panel=document.createElement(tab==='editor'?'mnd-accounting-panel':'mnd-accounting-card');
 if(tab!=='editor')panel.setConfig({...demo.views.config.views[0].cards[0],tab});
 panel.hass=hass;previous.replaceWith(panel);
}
document.getElementById('view').onchange=event=>show(event.target.value);
document.getElementById('boiler').onchange=event=>{demo.detail.place.settings.boiler_enabled=event.target.checked;show(document.getElementById('view').value);};
document.addEventListener('click',event=>{const link=event.composedPath().find(n=>n.tagName==='A'&&n.getAttribute('href')?.startsWith('/lovelace/'));if(!link)return;const tab=demo.views.config.views[0].cards[0].navigation.find(n=>n.path===link.getAttribute('href'))?.tab;if(tab){event.preventDefault();show(tab);}});
</script></html>""",
        encoding="utf-8",
        newline="\n",
    )
    # Samostatné HTML lze otevřít i bez serveru; fetch ani přístupy nejsou potřeba.
    html = output / "index.html"
    text = html.read_text(encoding="utf-8")
    text = text.replace(
        "import './mnd-panel.js';", (output / "mnd-panel.js").read_text(encoding="utf-8")
    )
    text = text.replace(
        "const demo=await (await fetch('./demo.json')).json();",
        "const demo=" + json.dumps(content, ensure_ascii=False).replace("<", "\\u003c") + ";",
    )
    html.write_text(text, encoding="utf-8", newline="\n")
    print(output / "index.html")


if __name__ == "__main__":
    main()
