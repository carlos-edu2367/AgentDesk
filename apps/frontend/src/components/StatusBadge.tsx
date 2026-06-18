import type { ExecutionStatus } from '../types/domain'

const STATUS_STYLES: Record<string, string> = {
  pending:          'bg-amber-500/15 text-amber-400 border-amber-500/30',
  running:          'bg-blue-500/15 text-blue-400 border-blue-500/30',
  waiting_approval: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  completed:        'bg-green-500/15 text-green-400 border-green-500/30',
  failed:           'bg-red-500/15 text-red-400 border-red-500/30',
  cancelled:        'bg-slate-500/15 text-slate-400 border-slate-500/30',
  ok:               'bg-green-500/15 text-green-400 border-green-500/30',
  online:           'bg-green-500/15 text-green-400 border-green-500/30',
  offline:          'bg-red-500/15 text-red-400 border-red-500/30',
  checking:         'bg-amber-500/15 text-amber-400 border-amber-500/30',
}

interface Props {
  status: ExecutionStatus | string
  className?: string
}

export function StatusBadge({ status, className = '' }: Props) {
  const style = STATUS_STYLES[status] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${style} ${className}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
