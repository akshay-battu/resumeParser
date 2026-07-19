import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadResume } from '../api/client'
import Dropzone from '../components/Dropzone'
import Layout from '../components/Layout'

export default function UploadPage() {
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFile = async (file) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx'].includes(ext)) {
      setError('Only PDF and DOCX files are allowed.')
      return
    }

    setError('')
    setLoading(true)
    setProgress(0)

    try {
      const result = await uploadResume(file, (pct) => setProgress(Math.min(pct, 90)))
      setProgress(100)
      navigate(`/candidates/${result.id}`)
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-2 text-2xl font-bold">Upload Resume</h1>
        <p className="mb-6 text-slate-600">
          Upload a candidate resume (PDF or DOCX) to extract structured profile data.
        </p>

        <Dropzone
          label="Drag and drop a resume here, or click to browse"
          accept=".pdf,.docx"
          onFile={handleFile}
        />

        {loading && (
          <div className="mt-6">
            <div className="mb-2 flex justify-between text-sm text-slate-600">
              <span>Uploading & parsing...</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-indigo-600 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </Layout>
  )
}
