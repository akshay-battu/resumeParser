import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteCandidate, generateDocumentRequest, getCandidate, sendDocumentRequest, submitDocuments, updateCandidate } from '../api/client'
import ConfidenceBar from '../components/ConfidenceBar'
import DocumentFileInput from '../components/DocumentFileInput'
import DocumentViewer from '../components/DocumentViewer'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'

const FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'company', label: 'Company' },
  { key: 'designation', label: 'Designation' },
]

export default function CandidateProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [candidate, setCandidate] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState(null)
  const [saveLoading, setSaveLoading] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [generateLoading, setGenerateLoading] = useState(false)
  const [sendLoading, setSendLoading] = useState(false)
  const [requestMessage, setRequestMessage] = useState('')
  const [messageEdited, setMessageEdited] = useState(false)
  const [requestMeta, setRequestMeta] = useState(null)
  const [requestError, setRequestError] = useState('')
  const [panFile, setPanFile] = useState(null)
  const [aadhaarFile, setAadhaarFile] = useState(null)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitProgress, setSubmitProgress] = useState(0)
  const [submitSuccess, setSubmitSuccess] = useState('')

  const load = () => {
    setLoading(true)
    getCandidate(id)
      .then((data) => {
        setCandidate(data)
        const latest = data.document_requests?.[0]
        if (latest?.message && !requestMessage) {
          setRequestMessage(latest.message)
          setRequestMeta(latest)
        }
      })
      .catch((err) => setError(err.response?.data?.error || err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleGenerateMessage = async () => {
    setGenerateLoading(true)
    setRequestError('')
    setRequestMeta(null)
    try {
      const result = await generateDocumentRequest(id)
      setRequestMessage(result.message)
      setMessageEdited(false)
    } catch (err) {
      setRequestError(err.response?.data?.error || err.message)
    } finally {
      setGenerateLoading(false)
    }
  }

  const handleSendMessage = async () => {
    setSendLoading(true)
    setRequestError('')
    try {
      const result = await sendDocumentRequest(id, requestMessage)
      setRequestMeta(result)
    } catch (err) {
      setRequestError(err.response?.data?.error || err.message)
    } finally {
      setSendLoading(false)
    }
  }

  const handleSubmitDocuments = async () => {
    if (!panFile || !aadhaarFile) {
      setError('Please select both PAN and Aadhaar documents.')
      return
    }
    setSubmitLoading(true)
    setSubmitProgress(0)
    setSubmitSuccess('')
    setError('')
    try {
      await submitDocuments(id, panFile, aadhaarFile, setSubmitProgress)
      setSubmitSuccess('Documents submitted successfully.')
      setPanFile(null)
      setAadhaarFile(null)
      load()
    } catch (err) {
      setError(err.response?.data?.error || err.message)
    } finally {
      setSubmitLoading(false)
    }
  }

  const handleDelete = async () => {
    const confirmed = window.confirm(
      `Permanently delete ${candidate?.name || 'this candidate'}? This removes their resume, PAN, Aadhaar, and all request history. This cannot be undone.`,
    )
    if (!confirmed) return

    setDeleteLoading(true)
    setError('')
    try {
      await deleteCandidate(id)
      navigate('/candidates')
    } catch (err) {
      setError(err.response?.data?.error || err.message)
      setDeleteLoading(false)
    }
  }

  const handleStartEdit = () => {
    setSaveError('')
    setEditForm({
      name: candidate.name || '',
      email: candidate.email || '',
      phone: candidate.phone || '',
      company: candidate.company || '',
      designation: candidate.designation || '',
      skillsText: (candidate.skills || []).join(', '),
    })
    setEditMode(true)
  }

  const handleCancelEdit = () => {
    setEditMode(false)
    setEditForm(null)
    setSaveError('')
  }

  const handleSaveEdit = async () => {
    setSaveLoading(true)
    setSaveError('')
    try {
      const newSkills = editForm.skillsText
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const candidates = {
        name: editForm.name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        company: editForm.company.trim(),
        designation: editForm.designation.trim(),
        skills: newSkills,
      }
      // Only send fields that actually changed, so untouched fields keep
      // their original LLM confidence instead of being marked as reviewed.
      const changed = {}
      for (const [key, value] of Object.entries(candidates)) {
        const original = key === 'skills' ? (candidate.skills || []) : candidate[key] || ''
        const isSame = key === 'skills'
          ? JSON.stringify(original) === JSON.stringify(value)
          : original === value
        if (!isSame) changed[key] = value
      }

      if (Object.keys(changed).length === 0) {
        setEditMode(false)
        setEditForm(null)
        return
      }

      const updated = await updateCandidate(id, changed)
      setCandidate(updated)
      setEditMode(false)
      setEditForm(null)
    } catch (err) {
      setSaveError(err.response?.data?.error || err.message)
    } finally {
      setSaveLoading(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <p className="text-slate-500">Loading candidate...</p>
      </Layout>
    )
  }

  if (error && !candidate) {
    return (
      <Layout>
        <p className="text-red-600">{error}</p>
        <Link to="/candidates" className="mt-4 inline-block text-indigo-600">
          Back to dashboard
        </Link>
      </Layout>
    )
  }

  const confidence = candidate?.confidence || {}
  const llmError = confidence.error
  const docs = candidate?.documents || {}
  const hasSubmittedDocs = docs.pan?.available || docs.aadhaar?.available
  const isSubmitted = candidate?.status === 'documents_submitted'
  const canSubmitDocs = candidate?.status === 'parsed' && !hasSubmittedDocs

  return (
    <Layout>
      <Link to="/candidates" className="mb-4 inline-block text-sm text-indigo-600 hover:underline">
        ← Back to dashboard
      </Link>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{candidate.name || 'Unknown Candidate'}</h1>
          <p className="text-slate-600">{candidate.designation || 'Role not extracted'}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={candidate.status} />
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteLoading}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleteLoading ? 'Deleting...' : 'Delete Candidate'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {llmError && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Parse error: {llmError}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Extracted Profile</h2>
            {!editMode && (
              <button
                type="button"
                onClick={handleStartEdit}
                className="text-sm font-medium text-indigo-600 hover:underline"
              >
                Edit
              </button>
            )}
          </div>

          {saveError && (
            <p className="mb-3 text-sm text-red-600">{saveError}</p>
          )}

          {editMode ? (
            <div className="space-y-4">
              {FIELDS.map(({ key, label }) => (
                <div key={key}>
                  <label className="text-xs uppercase tracking-wide text-slate-500">{label}</label>
                  <input
                    type="text"
                    value={editForm[key]}
                    onChange={(e) => setEditForm({ ...editForm, [key]: e.target.value })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
                  />
                </div>
              ))}
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-500">
                  Skills (comma-separated)
                </label>
                <input
                  type="text"
                  value={editForm.skillsText}
                  onChange={(e) => setEditForm({ ...editForm, skillsText: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={saveLoading}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saveLoading ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  disabled={saveLoading}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <dl className="space-y-4">
              {FIELDS.map(({ key, label }) => (
                <div key={key}>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                  <dd className="mt-1 font-medium">{candidate[key] || '—'}</dd>
                  <ConfidenceBar value={confidence[key]} />
                </div>
              ))}
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Skills</dt>
                <dd className="mt-2 flex flex-wrap gap-2">
                  {(candidate.skills || []).length ? (
                    candidate.skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full bg-indigo-50 px-3 py-1 text-xs text-indigo-700"
                      >
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </dd>
                <div className="mt-2">
                  <ConfidenceBar value={confidence.skills} />
                </div>
              </div>
            </dl>
          )}

          {candidate.status === 'failed' && candidate.raw_text_snippet && (
            <div className="mt-6 rounded-lg bg-slate-50 p-4">
              <h3 className="mb-2 text-sm font-medium text-slate-700">Raw text snippet</h3>
              <pre className="whitespace-pre-wrap text-xs text-slate-600">
                {candidate.raw_text_snippet}
              </pre>
            </div>
          )}
        </section>

        <div className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold">Document Request</h2>
            <p className="mb-4 text-sm text-slate-600">
              Generate a personalized message, review or edit it, then send it to the candidate.
            </p>
            <button
              type="button"
              onClick={handleGenerateMessage}
              disabled={generateLoading || candidate.status === 'processing' || candidate.status === 'failed'}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generateLoading ? 'Generating...' : requestMessage ? 'Regenerate Message' : 'Generate Message'}
            </button>
            {requestError && (
              <p className="mt-3 text-sm text-red-600">{requestError}</p>
            )}
            {requestMessage && (
              <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50 p-4">
                <h3 className="mb-2 text-sm font-medium text-indigo-900">
                  Message {messageEdited ? '(edited)' : '(review before sending)'}
                </h3>
                <textarea
                  className="w-full rounded-lg border border-indigo-200 bg-white p-3 text-sm text-indigo-900 focus:border-indigo-400 focus:outline-none"
                  rows={8}
                  value={requestMessage}
                  onChange={(e) => {
                    setRequestMessage(e.target.value)
                    setMessageEdited(true)
                  }}
                />
                <button
                  type="button"
                  onClick={handleSendMessage}
                  disabled={sendLoading || !requestMessage.trim()}
                  className="mt-3 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {sendLoading ? 'Sending...' : 'Send Email'}
                </button>
                {requestMeta && (
                  <p className="mt-3 text-xs text-indigo-700">
                    {requestMeta.send_status === 'sent' && (
                      <>Email sent to {requestMeta.recipient}</>
                    )}
                    {requestMeta.send_status === 'stub' && (
                      <>Logged only — {requestMeta.send_detail || 'SMTP not configured'}</>
                    )}
                    {requestMeta.send_status === 'failed' && (
                      <>Send failed: {requestMeta.send_detail}</>
                    )}
                  </p>
                )}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold">Identity Documents</h2>

            {hasSubmittedDocs && (
              <div className="mb-6 space-y-4">
                <h3 className="text-sm font-medium text-slate-700">Submitted documents</h3>
                <DocumentViewer label="PAN" doc={docs.pan} candidateId={id} />
                <DocumentViewer label="Aadhaar" doc={docs.aadhaar} candidateId={id} />
              </div>
            )}

            {isSubmitted && !hasSubmittedDocs && (
              <p className="rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-800">
                Documents marked as submitted but files are unavailable.
              </p>
            )}

            {canSubmitDocs ? (
              <>
                <p className="mb-4 text-sm text-slate-600">Upload PAN and Aadhaar documents manually.</p>
                <div className="space-y-4">
                  <DocumentFileInput
                    label="PAN Document"
                    accept=".jpg,.jpeg,.png,.pdf"
                    file={panFile}
                    onChange={setPanFile}
                  />
                  <DocumentFileInput
                    label="Aadhaar Document"
                    accept=".jpg,.jpeg,.png,.pdf"
                    file={aadhaarFile}
                    onChange={setAadhaarFile}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSubmitDocuments}
                  disabled={submitLoading}
                  className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitLoading ? 'Submitting...' : 'Submit Documents'}
                </button>
                {submitLoading && (
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full bg-indigo-600 transition-all"
                      style={{ width: `${submitProgress}%` }}
                    />
                  </div>
                )}
                {submitSuccess && (
                  <p className="mt-3 text-sm text-emerald-600">{submitSuccess}</p>
                )}
              </>
            ) : !hasSubmittedDocs ? (
              <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
                Document upload is available after the resume is successfully parsed.
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </Layout>
  )
}
