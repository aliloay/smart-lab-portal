# Device compatibility

| Requirement | Detail |
|---|---|
| Browser | A current mobile browser with `getUserMedia` (Chrome / Edge on Android, Safari on iOS). Native BarcodeDetector where available (Chrome on Android); otherwise the jsQR Web Worker is used automatically |
| Connection | HTTPS to the portal on the Smart_Lab Wi-Fi, with the Smart Lab CA trusted on the phone |
| Camera | Rear camera; the zoom control helps with small or far markers |
| Network | Local only; no internet needed for marker decoding or live cards |

Measured on 26 Oct 2026 in headless Chrome at phone size with a fake camera: **not yet on a real phone**. Marker to live card 226-255 ms warm (1.2-2.4 s on first start); jsQR decode 12-55 ms per check on a desktop CPU; people boxes at 7 frames/s from real lab footage. A real-phone measurement is still open.
