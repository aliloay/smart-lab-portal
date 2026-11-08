"""On/off decision of tools/lan_presence (no network needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lan_presence as L                                    # noqa: E402


def pc():
    return L.Pc({"device_uid": "PC_01", "mac": "60:EB:69:6B:C8:50"})


def test_mac_is_normalised():
    assert pc().mac == "60-eb-69-6b-c8-50"


def test_ping_reply_is_present_and_misses_turn_it_off_after_three():
    p = pc()
    p.decide(True, None)
    assert p.present and p.via == "ping"
    for _ in range(L.MISSES_OFF - 1):
        p.decide(False, 5)                                  # ARP still says Reachable: not trusted once ping worked
        assert p.present
    p.decide(False, 5)
    assert not p.present and p.via == "ping"
    p.decide(True, 5)
    assert p.present and p.misses == 0


def test_firewalled_pc_follows_the_neighbour_table():
    p = pc()
    p.decide(False, 5)                                      # Reachable
    assert p.present and p.via == "arp"
    for re_checking in (4, 3, 2):                           # Stale / Delay / Probe: keep the decision
        p.decide(False, re_checking)
        assert p.present
    p.decide(False, 0)                                      # Unreachable
    assert not p.present
    p.decide(False, None)                                   # no entry at all
    assert not p.present


def test_never_seen_pc_is_absent():
    p = pc()
    p.decide(False, None)
    assert not p.present and p.via == "arp"


def test_pcs_reported_by_their_agents_are_added_without_a_mac_list():
    pcs = [pc()]
    added = L.merge_targets(pcs, [
        {"device_uid": "PC_07", "asset_tag": "PC-07", "macs": ["AA:BB:CC:DD:EE:07"], "ips": ["192.168.1.107"]},
        {"device_uid": "PC_01", "asset_tag": "PC-01", "macs": ["60-eb-69-6b-c8-50", "70-f3-95-e5-db-57"]},
        {"device_uid": "PC_08", "macs": []}])
    assert added == ["PC-07", "PC_01 (+MAC)"]
    p7 = next(p for p in pcs if p.uid == "PC_07")
    assert p7.macs == {"aa-bb-cc-dd-ee-07"} and p7.ip == "192.168.1.107"
    assert L.merge_targets(pcs, [{"device_uid": "PC_07", "macs": ["aa-bb-cc-dd-ee-07"]}]) == []   # nothing new


def test_dual_nic_pc_is_pinged_on_its_smart_lab_address():
    # 2026-11-03 Gemini network audit: the lab engineer PC reports GIU 10.40.20.x and Smart Lab 192.168.1.210
    pcs = []
    L.merge_targets(pcs, [{"device_uid": "PC_ENG", "macs": ["aa-bb-cc-dd-ee-ff"], "ips": ["10.40.20.17", "192.168.1.210"]}])
    assert pcs[0].ip == "192.168.1.210"
