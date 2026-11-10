# Overlay and data integration

| Overlay | Drawn when | Colour (from `Scan.tsx`) | Data |
|---|---|---|---|
| Marker outline | A QR marker is decoded | Green when its record is known, amber otherwise | Marker corners from the decoder |
| Equipment box | The object detector sees equipment and one of our markers sits inside the box | Solid green, label "class · name"; dashed grey "unidentified (scan its marker)" | Lab detector (12 classes) via the camera service |
| People boxes | The camera service returns people | Per track | `POST /api/scan/people` |
| Live card | A target is selected or is the only identified one | Card pinned beside the target | `GET /api/scan/asset?code=`: the record of that key, with age and quality |
| History | Each new detection | List under the camera | Kept across refresh, max 30 |

Which information is live: device heartbeats, newest readings per metric (LIVE if ≤ 5 min old), robot joint values, door state and PC status, all read from the database at request time. Static: names and descriptions from the registry. No value is invented when a record has none: the card says "no reading in 24 h" or "never sent telemetry".

Markers: `/scan/markers` prints one marker per registry asset (41 in the current data). Stick each on a flat visible face, at least 4 cm wide.
