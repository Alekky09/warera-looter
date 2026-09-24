import requests
import os


API_BASE = "https://api2.warera.io/trpc"

API_TOKEN = os.environ.get("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API key missing from environment variables.")

HEADERS = {
    "X-API-Key": API_TOKEN,
    "accept": "*/*",
    "Content-Type": "application/json",
}
SIDE = "merged"
WEAPONS = {
    "jet": 6,
    "tank": 5,
    "sniper": 4,
    "rifle": 3,
    "gun": 2,
}
THRESHOLDS = {
    2: 'green',
    3: 'blue',
    4: 'purple',
    5: 'gold',
    6: 'red',
}
countries = {}
regions = {}
battles = {}

from datetime import datetime

battle_reports = []

COLORS = {
    "red": "#dc2626",
    "gold": "#eab308",
    "purple": "#9333ea",
    "blue": "#2563eb",
    "green": "#16a34a",
}


def get_all_countries():
    global countries
    r = requests.post(
        f"{API_BASE}/country.getAllCountries",
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()
    countries_info = r.json()['result']['data']
    countries = {x['_id']: x['name'] for x in countries_info}


def get_all_regions():
    global regions
    r = requests.post(
        f"{API_BASE}/region.getRegionsObject",
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()
    regions_info = r.json()['result']['data']
    regions = {x: regions_info[x]['name'] for x in regions_info}


def get_all_battles():
    global battles
    r = requests.post(
        f"{API_BASE}/battle.getBattles",
        headers=HEADERS,
        json={
            "isActive": True,
            "limit": 100,
            "direction": "forward",
            "filter": "all",
        },
        timeout=30
    )
    r.raise_for_status()
    battles_info = r.json()['result']['data']['items']
    for battle in battles_info:
        region = regions[battle['defender']['region']]
        defender_country = countries[battle['defender']['country']]
        attacker_country = countries[battle['attacker']['country']]
        current_round_id = battle['currentRound']['_id']
        get_loot_threshold(round_id=current_round_id, region=region, defender_country=defender_country, attacker_country=attacker_country)



def get_loot_threshold_1(round_id: str, region: str, defender_country: str, attacker_country: str):
    payload = {"roundId": round_id, "dataType": "damage", "type": "user", "side": SIDE, "limit": 100}
    loot_item, threshold_damage = None, None
    thresholds = {}
    while True:
        r = requests.post(
            f"{API_BASE}/battleRanking.getRanking",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        res = r.json()['result']['data']
        total_participants = res['itemCount']
        warriors = res['items']
        last_rank = None
        if not warriors:
            break
        for warrior in warriors:
            if not warrior.get('lootItem'):
                break
            threshold_damage = warrior['value']
            last_rank = warrior['rank']
            threshold = WEAPONS[warrior['lootItem']['code']] if warrior['lootItem']['code'] in WEAPONS else int(warrior['lootItem']['code'][-1:])
            thresholds[threshold] = threshold_damage
        if threshold_damage != warriors[-1]['value'] or not res.get('nextCursor'):
            break
        else:
            payload['cursor'] = res['nextCursor']
    print("\n" + "=" * 46)
    print("           LOOT THRESHOLD")
    print("=" * 46)
    print(f"Region    : {region}")
    print(f"------- {attacker_country} VS {defender_country} -------")
    print(f"Side             : {SIDE.capitalize()}")
    print("-" * 46)
    print(f"Participants     : {total_participants:,}")
    print("-" * 46)
    print(f"Threshold Damage : {threshold_damage:,} at rank {last_rank}")
    print(f"Need At Least    : {threshold_damage + 1:,}")
    print(f"All thresholds   :")
    for threshold, dmg in reversed(list(thresholds.items())):
        print(' ' * 4, f"{THRESHOLDS[threshold]} : {dmg:,}")
    print("=" * 46 + "\n")



def get_loot_threshold(round_id, region, defender_country, attacker_country):
    payload = {
        "roundId": round_id,
        "dataType": "damage",
        "type": "user",
        "side": SIDE,
        "limit": 100,
    }

    thresholds = {}
    threshold_damage = 0
    participants = 0
    last_rank = 0

    while True:
        r = requests.post(
            f"{API_BASE}/battleRanking.getRanking",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )

        res = r.json()["result"]["data"]
        participants = res["itemCount"]
        warriors = res["items"]

        if not warriors:
            break

        for w in warriors:
            if not w.get("lootItem"):
                break

            threshold_damage = w["value"]
            last_rank = w["rank"]

            code = w["lootItem"]["code"]
            tier = WEAPONS.get(code) if code in WEAPONS else int(code[-1:])
            thresholds[THRESHOLDS[tier]] = threshold_damage

        if threshold_damage != warriors[-1]["value"] or not res.get("nextCursor"):
            break

        payload["cursor"] = res["nextCursor"]

    battle_reports.append({
        "region": region,
        "attacker": attacker_country,
        "defender": defender_country,
        "participants": participants,
        "rank": last_rank,
        "need": threshold_damage + 1,
        "thresholds": thresholds,
    })


def generate_html():
    from datetime import datetime

    # Order battles by lowest GREEN threshold first
    battle_reports.sort(
        key=lambda b: b["thresholds"].get("green", float("inf"))
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>WarEra Battle Report</title>
<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 24px;
    background: #0f172a;
    color: #f8fafc;
    font-family: Arial, Helvetica, sans-serif;
}}

h1 {{
    margin: 0;
    font-size: 32px;
}}

.subtitle {{
    color: #94a3b8;
    margin: 6px 0 22px;
}}

.battle-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
}}

