"""SIMULATED example measurements for a throw-away demo database. Every row has provenance DEMO_DATA.

It refuses any database whose name does not start with "smartlab_demo". Standard library + SQLAlchemy.
  python load_simulated_metrics.py            14 days of example data
  python load_simulated_metrics.py --bulk     about 300,000 extra rows for timing
  python load_simulated_metrics.py --json F   only write the example as JSON, no database
"""
import json, math, os, random, sys
from datetime import datetime, timedelta, timezone

rnd = random.Random(20261123)
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def series(days=14):
    """(metric, value, time): one value per 10 minutes, with a six-hour gap nine days ago and one impossible value."""
    t = NOW - timedelta(days=days)
    while t <= NOW:
        age = (NOW - t).total_seconds() / 86400
        if not 9 < age < 9.25:
            day = math.sin((t.hour - 9) / 24 * 2 * math.pi)
            busy = max(0, math.sin((t.hour - 7) / 12 * math.pi)) if 7 < t.hour < 19 else 0
            yield from (("temperature", round(23.5 + 2.2 * day + rnd.gauss(0, .15), 2), t), ("humidity", round(46 - 6 * day + rnd.gauss(0, .5), 1), t),
                        ("co2_ppm", round(430 + 420 * busy + rnd.gauss(0, 12)), t), ("illuminance_lux", round(5 + 430 * busy), t),
                        ("wifi_rssi_dbm", round(-61 + rnd.gauss(0, 2)), t), ("free_heap_b", 270000 + rnd.randint(-900, 900), t),
                        ("smoke", 0, t), ("flame", 0, t), ("motion", int(rnd.random() < .7 * busy), t))
        t += timedelta(minutes=10)
    yield ("temperature", 999, NOW - timedelta(days=3))


if "--json" in sys.argv:
    out = sys.argv[sys.argv.index("--json") + 1]
    rows = [{"device_uid": "DEMO_ENV_SIM", "metric": m, "value": v, "recorded_at": t.isoformat(), "provenance": "DEMO_DATA"} for m, v, t in series(2)]
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"label": "SIMULATED - not measurements", "rows": rows}, f, indent=0)
    sys.exit(print(len(rows), "simulated rows written"))

from sqlalchemy import create_engine, text

e = create_engine(os.environ["DATABASE_URL"])
if not (e.url.database or "").startswith("smartlab_demo"):
    sys.exit("REFUSED: only a database named smartlab_demo* may receive simulated data")
with e.begin() as c:
    lab = c.execute(text("select id from labs order by id limit 1")).scalar()
    c.execute(text("insert into devices (device_uid, name, device_type, lab_id, is_online, last_seen_at, is_master_pc) "
                   "values ('DEMO_ENV_SIM', 'Simulated environment node', 'SENSOR_NODE', :l, true, now(), false) on conflict do nothing"), {"l": lab})
    ids = {r.device_uid: r.id for r in c.execute(text("select id, device_uid from devices"))}
    targets = [ids["DEMO_ENV_SIM"]] + [ids[u] for u in ("ENV_LAB01",) if u in ids]
    q = text("insert into sensor_readings (lab_id, device_id, metric, value, unit, recorded_at, provenance) values (:l,:d,:m,:v,'',:t,'DEMO_DATA')")
    rows = [{"l": lab, "d": d, "m": m, "v": v, "t": t} for d in targets for m, v, t in series() if d == ids["DEMO_ENV_SIM"] or m in ("temperature", "humidity", "smoke", "flame", "motion")]
    c.execute(q, rows)
    print(len(rows), "simulated rows")
    if "--bulk" in sys.argv:
        for i in range(1, 11):
            c.execute(text("insert into devices (device_uid, name, device_type, lab_id, is_online, is_master_pc) values (:u, :u, 'PC', :l, false, false) on conflict do nothing"), {"u": f"DEMO_BULK_{i}_SIM", "l": lab})
        c.execute(text("insert into sensor_readings (lab_id, device_id, metric, value, unit, recorded_at, provenance) "
                       "select :l, d.id, m.m, 50, '', now() - (g.g * interval '2 minutes'), 'DEMO_DATA' from devices d, "
                       "(values ('pc_cpu_pct'),('pc_ram_pct'),('pc_disk_pct'),('pc_net_rx_kbps'),('pc_net_tx_kbps')) m(m), "
                       "generate_series(1, 6000) g(g) where d.device_uid like 'DEMO_BULK%'"), {"l": lab})
        print("bulk", c.execute(text("select count(*) from sensor_readings")).scalar(), "rows in total")
