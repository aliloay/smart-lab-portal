import type { MetricHistory, MetricLatest } from './api'

/** One CSV text: a spreadsheet must not run a cell that starts like a formula, and empty buckets stay empty. */
const cell = (v: unknown) => {
  if (typeof v === 'number') return String(v)
  const s = String(v ?? '')
  return /[",\n\r]|^[=+\-@\t]/.test(s) ? `"${/^[=+\-@\t]/.test(s) ? "'" : ''}${s.replace(/"/g, '""')}"` : s
}
export function csv(h: Pick<MetricHistory, 'series'>, r: Pick<MetricLatest, 'device_uid' | 'metric_name' | 'unit' | 'metadata'>): string {
  const head = ['bucket_start_utc', 'device_uid', 'metric', 'unit', 'average', 'lowest', 'highest', 'readings', 'rejected', 'simulated']
  return '﻿' + [head, ...h.series.map(s => [s.t, r.device_uid, r.metric_name, r.unit, s.avg, s.min, s.max, s.n, s.rejected, r.metadata.simulated ? 'yes' : 'no'])]
    .map(x => x.map(cell).join(',')).join('\r\n') + '\r\n'
}
