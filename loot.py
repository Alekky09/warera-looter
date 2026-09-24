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
        defender_damages = battle['currentRound']['defender']['damages'] or 0
        defender_points = battle['currentRound']['defender']['points'] or 0
        attacker_country = countries[battle['attacker']['country']]
        attacker_damages = battle['currentRound']['attacker']['damages'] or 0
        attacker_points = battle['currentRound']['attacker']['points'] or 0
        current_round_id = battle['currentRound']['_id']
        get_loot_threshold(
            round_id=current_round_id,
            region=region,
            defender_country=defender_country,
            defender_damages=defender_damages,
            defender_points=defender_points,
            attacker_country=attacker_country,
            attacker_damages=attacker_damages,
            attacker_points=attacker_points,
        )


def get_loot_threshold(
    round_id: str,
    region: str,
    defender_country: str,
    defender_damages: int,
    defender_points: int,
    attacker_country: str,
    attacker_damages: int,
    attacker_points: int,
):
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
        "defender_damages": defender_damages,
        "defender_points": defender_points,
        "attacker_damages": attacker_damages,
        "attacker_points": attacker_points,
    })


def generate_html():
    from datetime import datetime
    from html import escape

    def compact_number(value):
        """
        Format large numbers:
        999        -> 999
        1,200      -> 1.2K
        25,000     -> 25K
        1,000,000  -> 1M
        2,400,000  -> 2.4M
        1,500,000,000 -> 1.5B
        """
        value = float(value)
        abs_value = abs(value)

        if abs_value >= 1_000_000_000:
            result = f"{value / 1_000_000_000:.1f}B"
        elif abs_value >= 1_000_000:
            result = f"{value / 1_000_000:.1f}M"
        elif abs_value >= 1_000:
            result = f"{value / 1_000:.1f}K"
        else:
            return f"{int(value):,}"

        return (
            result
            .replace(".0B", "B")
            .replace(".0M", "M")
            .replace(".0K", "K")
        )

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
    font-size: 18px;
    text-align: center;
    font-weight: 700;
}}

.region-meta {{
    color: #64748b;
    font-size: 11px;
    text-align: center;
    margin-top: 3px;
}}

.players {{
    color: #64748b;
    font-size: 11px;
    text-align: center;
    margin: 8px 0 10px;
}}

/* -----------------------------------------
   Country labels
   Defender = LEFT
   Attacker = RIGHT
   ----------------------------------------- */

.side-labels {{
    display: flex;
    width: 100%;
    margin-bottom: 5px;
    font-size: 11px;
    font-weight: bold;
}}

.side-label {{
    width: 50%;
    min-width: 0;
}}

.side-label.defender {{
    text-align: left;
    color: #60a5fa;
}}

.side-label.attacker {{
    text-align: right;
    color: #f87171;
}}

.side-label span {{
    color: #94a3b8;
    font-weight: normal;
    margin-left: 4px;
}}

/* -----------------------------------------
   Points progress bar
   Both sides grow toward the center.
   300 points = full half.
   ----------------------------------------- */

.points-bar {{
    position: relative;
    width: 100%;
    height: 10px;
    display: flex;
    overflow: hidden;
    border-radius: 5px;
    background: #1f2937;
    margin-bottom: 10px;
}}

.points-side {{
    position: relative;
    width: 50%;
    height: 100%;
    background: #1f2937;
}}

.points-fill {{
    position: absolute;
    top: 0;
    height: 100%;
}}

.points-fill.defender {{
    left: 0;
    background: #2563eb;
}}

.points-fill.attacker {{
    right: 0;
    background: #dc2626;
}}

.points-center {{
    position: absolute;
    left: 50%;
    top: 0;
    transform: translateX(-50%);
    width: 2px;
    height: 100%;
    background: #f8fafc;
    opacity: 0.8;
    z-index: 2;
}}

/* -----------------------------------------
   Damage comparison bar
   Defender = LEFT
   Attacker = RIGHT
   ----------------------------------------- */

.damage-bar {{
    width: 100%;
    height: 22px;
    display: flex;
    overflow: hidden;
    border-radius: 11px;
    background: #1f2937;
    margin-bottom: 10px;
}}

.damage-segment {{
    height: 100%;
    min-width: 0;
    display: flex;
    align-items: center;
    padding: 0 7px;
    font-size: 10px;
    font-weight: bold;
    color: white;
    white-space: nowrap;
    overflow: hidden;
}}

.damage-segment.defender {{
    justify-content: flex-start;
    background: #2563eb;
}}

