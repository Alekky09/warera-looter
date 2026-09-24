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
        999            -> 999
        1,200          -> 1.2K
        25,000         -> 25K
        1,000,000      -> 1M
        2,400,000      -> 2.4M
        1,500,000,000  -> 1.5B
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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WarEra Battle Report</title>

<style>
:root {{
    --bg: #0b1120;
    --card: #111827;
    --border: rgba(148, 163, 184, 0.14);
    --muted: #64748b;
    --text: #f8fafc;

    --defender: #3b82f6;
    --defender-light: #60a5fa;

    --attacker: #ef4444;
    --attacker-light: #f87171;

    --track: #1e293b;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 32px;
    min-height: 100vh;
    background:
        radial-gradient(
            circle at top left,
            rgba(59, 130, 246, 0.08),
            transparent 28%
        ),
        radial-gradient(
            circle at top right,
            rgba(239, 68, 68, 0.06),
            transparent 25%
        ),
        var(--bg);
    color: var(--text);
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}}

h1 {{
    margin: 0;
    font-size: 30px;
    font-weight: 750;
    letter-spacing: -0.5px;
}}

.subtitle {{
    color: var(--muted);
    margin: 6px 0 26px;
    font-size: 12px;
}}

.battle-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
    align-items: start;
}}

.card {{
    position: relative;
    overflow: hidden;
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: 16px;
    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.025),
            rgba(255,255,255,0)
        ),
        var(--card);
    box-shadow:
        0 10px 30px rgba(0, 0, 0, 0.20),
        inset 0 1px 0 rgba(255,255,255,0.02);
    transition:
        transform 0.18s ease,
        border-color 0.18s ease,
        box-shadow 0.18s ease;
}}

.card:hover {{
    transform: translateY(-2px);
    border-color: rgba(148, 163, 184, 0.25);
    box-shadow:
        0 16px 36px rgba(0, 0, 0, 0.28),
        inset 0 1px 0 rgba(255,255,255,0.03);
}}

/* ---------------------------------------------------------
   Region
   --------------------------------------------------------- */

.card h3 {{
    margin: 0;
    text-align: center;
    font-size: 18px;
    font-weight: 750;
    letter-spacing: -0.2px;
}}

.region-meta {{
    margin-top: 3px;
    text-align: center;
    color: #475569;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}}

.players {{
    margin: 9px 0 16px;
    text-align: center;
    color: #64748b;
    font-size: 11px;
}}

/* ---------------------------------------------------------
   Country headings
   --------------------------------------------------------- */

.side-labels {{
    display: flex;
    width: 100%;
    margin-bottom: 6px;
}}

.side-label {{
    width: 50%;
    min-width: 0;
    font-size: 12px;
    font-weight: 700;
}}

.side-label.defender {{
    text-align: left;
    color: var(--defender-light);
}}

.side-label.attacker {{
    text-align: right;
    color: var(--attacker-light);
}}

.points-count {{
    display: inline-block;
    margin-left: 4px;
    color: #94a3b8;
    font-size: 10px;
    font-weight: 500;
}}

/* ---------------------------------------------------------
   Points progress bar
   Both sides grow toward the center.
   300 points = full half.
   --------------------------------------------------------- */

.points-bar {{
    position: relative;
    display: flex;
    width: 100%;
    height: 9px;
    overflow: hidden;
    border-radius: 999px;
    background: #1e293b;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
}}

.points-side {{
    position: relative;
    width: 50%;
    height: 100%;
    background: rgba(30, 41, 59, 0.75);
}}

.points-fill {{
    position: absolute;
    top: 0;
    height: 100%;
    border-radius: 999px;
}}

.points-fill.defender {{
    left: 0;
    background: linear-gradient(
        90deg,
        #2563eb,
        #60a5fa
    );
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.25);
}}

.points-fill.attacker {{
    right: 0;
    background: linear-gradient(
        270deg,
        #dc2626,
        #f87171
    );
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.22);
}}

.points-center {{
    position: absolute;
    top: -2px;
    left: 50%;
    z-index: 3;
    width: 2px;
    height: calc(100% + 4px);
    transform: translateX(-50%);
    border-radius: 999px;
    background: rgba(248, 250, 252, 0.9);
    box-shadow: 0 0 6px rgba(255,255,255,0.35);
}}

/* ---------------------------------------------------------
   DAMAGE BAR
   Defender = LEFT
   Attacker = RIGHT
   Numbers stay inside the colored sections.
   --------------------------------------------------------- */

.damage-wrapper {{
    margin-top: 11px;
}}

.damage-bar {{
    display: flex;
    width: 100%;
    height: 24px;
    overflow: hidden;
    border-radius: 999px;
    background: var(--track);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
}}

.damage-segment {{
    min-width: 0;
    height: 100%;
    display: flex;
    align-items: center;
    padding: 0 8px;
    font-size: 10px;
    font-weight: 700;
    color: white;
    white-space: nowrap;
    overflow: hidden;
}}

.damage-segment.defender {{
    justify-content: flex-start;
    background: linear-gradient(
        90deg,
        #2563eb,
        #3b82f6
    );
}}

