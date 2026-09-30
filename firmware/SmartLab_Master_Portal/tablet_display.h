// ===========================================================================
// TABLET DISPLAY - a second, larger, READ-ONLY view of the access station.
//
// The TFT stays the local display and is not touched. This file only READS
// the same state the TFT is drawn from (state, verifyPromptShown, step1Label,
// pendingUserIndex, deniedReason, heldOpenAlarmed, ...) and serves it to a
// browser on the same Wi-Fi:
//
//     http://<Master ESP32 IP>/        the tablet page
//     http://<Master ESP32 IP>/state   the current state as JSON
//
// Guarantees:
//   - Two GET routes, nothing else (anything else is a 404). No route writes
//     a variable, calls a state transition or touches the relay/lock, so no
//     request - including one from a modified page - can open the door.
//   - handleClient() is non-blocking and a /state reply is ~1 KB, so the
//     access logic keeps its timing. With no tablet, it costs nothing.
//   - Wording is taken from the TFT screens in SmartLab_Master_Portal.ino so
//     both displays say the same thing.
//
// Included from the .ino just before setup(), where every variable and
// helper it reads (friendlyReason, cameraHealthy, authorizedUsers, ...) is
// already declared.
// ===========================================================================
#pragma once
#include <WebServer.h>

static WebServer tabletServer(80);

// --- tiny JSON writer (names and reasons are short firmware strings) --------
static void tjStr(String &o, const char *s) {
  o += '"';
  for (const char *p = s ? s : ""; *p; ++p) {
    char c = *p;
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if ((uint8_t)c < 0x20) o += ' ';
    else o += c;
  }
  o += '"';
}
static void tjKey(String &o, const char *k) { tjStr(o, k); o += ':'; }
static void tjKV(String &o, const char *k, const char *v) { tjKey(o, k); tjStr(o, v); o += ','; }
static void tjKV(String &o, const char *k, bool v) { tjKey(o, k); o += v ? "true" : "false"; o += ','; }
static void tjKV(String &o, const char *k, long v) { tjKey(o, k); o += String(v); o += ','; }

