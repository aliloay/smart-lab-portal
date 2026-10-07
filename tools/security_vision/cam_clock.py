"""Read (and with --set, set) the MC210 clock over ONVIF on port 2020.
Credentials come from the gitignored camera.env RTSP URL. The MC210 forgets
its clock when it loses power, so start_security_vision.bat runs --set."""
import base64, datetime, hashlib, os, re, sys, urllib.parse, urllib.request

env = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera.env"), encoding="utf-8").read()
url = re.search(r"rtsp://[^\s\"]+", env).group(0)
u = urllib.parse.urlsplit(url)
USER, PW, HOST = urllib.parse.unquote(u.username), urllib.parse.unquote(u.password), u.hostname
EP = f"http://{HOST}:2020/onvif/device_service"


def security():
    nonce = os.urandom(16)
    created = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + PW.encode()).digest()).decode()
    return f"""<s:Header><Security s:mustUnderstand="1" xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<UsernameToken><Username>{USER}</Username>
<Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</Password>
<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{base64.b64encode(nonce).decode()}</Nonce>
<Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">{created}</Created>
</UsernameToken></Security></s:Header>"""


def call(body, auth=True):
    env = (f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
           f'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">'
           f'{security() if auth else ""}<s:Body>{body}</s:Body></s:Envelope>')
    req = urllib.request.Request(EP, env.encode(), {"Content-Type": "application/soap+xml; charset=utf-8"})
    try:
        return urllib.request.urlopen(req, timeout=8).read().decode()
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: " + e.read().decode()[:600]


def show(xml):
    tz = re.search(r"<tt:TZ>(.*?)</tt:TZ>", xml)
    kind = re.search(r"<tt:DateTimeType>(.*?)</tt:DateTimeType>", xml)
    for part in ("UTCDateTime", "LocalDateTime"):
        m = re.search(rf"<tt:{part}>.*?<tt:Hour>(\d+)</tt:Hour><tt:Minute>(\d+)</tt:Minute><tt:Second>(\d+)</tt:Second>"
                      rf".*?<tt:Year>(\d+)</tt:Year><tt:Month>(\d+)</tt:Month><tt:Day>(\d+)</tt:Day>", xml, re.S)
        if not m:
            m2 = re.search(rf"<tt:{part}>(.*?)</tt:{part}>", xml, re.S)
            print(part, "raw:", re.sub(r"\s+", " ", m2.group(1)) if m2 else "-")
        else:
            h, mi, s, y, mo, d = m.groups()
            print(f"{part}: {y}-{int(mo):02d}-{int(d):02d} {int(h):02d}:{int(mi):02d}:{int(s):02d}")
    print("type:", kind.group(1) if kind else "-", "| TZ:", tz.group(1) if tz else "-")


xml = call("<tds:GetSystemDateAndTime/>", auth=False)
if "UTCDateTime" not in xml and "LocalDateTime" not in xml:
    xml = call("<tds:GetSystemDateAndTime/>")
print("camera says:"); show(xml) if "DateTime" in xml else print(xml[:800])
print("laptop UTC:  ", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

if "--set" in sys.argv:
    n = datetime.datetime.now(datetime.timezone.utc)
    body = (f"<tds:SetSystemDateAndTime><tds:DateTimeType>Manual</tds:DateTimeType>"
            f"<tds:DaylightSavings>false</tds:DaylightSavings>"
            f"<tds:TimeZone><tt:TZ>GMT-03:00</tt:TZ></tds:TimeZone>"
            f"<tds:UTCDateTime><tt:Time><tt:Hour>{n.hour}</tt:Hour><tt:Minute>{n.minute}</tt:Minute>"
            f"<tt:Second>{n.second}</tt:Second></tt:Time><tt:Date><tt:Year>{n.year}</tt:Year>"
            f"<tt:Month>{n.month}</tt:Month><tt:Day>{n.day}</tt:Day></tt:Date></tds:UTCDateTime>"
            f"</tds:SetSystemDateAndTime>")
    r = call(body)
    print("set:", "OK" if "SetSystemDateAndTimeResponse" in r else r[:800])
    print("camera now says:"); show(call("<tds:GetSystemDateAndTime/>"))