.damage-segment.attacker {{
    justify-content: flex-end;
    background: linear-gradient(
        270deg,
        #dc2626,
        #ef4444
    );
}}

.damage-segment span {{
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* ---------------------------------------------------------
   Threshold bars
   Smaller, with only the number.
   --------------------------------------------------------- */

.thresholds {{
    margin-top: 13px;
    padding-top: 12px;
    border-top: 1px solid rgba(148, 163, 184, 0.08);
}}

.threshold-row {{
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    height: 13px;
    margin: 5px 0;
}}

.threshold-track {{
    position: absolute;
    inset: 0;
    overflow: hidden;
    border-radius: 999px;
    background: #1a2434;
}}

.threshold-fill {{
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    border-radius: 999px;
}}

.threshold-number {{
    position: absolute;
    top: 50%;
    z-index: 3;
    transform: translateY(-50%);
    font-size: 8px;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
    pointer-events: none;
}}

/*
 * Normal case:
 * number sits in the unused dark area immediately
 * after the colored fill.
 */
.threshold-number.outside {{
    color: #94a3b8;
    left: var(--fill-end);
    margin-left: 5px;
}}

/*
 * When the fill is large enough, put the number
 * inside the colored area on the right.
 */
.threshold-number.inside {{
    right: 6px;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}}

/* Threshold colors */

.red {{
    background: linear-gradient(
        90deg,
        #b91c1c,
        #ef4444
    );
}}

.gold {{
    background: linear-gradient(
        90deg,
        #ca8a04,
        #eab308
    );
}}

.purple {{
    background: linear-gradient(
        90deg,
        #7e22ce,
        #a855f7
    );
}}

.blue {{
    background: linear-gradient(
        90deg,
        #1d4ed8,
        #3b82f6
    );
}}

.green {{
    background: linear-gradient(
        90deg,
        #15803d,
        #22c55e
    );
}}

.footer {{
    margin-top: 24px;
    text-align: center;
    color: #475569;
    font-size: 11px;
}}
</style>
</head>

<body>

<h1>⚔ WarEra Battle Report</h1>

<div class="subtitle">
    Generated {datetime.now():%Y-%m-%d %H:%M}
    • Ordered by lowest GREEN threshold
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

        # -----------------------------------------------------
        # Damage percentages
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Points progress toward 300
        # -----------------------------------------------------

        points_goal = 300

        defender_points_pct = min(
            max((defender_points / points_goal) * 100, 0),
            100
        )

        attacker_points_pct = min(
            max((attacker_points / points_goal) * 100, 0),
            100
        )

        # -----------------------------------------------------
        # Compact damage values
        # -----------------------------------------------------

        defender_damage_display = compact_number(defender_damage)
        attacker_damage_display = compact_number(attacker_damage)

        # -----------------------------------------------------
        # Card
        # -----------------------------------------------------

        html += f"""
<div class="card">

    <h3>{region}</h3>

    <div class="region-meta">
        {SIDE.capitalize()}
    </div>

    <div class="players">
        {battle['participants']:,} players
    </div>

    <!-- Country labels -->
    <div class="side-labels">

        <div class="side-label defender">
            {defender}
            <span class="points-count">
                {defender_points:,}/{points_goal}
            </span>
        </div>

        <div class="side-label attacker">
            <span class="points-count">
                {attacker_points:,}/{points_goal}
            </span>
            {attacker}
        </div>

    </div>

    <!-- Points progress -->
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

        <div class="points-center"></div>

    </div>

    <!-- Damage -->
    <div class="damage-wrapper">

        <div
            class="damage-bar"
            title="{defender}: {defender_damage_display} • {attacker}: {attacker_damage_display}"
        >

            <!-- Defender = LEFT -->
            <div
                class="damage-segment defender"
                style="width:{defender_damage_pct:.1f}%"
                title="{defender}: {defender_damage_display}"
            >
                <span>{defender_damage_display}</span>
            </div>

            <!-- Attacker = RIGHT -->
            <div
                class="damage-segment attacker"
                style="width:{attacker_damage_pct:.1f}%"
                title="{attacker}: {attacker_damage_display}"
            >
                <span>{attacker_damage_display}</span>
            </div>

        </div>

    </div>

    <!-- Threshold bars -->
    <div class="thresholds">
"""

        # -----------------------------------------------------
        # Threshold bars
        # -----------------------------------------------------

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

            # If the fill is small, put the number in the
            # unused space. Otherwise put it inside the fill.
            #
            # 18% is a conservative threshold that leaves
            # enough room for numbers such as "2.4M".
            label_inside = width >= 18

            label_class = (
                "threshold-number inside"
                if label_inside
                else "threshold-number outside"
            )

            html += f"""
        <div class="threshold-row">

            <div class="threshold-track">
                <div
                    class="threshold-fill {color}"
                    style="width:{width:.1f}%"
                ></div>
            </div>

            <span
                class="{label_class}"
                style="--fill-end:{width:.1f}%"
            >
                {compact_number(dmg)}
            </span>

        </div>
"""

        html += """
    </div>

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