.card {{
    background: #111827;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 14px;
}}

.card h3 {{
    margin: 0;
    font-size: 17px;
}}

.region {{
    color: #94a3b8;
    font-size: 12px;
    margin: 4px 0 12px;
}}

.info {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}}

.metric {{
    background: #1f2937;
    border-radius: 8px;
    padding: 8px;
    text-align: center;
}}

.metric small {{
    display: block;
    color: #9ca3af;
    font-size: 10px;
    margin-bottom: 4px;
}}

.metric b {{
    font-size: 16px;
}}

.bar {{
    height: 18px;
    background: #1f2937;
    border-radius: 9px;
    overflow: hidden;
    margin: 6px 0;
}}

.fill {{
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 8px;
    font-size: 10px;
    font-weight: bold;
    color: white;
}}

.red {{ background: #dc2626; }}
.gold {{ background: #eab308; color: #111827; }}
.purple {{ background: #9333ea; }}
.blue {{ background: #2563eb; }}
.green {{ background: #16a34a; }}

.footer {{
    margin-top: 20px;
    text-align: center;
    color: #64748b;
    font-size: 12px;
}}
</style>
</head>
<body>

<h1>⚔ WarEra Battle Report</h1>
<div class="subtitle">
Generated {datetime.now():%Y-%m-%d %H:%M} • Ordered by lowest GREEN threshold
</div>

<div class="battle-grid">
"""

    for battle in battle_reports:
        html += f"""
<div class="card">
    <h3>{battle['attacker']} vs {battle['defender']}</h3>
    <div class="region">📍 {battle['region']} • {SIDE.capitalize()}</div>

    <div class="info">
        <div class="metric">
            <small>Players</small>
            <b>{battle['participants']:,}</b>
        </div>
        <div class="metric">
            <small>Rank</small>
            <b>{battle['rank']}</b>
        </div>
        <div class="metric">
            <small>Need</small>
            <b style="color:#4ade80;">{battle['need']:,}</b>
        </div>
    </div>
"""

        max_dmg = max(battle["thresholds"].values(), default=1)

        for color, dmg in sorted(
            battle["thresholds"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            width = (dmg / max_dmg) * 100
            html += f"""
    <div class="bar">
        <div class="fill {color}" style="width:{width:.1f}%">
            <span>{color.upper()}</span>
            <span>{dmg:,}</span>
        </div>
    </div>
"""

        html += "</div>"

    html += f"""
</div>

<div class="footer">
    {len(battle_reports)} active battles
</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Saved index.html")


get_all_countries()
get_all_regions()
get_all_battles()
battle_reports.sort(
    key=lambda b: b["thresholds"].get("green", float("inf"))
)
generate_html()