import { useCallback, useState } from 'react'

export default function Dropzone({ onFile, accept, label }) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (file) onFile(file)
    },
    [onFile],
  )

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`rounded-xl border-2 border-dashed p-8 text-center transition ${
        dragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white'
      }`}
    >
      <p className="mb-3 text-sm text-slate-600">{label}</p>
      <label className="inline-flex cursor-pointer items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
        Choose file
        <input
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
      </label>
    </div>
  )
}
