import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listCandidates, syncInbox } from '../api/client'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'

const STATUSES = ['', 'processing', 'parsed', 'failed', 'documents_submitted']

export default function Dashboard() {
  const [candidates, setCandidates] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncMessage, setSyncMessage] = useState('')

  useEffect(() => {
    setLoading(true)
    listCandidates(statusFilter || undefined)
      .then(setCandidates)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [statusFilter])

  const handleSyncInbox = async () => {
    setSyncLoading(true)
    setSyncMessage('')
    try {
      const result = await syncInbox()
      const attached = result.processed || 0
      setSyncMessage(
        attached > 0
          ? `Auto-attached documents for ${attached} candidate(s).`
          : result.results?.[0]?.detail || 'Inbox sync complete — no new attachments.',
      )
      listCandidates(statusFilter || undefined).then(setCandidates)
    } catch (err) {
      setSyncMessage(err.response?.data?.error || err.message)
    } finally {
      setSyncLoading(false)
    }
  }

  return (
    <Layout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Candidates</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSyncInbox}
            disabled={syncLoading}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {syncLoading ? 'Syncing...' : 'Sync Email Inbox'}
          </button>
          <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s || 'all'} value={s}>
              {s ? s.replace(/_/g, ' ') : 'All statuses'}
            </option>
          ))}
        </select>
        </div>
      </div>

      {syncMessage && (
        <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
          {syncMessage}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : candidates.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No candidates yet.{' '}
                  <Link to="/" className="text-indigo-600 hover:underline">
                    Upload a resume
                  </Link>
                </td>
              </tr>
            ) : (
              candidates.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/candidates/${c.id}`} className="font-medium text-indigo-600 hover:underline">
                      {c.name || '—'}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{c.email || '—'}</td>
                  <td className="px-4 py-3">{c.company || '—'}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {c.created_at ? new Date(c.created_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  )
}
