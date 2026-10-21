// Lab PCs on Windows 7 run old Chrome (2026-10-21: sign-in failed with "structuredClone is not defined").
// Offline: node --test e2e/old_browser_compat.test.mjs - no unguarded API newer than Chrome 87 in src/.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const files = []
const walk = d => { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : /\.(ts|tsx)$/.test(f) && files.push(p) } }
walk(new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))

// [pattern, allowed only when the line also matches this guard]
const RULES = [
  [/structuredClone\(/, /typeof structuredClone === 'function'/],      // Chrome 98
  [/crypto\.randomUUID\(/, /randomUUID\?\.\(/],                         // Chrome 92 + secure pages only (lab uses http)
  [/AbortSignal\.timeout\(/, null],                                     // Chrome 103
  [/\.(toSorted|toReversed|toSpliced|findLast|findLastIndex)\(/, null], // Chrome 97-110
  [/Object\.hasOwn\(/, null], [/Promise\.withResolvers\(/, null],
]

test('no unguarded new browser API in the web app', () => {
  const bad = []
  for (const f of files) readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
    for (const [re, guard] of RULES) if (re.test(line) && !(guard && guard.test(line))) bad.push(`${f}:${i + 1}: ${line.trim().slice(0, 90)}`)
  })
  assert.deepEqual(bad, [])
})
