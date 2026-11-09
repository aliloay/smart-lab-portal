# Mobile camera

1. **Secure page required.** Browsers only allow `getUserMedia` in a secure context. The Scan page checks `window.isSecureContext`; over plain `http://<laptop-ip>` the camera is refused, and the page says so ("The camera needs a secure page (https://)").
2. **HTTPS on the local network.** nginx serves the portal on `https://<laptop>/` with a certificate issued by the local Smart Lab CA. Each phone trusts the CA once: open `/phone-setup`, download `/smartlab-ca.crt` (public certificate only) and follow the Android or iPhone steps shown. The CA private key is kept out of the nginx folder (`deploy/tls-ca/`, see [SECURITY.md](../SECURITY.md)).
3. **Permission.** On Start the page requests the rear camera (`facingMode: environment`, video only, no audio). Denying it shows a retry hint.
4. **Capture.** The video stays on the phone. About 4 marker checks per second; people frames at most every 0.8 s and only when the view changed (motion gating). Zoom crops the centre so small far markers decode.
5. **Release.** Stop, hiding the tab or leaving the page releases the camera, microphone, loops and worker (5/5 cycles verified in the headless test).
