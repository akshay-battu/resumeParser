import { useEffect, useState } from 'react'

export default function DocumentFileInput({ label, accept, file, onChange }) {
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    if (!file) {
      setPreview(null)
      return undefined
    }
    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file)
      setPreview(url)
      return () => URL.revokeObjectURL(url)
    }
    setPreview(null)
    return undefined
  }, [file])

  return (
    <div>
      <label className="mb-1 block text-sm font-medium">{label}</label>
      <input
        type="file"
        accept={accept}
        onChange={(e) => onChange(e.target.files?.[0] || null)}
        className="block w-full text-sm"
      />
      {file && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-600">{file.name}</p>
          {preview ? (
            <img
              src={preview}
              alt={`${label} preview`}
              className="mt-2 max-h-32 rounded border border-slate-200 object-contain"
            />
          ) : (
            <p className="mt-1 text-xs text-slate-500">PDF selected — preview not available</p>
          )}
        </div>
      )}
    </div>
  )
}
