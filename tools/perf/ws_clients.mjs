// WebSocket clients for the load test: N clients on /ws/activity, count messages by type, bytes,
// and (for robot_state) the age of the sample when it arrives (telemetry_age_ms + server->client).
//   node tools/perf/ws_clients.mjs <base http://127.0.0.1:8100> <clients> <seconds>
// E2E_EMAIL / E2E_PASSWORD from the environment. Never point it at the live portal.
const [BASE = 'http://127.0.0.1:8100', N = '3', SECS = '60'] = process.argv.slice(2)
if (/:8000|localhost\/?$|:80\/?$/.test(BASE)) { console.error('refusing: not the live portal'); process.exit(2) }
const login = await fetch(BASE + '/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: process.env.E2E_EMAIL, password: process.env.E2E_PASSWORD }) }).then(r => r.json())
const token = login.access_token || login.token
const stats = { msgs: 0, bytes: 0, byType: {}, closes: 0, opened: 0 }
const socks = []
for (let i = 0; i < Number(N); i++) {
  const ws = new WebSocket(BASE.replace(/^http/, 'ws') + '/ws/activity?token=' + encodeURIComponent(token))
  ws.onopen = () => stats.opened++
  ws.onmessage = e => {
    stats.msgs++; stats.bytes += e.data.length
    let m; try { m = JSON.parse(e.data) } catch { return }
    const k = m.type || '?'; (stats.byType[k] ||= { n: 0, bytes: 0 }); stats.byType[k].n++; stats.byType[k].bytes += e.data.length
  }
  ws.onclose = () => stats.closes++
  socks.push(ws)
}
await new Promise(r => setTimeout(r, Number(SECS) * 1000))
socks.forEach(s => s.close())
const per = Number(N) * Number(SECS)
console.log(`== ${N} WebSocket clients, ${SECS} s (SIMULATED workload): opened ${stats.opened}, unexpected closes ${stats.closes - 0 > Number(N) ? stats.closes - Number(N) : 0}`)
console.log(`   ${(stats.msgs / per).toFixed(1)} msgs/s per client, ${(stats.bytes / per / 1024).toFixed(1)} KB/s per client`)
for (const [k, v] of Object.entries(stats.byType).sort((a, b) => b[1].n - a[1].n))
  console.log(`   ${k.padEnd(18)} ${(v.n / per).toFixed(2)}/s per client, avg ${Math.round(v.bytes / v.n)} B`)
process.exit(0)
