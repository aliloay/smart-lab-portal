# Working prototypes
| # | Prototype | Address | Data |
|---|---|---|---|
| 1 | Simplified grouped navigation | every page | real roles |
| 2 | Unified health page | `/admin/health` | real API |
| 3 | Sensor/asset analytics | `/admin/sensors` | real API |
| + | Exhibition screen | `/exhibit` | real API, then last real values, then labelled example |

They were run in a test copy (backend 127.0.0.1:8100, page :5176) with its own Docker network and throw-away database. Pictures in `graphics/`;
their measurements are simulated and their device states belong to the test copy, not to the lab.

Exhibition: no names, host names, addresses, pictures or controls. After 25 s without a good answer it changes LIVE to HISTORICAL. It must be open
before the portal stops; a reload without the portal does not work. A safety alarm still appears on top.

Run again: start a copy, load `prototypes/load_simulated_metrics.py` (it refuses any database not named `smartlab_demo*`), then
`node e2e/expansion.mjs http://127.0.0.1:5176`.