// Mirrors updateDisplay(): same states, same branches, same words.
static void tabletHandleState() {
  const char *name = (pendingUserIndex >= 0) ? authorizedUsers[pendingUserIndex].displayName : "";
  const char *screen = "idle", *tone = "idle", *header = "SMART LAB", *title = "";
  const char *lines[5] = {nullptr, nullptr, nullptr, nullptr, nullptr};
  const char *note = nullptr;
  int step = 0;
  long remainingMs = -1;

  switch (state) {
    case STATE_IDLE:
      screen = "idle"; title = "WELCOME"; step = 1;
      lines[0] = "Scan your QR code"; lines[1] = "or RFID tag / card";
      if (rfidLinkDown && !cameraHealthy()) note = "Readers offline - call staff";
      else if (rfidLinkDown)                note = "RFID offline - use QR code";
      else if (!cameraHealthy())            note = "Camera offline - use card";
      break;
    case STATE_WAIT_FINGERPRINT:
      step = 2; tone = "ok";
      if (verifyPromptShown) {
        screen = "verify"; title = "VERIFY"; tone = "idle";
        lines[0] = "Look at the camera"; lines[1] = "or place your finger";
        uint32_t used = millis() - stateEnteredMs;
        remainingMs = used >= FINGERPRINT_TIMEOUT_MS ? 0 : (long)(FINGERPRINT_TIMEOUT_MS - used);
      } else {
        screen = "step1ok"; title = step1Label;
      }
      break;
    case STATE_ACCESS_GRANTED:
    case STATE_DOOR_UNLOCKED_WAIT_OPEN:
      screen = "granted"; tone = "ok"; header = "DOOR UNLOCKED"; title = "ACCESS GRANTED";
      break;
    case STATE_DOOR_OPEN_WAIT_CLOSE:
      if (heldOpenAlarmed) {
        screen = "heldopen"; tone = "bad"; header = "DOOR HELD OPEN"; title = "CLOSE THE DOOR";
        lines[0] = "Open for too long"; lines[1] = "Staff have been notified";
      } else {
        screen = "dooropen"; title = "DOOR OPEN";
        lines[0] = "Please close the door"; lines[1] = "behind you";
      }
      break;
    case STATE_ACCESS_DENIED:
      screen = "denied"; tone = "bad"; header = "DOOR LOCKED"; title = "ACCESS DENIED";
      lines[0] = friendlyReason(deniedReason);
      break;
    case STATE_DOOR_ALARM:
      screen = "alarm"; tone = "bad"; header = "! SECURITY ALERT !"; title = "FORCED ENTRY";
      lines[0] = "Door opened while locked"; lines[1] = "Staff have been notified";
      lines[2] = "Please close the door";
      break;
  }

  String o; o.reserve(900);
  o += '{';
  tjKV(o, "screen", screen); tjKV(o, "tone", tone); tjKV(o, "header", header);
  tjKV(o, "title", title); tjKV(o, "name", name);
  tjKV(o, "note", note ? note : "");
  tjKey(o, "lines"); o += '[';
  bool first = true;
  for (auto l : lines) if (l && *l) { if (!first) o += ','; tjStr(o, l); first = false; }
  o += "],";
  tjKV(o, "step", (long)step);
  tjKV(o, "remainingMs", remainingMs);
  tjKV(o, "totalMs", (long)FINGERPRINT_TIMEOUT_MS);
  tjKV(o, "method", (state == STATE_WAIT_FINGERPRINT) ? step1Label : "");
  tjKV(o, "viaPortal", (bool)(pendingViaPortal && pendingUserIndex >= 0));
  // Station facts the ESP32 already tracks (read-only).
  tjKV(o, "lab", LAB_ID); tjKV(o, "device", DEVICE_ID);
  tjKV(o, "doorClosed", doorClosed);
  tjKV(o, "lockReleased", relayUnlocked);
  tjKV(o, "camera", cameraHealthy());
  tjKV(o, "fingerprint", fpOk);
  tjKV(o, "rfidReader", !rfidLinkDown);
  tjKV(o, "portalIntegration", BACKEND_ENABLED);
  tjKV(o, "wifi", WiFi.status() == WL_CONNECTED);
  tjKV(o, "rssi", (long)WiFi.RSSI());
  tjKV(o, "ip", WiFi.localIP().toString().c_str());
  tjKey(o, "uptimeS"); o += String(millis() / 1000);
  o += '}';

  tabletServer.sendHeader("Cache-Control", "no-store");
  tabletServer.send(200, "application/json", o);
}

