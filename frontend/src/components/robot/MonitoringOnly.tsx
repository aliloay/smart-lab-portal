import { Eye } from 'lucide-react'

/** Robots are monitored, never commanded, from the portal (owner decision 2026-10-29: the project is monitoring and
 *  analysis). Moving or stopping a robot is done at its teach pendant; the pendant / cell E-stops are the only stops. */
export function MonitoringOnly({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-start gap-2 rounded-lg border border-sky-400/30 bg-sky-500/10 text-sky-100 ${compact ? 'px-3 py-2 text-xs' : 'px-4 py-3 text-sm'}`}>
      <Eye size={compact ? 14 : 16} className="mt-0.5 shrink-0 text-sky-300" />
      <span><b>Monitoring only.</b> The portal shows this robot live and raises alerts; it never moves or stops it.
        Use the teach pendant to move the robot, and the pendant or cell E-stop to stop it.</span>
    </div>
  )
}
