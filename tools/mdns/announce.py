"""Announce the portal on the lab network as smartlab.local (mDNS, no router or DNS server needed).

Every phone/PC on the Smart_Lab network can then open https://smartlab.local. Only the laptop's
LAN addresses are announced (default: the Smart_Lab cable 192.168.1.200). Runs until closed.
Usage: py tools/mdns/announce.py [--ip 192.168.1.200] [--name smartlab]
"""
import argparse
import socket
import time

from zeroconf import IPVersion, ServiceInfo, Zeroconf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", action="append", default=[], help="address to announce (default 192.168.1.200)")
    ap.add_argument("--name", default="smartlab")
    a = ap.parse_args()
    ips = a.ip or ["192.168.1.200"]
    host = f"{a.name}.local."
    # Bind only to the announced addresses so the name never leaks onto another network (e.g. home Wi-Fi).
    zc = Zeroconf(interfaces=ips, ip_version=IPVersion.V4Only)
    infos = [ServiceInfo(t, f"Smart Lab portal.{t}", port=p, server=host,
                         addresses=[socket.inet_aton(i) for i in ips], properties={"path": "/"})
             for t, p in (("_https._tcp.local.", 443), ("_http._tcp.local.", 80))]
    for info in infos:
        zc.register_service(info, allow_name_change=True)
    print(f"Announcing https://{a.name}.local -> {', '.join(ips)}  (close this window to stop)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        for info in infos:
            zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    main()
