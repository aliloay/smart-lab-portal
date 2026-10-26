// Copy to secrets.h (gitignored) and fill in. Never commit secrets.h.
#pragma once

const char *WIFI_SSID = "Smart_Lab";
const char *WIFI_PASS = "your-wifi-password";

// This device's OWN key, issued on the portal's Devices page for UR5E_STOP_RELAY.
// The shared door key is refused by /api/robots/stop-relay/poll.
const char *DEVICE_KEY = "issue-on-the-devices-page";
