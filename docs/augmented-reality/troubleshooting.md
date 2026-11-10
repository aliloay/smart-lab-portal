# AR troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "The camera needs a secure page" | Opened over `http://` | Open `https://<laptop>/scan`; trust the CA via `/phone-setup` |
| Certificate warning on the phone | Smart Lab CA not trusted | Install `/smartlab-ca.crt` and enable full trust (iPhone: Settings → General → About → Certificate Trust Settings) |
| Camera permission denied | Browser setting | Allow the camera for the portal's address and press Start again |
| Marker not decoded | Too small, far, glare or angled | Zoom in, move closer, avoid reflections; markers ≥ 4 cm |
| "unidentified (scan its marker)" | No marker inside the detected box | Point at the marker; equipment is named only through its own marker |
| No people boxes | Camera service not running or busy | Start `tools/security_vision` (launch.bat); the page retries after 3-5 s |
| Card says STALE | The device has not reported for > 5 min | Check the device and its Wi-Fi |
