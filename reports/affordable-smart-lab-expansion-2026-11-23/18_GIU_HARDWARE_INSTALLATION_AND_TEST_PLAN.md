# GIU installation and test plan (owner, later)
Do one step, check it, then go on. Door, relays, robots and OPC UA are not touched.

1. **Before:** save the env-0.1.1 image; note the ENV node readings; power off before wiring.
2. **Firmware only:** copy `secrets.h`, compile with the known core, flash ENV_LAB01 by USB (owner). Pass: temperature, humidity, smoke, flame and
   motion as before; three new metrics in Sensor analytics; alarms still raise and clear in a supervised test; 1 h without reboot.
3. **I2C check:** power off, pull-ups measured to 3V3; power on; SDA/SCL at 3.3 V, never 5 V.
4. **BH1750:** set FIT_BH1750 true. Pass: covered near 0, lamp on higher; unplug: `bh1750` false and no old value as new.
5. **SCD41:** set FIT_SCD41 true. Pass: outdoor value recorded for 10 minutes and noted as reference (not assumed 420); breath raises it; warm-up noted.
6. **DS18B20, leak, INA219** (firmware part not written yet): multimeter comparison at three loads for INA219; stay below 26 V and 3.2 A.
7. **Soak 24 h:** coverage at least 95 %, gaps explained, no extra offline alerts.
8. **Record:** value, reference instrument, date, person. Without a reference write "not calibrated".

Mains energy: not part of this plan. If wanted: a certified plug-in or DIN meter installed under the university's electrical procedure, isolated output.
Stop: any door, alarm or safety reading that behaves differently. Roll back to env-0.1.1.