// --- the page ------------------------------------------------------------------
static const char TABLET_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0d1a2e">
<title>Smart Lab - Access Station</title>
<style>
:root{--bg:#0d1a2e;--glass:rgba(36,58,92,.62);--line:rgba(148,184,226,.14);--txt:#f1f5f9;--sub:#94a3b8;
--cy:#38bdf8;--ok:#10b981;--bad:#ef4444;--warn:#f59e0b}
*{box-sizing:border-box;margin:0}
[hidden]{display:none!important}
html,body{height:100%}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--txt);
background:radial-gradient(1200px 600px at 10% -10%,rgba(14,165,233,.14),transparent 60%),
radial-gradient(900px 500px at 100% 0,rgba(139,92,246,.08),transparent 55%),
linear-gradient(180deg,#152642,#101e35);display:flex;flex-direction:column;overflow:hidden}
body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.5;
background-image:linear-gradient(rgba(148,184,226,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(148,184,226,.06) 1px,transparent 1px);
background-size:32px 32px}
header{display:flex;align-items:center;justify-content:space-between;padding:2.2vh 3vw;border-bottom:1px solid var(--line);
background:rgba(13,26,46,.55);backdrop-filter:blur(12px);position:relative}
.brand{font-weight:800;letter-spacing:.18em;font-size:clamp(16px,2.4vw,28px)}
.brand b{color:var(--cy)}
.lab{font-family:ui-monospace,Consolas,monospace;color:var(--sub);font-size:clamp(13px,1.8vw,20px);letter-spacing:.1em}
main{flex:1;display:flex;align-items:center;justify-content:center;padding:3vh 4vw;position:relative}
.card{width:min(1100px,100%);border-radius:28px;border:1px solid var(--line);background:var(--glass);
backdrop-filter:blur(16px);box-shadow:0 1px 0 rgba(255,255,255,.06) inset,0 30px 60px -30px rgba(2,6,23,.9);
padding:5vh 5vw;text-align:center;transition:background .3s,border-color .3s}
.card.ok{background:linear-gradient(180deg,rgba(16,185,129,.30),rgba(6,95,70,.35));border-color:rgba(52,211,153,.45)}
.card.bad{background:linear-gradient(180deg,rgba(239,68,68,.30),rgba(127,29,29,.40));border-color:rgba(248,113,113,.5)}
.hdr{font-family:ui-monospace,Consolas,monospace;letter-spacing:.2em;font-size:clamp(13px,1.8vw,20px);color:var(--sub);margin-bottom:2.5vh}
.icon{width:clamp(80px,13vh,150px);height:clamp(80px,13vh,150px);margin:0 auto 2.5vh;border-radius:50%;display:grid;place-items:center;
border:2px solid rgba(255,255,255,.5)}
.icon svg{width:55%;height:55%}
h1{font-size:clamp(40px,8vw,104px);line-height:1.02;font-weight:800;letter-spacing:.02em}
.name{margin-top:1.6vh;font-size:clamp(26px,4.6vw,60px);font-weight:700;color:#a7f3d0}
.card:not(.ok) .name{color:#bae6fd}
.lines{margin-top:2.4vh;font-size:clamp(18px,2.8vw,34px);color:#e2e8f0;line-height:1.35}
.note{margin-top:2vh;font-size:clamp(16px,2.2vw,26px);color:var(--warn);font-weight:600}
.step{margin-top:3vh;display:inline-block;padding:.6vh 1.6vw;border-radius:999px;border:1px solid rgba(56,189,248,.45);
color:var(--cy);font-family:ui-monospace,Consolas,monospace;letter-spacing:.2em;font-size:clamp(13px,1.8vw,20px)}
.bar{margin:3vh auto 0;height:12px;width:min(700px,90%);border-radius:99px;background:rgba(148,184,226,.15);overflow:hidden}
.bar i{display:block;height:100%;width:100%;background:var(--ok);transition:width .4s linear}
.bar.low i{background:var(--warn)}
footer{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border-top:1px solid var(--line)}
footer div{background:rgba(13,26,46,.72);padding:1.6vh 1.6vw}
footer small{display:block;color:var(--sub);font-size:clamp(11px,1.3vw,14px);letter-spacing:.14em;text-transform:uppercase}
footer span{font-size:clamp(14px,1.9vw,22px);font-weight:600}
.g{color:var(--ok)}.r{color:var(--bad)}.m{color:var(--sub)}.y{color:var(--warn)}
#conn{position:fixed;top:12px;left:50%;transform:translateX(-50%);padding:10px 22px;border-radius:999px;font-weight:700;
letter-spacing:.14em;font-size:clamp(12px,1.6vw,18px);display:none;z-index:5}
#conn.down{display:block;background:#7f1d1d;border:1px solid #f87171}
#conn.up{display:block;background:#065f46;border:1px solid #34d399}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<div id="conn"></div>
<header><div class="brand">GIU &middot; SMART <b>LAB</b></div><div class="lab" id="lab">ACCESS STATION</div></header>
<main><div class="card" id="card">
<div class="hdr" id="hdr">SMART LAB</div>
<div class="icon" id="icon" hidden></div>
<h1 id="title">CONNECTING&hellip;</h1>
<div class="name" id="name" hidden></div>
<div class="lines" id="lines"></div>
<div class="note" id="note" hidden></div>
<div class="bar" id="bar" hidden><i id="barFill"></i></div>
<div class="step" id="step" hidden></div>
</div></main>
<footer>
<div><small>Door</small><span id="fDoor" class="m">&ndash;</span></div>
<div><small>Lock</small><span id="fLock" class="m">&ndash;</span></div>
<div><small>Camera / Face</small><span id="fCam" class="m">&ndash;</span></div>
<div><small>Fingerprint</small><span id="fFp" class="m">&ndash;</span></div>
<div><small>RFID reader</small><span id="fRfid" class="m">&ndash;</span></div>
<div><small>Network</small><span id="fNet" class="m">&ndash;</span></div>
</footer>
<script>
var CHECK='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
var CROSS='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
var WARN='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18h.01"/></svg>';
function $(i){return document.getElementById(i)}
function set(el,txt,cls){el.textContent=txt;el.className=cls||''}
var fails=0,wasDown=false,upTimer=null;
function render(s){
 var c=$('card');c.className='card'+(s.tone==='ok'?' ok':s.tone==='bad'?' bad':'');
 $('hdr').textContent=s.header;$('lab').textContent=s.lab+' · ACCESS STATION';
 $('title').textContent=s.title;
 var ic=$('icon');
 if(s.screen==='granted'||s.screen==='step1ok'){ic.innerHTML=CHECK;ic.hidden=false}
 else if(s.screen==='denied'){ic.innerHTML=CROSS;ic.hidden=false}
 else if(s.screen==='alarm'||s.screen==='heldopen'){ic.innerHTML=WARN;ic.hidden=false}
 else ic.hidden=true;
 var n=$('name');n.textContent=s.name;n.hidden=!s.name;
 var L=$('lines');L.innerHTML='';s.lines.forEach(function(t){var d=document.createElement('div');d.textContent=t;L.appendChild(d)});
 if(s.viaPortal&&s.screen!=='idle'){var d=document.createElement('div');d.className='m';d.textContent='Booking verified by the portal';L.appendChild(d)}
 var nt=$('note');nt.textContent=s.note;nt.hidden=!s.note;
 var st=$('step');st.hidden=!s.step;st.textContent='STEP '+s.step+' OF 2';
 var b=$('bar');
 if(s.remainingMs>=0){b.hidden=false;var p=Math.max(0,Math.min(100,100*s.remainingMs/s.totalMs));
  $('barFill').style.width=p+'%';b.className='bar'+(s.remainingMs<5000?' low':'')}else b.hidden=true;
 set($('fDoor'),s.doorClosed?'Closed':'Open',s.doorClosed?'g':'y');
 set($('fLock'),s.lockReleased?'Released':'Locked',s.lockReleased?'y':'g');
 set($('fCam'),s.camera?'Online':'Offline',s.camera?'g':'r');
 set($('fFp'),s.fingerprint?'Ready':'Not detected',s.fingerprint?'g':'r');
 set($('fRfid'),s.rfidReader?'Ready':'Offline',s.rfidReader?'g':'r');
 set($('fNet'),s.ip+' · '+s.rssi+' dBm',s.wifi?'g':'r');
}
function conn(down){
 var e=$('conn');
 if(down){e.className='down';e.textContent='TABLET DISCONNECTED · RECONNECTING';wasDown=true;return}
 if(wasDown){wasDown=false;e.className='up';e.textContent='TABLET CONNECTED';clearTimeout(upTimer);upTimer=setTimeout(function(){e.className=''},3000)}
}
function poll(){
 var ctl=new AbortController(),t=setTimeout(function(){ctl.abort()},2500);
 fetch('/state',{cache:'no-store',signal:ctl.signal}).then(function(r){return r.json()})
 .then(function(s){clearTimeout(t);fails=0;conn(false);render(s)})
 .catch(function(){clearTimeout(t);if(++fails>=3)conn(true)})
 .then(function(){setTimeout(poll,fails?1500:500)});
}
poll();
</script></body></html>)HTML";

static void tabletHandlePage() {
  tabletServer.sendHeader("Cache-Control", "no-store");
  tabletServer.send_P(200, "text/html", TABLET_PAGE);
}

// Called once from setup(), after the existing Wi-Fi start. Listens on every
// interface, so it also works if Wi-Fi only connects later.
void tabletBegin() {
  tabletServer.on("/", HTTP_GET, tabletHandlePage);
  tabletServer.on("/state", HTTP_GET, tabletHandleState);
  tabletServer.onNotFound([]() { tabletServer.send(404, "text/plain", "Not found"); });
  tabletServer.begin();
  Serial.print("[TABLET] Read-only display at http://");
  Serial.print(WiFi.localIP());
  Serial.println("/  (same Wi-Fi)");
}

// Called every loop(). Returns at once when no tablet is asking.
void tabletLoop() {
  tabletServer.handleClient();
}
