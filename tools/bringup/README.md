# Bring-up tools (physical validation, thesis Chapter 4)

Results go in [docs/BRINGUP_LOG.md](../../docs/BRINGUP_LOG.md) - only measured values.

## Capture a node's output

```
py -m pip install pyserial          (once)
py serial_log.py --list             find the COM port of the ESP32
py serial_log.py COM5 --tag dht-baseline
```

- Close the Arduino Serial Monitor first (one program per COM port).
- Type node commands into the logger (`tare`, `cal 100`, `avg 50`, `stream`, `show`).
- Type `# ...` for a note that is saved but not sent, e.g. `# ref 100.0`
  (the reference scale's reading of the mass you just placed).
- Files: `logs/<date>_<time>_<tag>.log` (everything) and `.csv` (node `CSV,` lines,
  prefixed `host_iso,host_ms`). Keep the raw logs: they are the evidence behind
  every number in the thesis.

## What the nodes print (`CSV,` lines)

| Line | Node | Fields after `CSV,<kind>,` | Used for |
|---|---|---|---|
| `dht` | environment | node_ms, temperature_c, humidity_rh | readings, repeatability, update rate |
| `dht_fail` | environment | node_ms | read failures |
| `state` | environment | node_ms, metric, 0/1 (`gas_level`: 1 normal, 2 warning, 3 critical) | flame_1..5 / pir_1, pir_2 / gas changes, response time |
| `mq` | environment | node_ms, raw, pin_mv, filtered_mv, baseline_mv, ratio, status, level | MQ-2 warm-up curve, baseline drift, response |
| `event` | environment | node_ms, EVENT_NAME, source, value | event timestamps (response times, false triggers) |
| `lc` | consumable (`stream`) | node_ms, raw, grams (`nan` until calibrated) | noise, drift, settling, step response |
| `avg` | consumable (`avg <n>`) | node_ms, n, mean_raw, sd_raw, mean_g, sd_g | known-mass accuracy, repeatability |
| `mass` | consumable | node_ms, grams, stable 0/1 | normal operation |
| `sent` | consumable | node_ms, grams, qty_est (-1 = none), transaction | what the portal recorded |
| `nfc` | reusable | node_ms, uid, accepted / duplicate | read success, duplicate suppression |
| `lid` | reusable | node_ms, opened, closed, open_ms, close_ms, reed fitted | servo / lid timing (only with the reed) |
| `http` | all three | node_ms, path, HTTP code, round_trip_ms | node -> portal latency, failures |
| `wifi` | all three | node_ms, connected / disconnected, RSSI dBm | reconnect behaviour and time |

`node_ms` is the ESP32's `millis()` (restarts at 0 on reset); `host_ms` is the
laptop clock, the one to use across devices.

## Load-cell statistics (from your logged rows only)

```
py loadcell_stats.py accuracy logs/<file>.csv     # needs "# ref <g>" notes before each avg
py loadcell_stats.py noise    logs/<file>.csv [--from <node_ms> --to <node_ms>]
py loadcell_stats.py drift    logs/<file>.csv
```

## Where the bench data goes

The three new nodes report as lab **BENCH** ("Bring-up bench (home)", not
bookable), so bench tests never mix with the Robotics Lab's history. Each has its
own device key (in its git-ignored `secrets.h`), so it can only report as itself.
Moving a node into the Robotics Lab later: set `LAB_ID = "LAB_01"` in its sketch,
re-flash, and move its device / bin / items to LAB_01 (one admin step - ask).