.damage-segment.attacker {{
    justify-content: flex-end;
    background: #dc2626;
}}

.damage-segment span {{
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* -----------------------------------------
   Threshold bars
   Smaller and only show the number.
   ----------------------------------------- */

.bar {{
    height: 14px;
    background: #1f2937;
    border-radius: 7px;
    overflow: hidden;
    margin: 4px 0;
}}

.fill {{
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 6px;
    font-size: 9px;
    font-weight: bold;
    color: white;
}}

.red {{
    background: #dc2626;
}}

.gold {{
    background: #eab308;
    color: #111827;
}}

.purple {{
    background: #9333ea;
}}

.blue {{
    background: #2563eb;
}}

.green {{
    background: #16a34a;
}}

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

        attacker = escape(str(battle["attacker"]))
        defender = escape(str(battle["defender"]))
        region = escape(str(battle["region"]))

        defender_damage = battle.get("defender_damages", 0) or 0
        attacker_damage = battle.get("attacker_damages", 0) or 0

        defender_points = battle.get("defender_points", 0) or 0
        attacker_points = battle.get("attacker_points", 0) or 0

        # -----------------------------------------
        # Damage percentages
        # -----------------------------------------

        total_damage = defender_damage + attacker_damage

        if total_damage > 0:
            defender_damage_pct = (
                defender_damage / total_damage
            ) * 100

            attacker_damage_pct = (
                attacker_damage / total_damage
            ) * 100
        else:
            defender_damage_pct = 50
            attacker_damage_pct = 50

        # -----------------------------------------
        # Points progress toward 300
        # -----------------------------------------

        points_goal = 300

        defender_points_pct = min(
            max((defender_points / points_goal) * 100, 0),
            100
        )

        attacker_points_pct = min(
            max((attacker_points / points_goal) * 100, 0),
            100
        )

        # -----------------------------------------
        # Compact damage values
        # -----------------------------------------

        defender_damage_display = compact_number(defender_damage)
        attacker_damage_display = compact_number(attacker_damage)
        total_damage_display = compact_number(total_damage)

        # -----------------------------------------
        # Card
        # -----------------------------------------

        html += f"""
<div class="card">

    <!-- Region headline -->
    <h3>{region}</h3>

    <div class="region-meta">
        {SIDE.capitalize()}
    </div>

    <!-- Player count -->
    <div class="players">
        {battle['participants']:,} players
    </div>

    <!-- Countries -->
    <div class="side-labels">

        <div class="side-label defender">
            {defender}
            <span>{defender_points:,}/{points_goal}</span>
        </div>

        <div class="side-label attacker">
            {attacker}
            <span>{attacker_points:,}/{points_goal}</span>
        </div>

    </div>

    <!-- Points progress bar -->
    <div class="points-bar">

        <!-- Defender: LEFT -> CENTER -->
        <div class="points-side">
            <div
                class="points-fill defender"
                style="width:{defender_points_pct:.1f}%"
                title="{defender}: {defender_points:,} / {points_goal}"
            ></div>
        </div>

        <!-- Attacker: RIGHT -> CENTER -->
        <div class="points-side">
            <div
                class="points-fill attacker"
                style="width:{attacker_points_pct:.1f}%"
                title="{attacker}: {attacker_points:,} / {points_goal}"
            ></div>
        </div>

        <!-- Center / win line -->
        <div class="points-center"></div>

    </div>

    <!-- Damage comparison -->
    <div
        class="damage-bar"
        title="Total damage: {total_damage_display}"
    >

        <!-- Defender: always LEFT -->
        <div
            class="damage-segment defender"
            style="width:{defender_damage_pct:.1f}%"
            title="{defender}: {defender_damage_display}"
        >
            <span>{defender_damage_display}</span>
        </div>

        <!-- Attacker: always RIGHT -->
        <div
            class="damage-segment attacker"
            style="width:{attacker_damage_pct:.1f}%"
            title="{attacker}: {attacker_damage_display}"
        >
            <span>{attacker_damage_display}</span>
        </div>

    </div>
"""

        # -----------------------------------------
        # Threshold bars
        # -----------------------------------------

        max_dmg = max(
            battle["thresholds"].values(),
            default=1
        )

        for color, dmg in sorted(
            battle["thresholds"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            width = (dmg / max_dmg) * 100

            html += f"""
    <div class="bar">
        <div
            class="fill {color}"
            style="width:{width:.1f}%"
        >
            <span>{compact_number(dmg)}</span>
        </div>
    </div>
"""

        html += """
</div>
"""

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