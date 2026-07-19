const STYLES = {
  processing: 'bg-amber-100 text-amber-800 border-amber-200',
  parsed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  failed: 'bg-red-100 text-red-800 border-red-200',
  documents_submitted: 'bg-blue-100 text-blue-800 border-blue-200',
}

export default function StatusBadge({ status }) {
  const style = STYLES[status] || 'bg-slate-100 text-slate-700 border-slate-200'
  const label = (status || 'unknown').replace(/_/g, ' ')

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${style}`}>
      {label}
    </span>
  )
}
