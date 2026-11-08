"""
The security camera's config carries each lab PC's power (2026-10-21): sitting at PC-07 showed "PC-08 in use"
on both cameras; the camera prefers the PC that is ON. Tested: the LAN check wins (on / off), an unknown PC is
None (never guessed off), the box name matches the PC's asset tag case-insensitively, robots carry nothing.
"""
from app.models import Asset, SecurityZone
from app.services import lan_presence


def _report(client, headers, lab, uid, tag, present):
    return client.post("/api/equipment/pc/presence", headers=headers, json={
        "lab_id": lab.code, "pcs": [{"device_uid": uid, "asset_tag": tag, "present": present,
                                     "ip": "192.168.1.150", "mac": "aa-bb-cc-dd-ee-ff", "via": "arp"}]})


def _config(client, headers, lab):
    return client.get("/api/security/config", headers=headers,
                      params={"device_uid": "SECCAM_T1", "lab_id": lab.code}).json()


def test_camera_config_has_pc_power_from_the_lan(client, db, lab, device_headers):
    lan_presence.clear()
    for tag in ("PC-07", "PC-08"):
        db.add(Asset(asset_tag=tag, name=tag, lab_id=lab.id))
    db.commit()
    cam_id = _config(client, device_headers, lab)["device_id"]           # registers the camera
    for name in ("pc-07", "PC-08", "PC-09", "UR5e"):
        db.add(SecurityZone(device_id=cam_id, name=name, kind="EQUIPMENT", x=0.1, y=0.1, w=0.05, h=0.05,
                            alert_on_motion=name != "UR5e"))
    db.commit()
    _report(client, device_headers, lab, "PC_07", "PC-07", True)
    _report(client, device_headers, lab, "PC_08", "PC-08", True)
    _report(client, device_headers, lab, "PC_08", "PC-08", False)        # unplugged
    zones = {z["name"]: z for z in _config(client, device_headers, lab)["zones"]}
    assert zones["pc-07"]["pc_on"] is True
    assert zones["PC-08"]["pc_on"] is False
    assert zones["PC-09"]["pc_on"] is None                             # never reported: unknown, not off
    assert zones["UR5e"]["pc_on"] is None
