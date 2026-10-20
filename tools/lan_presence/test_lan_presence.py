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
