export default function DocumentViewer({ label, doc, candidateId }) {
  if (!doc?.available) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">
        {label}: not uploaded
      </div>
    )
  }

  const url = doc.url || `/candidates/${candidateId}/documents/${label.toLowerCase()}`
  const isPdf = doc.filename?.toLowerCase().endsWith('.pdf')
  const isImage = /\.(jpg|jpeg|png)$/i.test(doc.filename || '')

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium text-slate-800">{label}</h4>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-indigo-600 hover:underline"
        >
          Open / Download
        </a>
      </div>
      <p className="mb-3 text-xs text-slate-500">{doc.filename}</p>
      {isImage && (
        <img
          src={url}
          alt={`${label} document`}
          className="max-h-48 w-full rounded border border-slate-200 object-contain bg-white"
        />
      )}
      {isPdf && (
        <div className="flex items-center gap-2 rounded bg-white px-3 py-2 text-sm text-slate-600">
          <span>PDF document</span>
          <a href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
            View PDF
          </a>
        </div>
      )}
      {!isImage && !isPdf && doc.available && (
        <a href={url} className="text-sm text-indigo-600 hover:underline">
          Download file
        </a>
      )}
    </div>
  )
}
