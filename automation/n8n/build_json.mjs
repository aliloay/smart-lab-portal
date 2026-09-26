/**
 * Compile src/*.ts (n8n Workflow SDK) into importable n8n JSON in json/.
 *
 *   npm i --no-save @n8n/workflow-sdk@0.33.1   (once, in this folder)
 *   node build_json.mjs
 *
 * Output is deterministic (node ids derived from workflow + node name) so a
 * re-run only changes what changed. Credentials are referenced BY NAME only
 * ("Smart Lab automation key", "Smart Lab webhook token"); no id, key or
 * secret is ever written - create those two credentials in n8n after import.
 */
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { parseWorkflowCode } = require('@n8n/workflow-sdk')
const here = new URL('.', import.meta.url).pathname
const manifest = JSON.parse(readFileSync(here + 'workflows.json', 'utf8')).workflows

const CREDENTIAL_NAMES = {
  httpTemplatedCustomAuth: 'Smart Lab automation key',   // X-Automation-Key
  httpHeaderAuth: 'Smart Lab webhook token',              // X-Smartlab-Token
}

const uuid = s => {
  const h = createHash('sha1').update(s).digest('hex')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-5${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`
}

mkdirSync(here + 'json', { recursive: true })
for (const file of readdirSync(here + 'src').filter(f => f.endsWith('.ts')).sort()) {
  const code = readFileSync(here + 'src/' + file, 'utf8').replace(/^import .*\n/m, '')
  const wf = parseWorkflowCode(code)
  const entry = manifest.find(m => m.file === 'src/' + file)
  for (const n of wf.nodes) {
    n.id = uuid(file + '/' + n.name)
    for (const type of Object.keys(n.credentials ?? {})) {
      n.credentials[type] = { name: CREDENTIAL_NAMES[type] }
    }
    if (n.webhookId !== undefined) n.webhookId = uuid('webhook/' + file + '/' + n.name)
  }
  const out = { id: entry?.id ?? wf.id, name: wf.name, active: false,
                nodes: wf.nodes, connections: wf.connections,
                settings: wf.settings ?? { executionOrder: 'v1' }, tags: [] }
  writeFileSync(here + 'json/' + file.replace('.ts', '.json'), JSON.stringify(out, null, 2) + '\n')
  console.log('built', file, `${wf.nodes.length} nodes`)
}
