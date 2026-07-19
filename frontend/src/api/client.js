import axios from 'axios'
import { notifyToast } from './toastBridge'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorType = error.response?.data?.error_type
    if (status === 429 || errorType === 'quota_exceeded') {
      notifyToast(
        error.response?.data?.error || 'Gemini API quota exceeded — please try again later.',
        'warning',
      )
    }
    return Promise.reject(error)
  },
)

export async function uploadResume(file, onProgress) {
  const form = new FormData()
  form.append('resume', file)
  const { data } = await api.post('/candidates/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
  return data
}

export async function listCandidates(status) {
  const params = status ? { status } : {}
  const { data } = await api.get('/candidates', { params })
  return data
}

export async function getCandidate(id) {
  const { data } = await api.get(`/candidates/${id}`)
  return data
}

export async function deleteCandidate(id) {
  const { data } = await api.delete(`/candidates/${id}`)
  return data
}

export async function updateCandidate(id, fields) {
  const { data } = await api.patch(`/candidates/${id}`, fields)
  return data
}

export async function generateDocumentRequest(id, channel = 'email') {
  const { data } = await api.post(`/candidates/${id}/generate-document-request`, { channel })
  return data
}

export async function sendDocumentRequest(id, message, channel = 'email') {
  const { data } = await api.post(`/candidates/${id}/request-documents`, { message, channel })
  return data
}

export async function submitDocuments(id, panFile, aadhaarFile, onProgress) {
  const form = new FormData()
  form.append('pan_document', panFile)
  form.append('aadhaar_document', aadhaarFile)
  const { data } = await api.post(`/candidates/${id}/submit-documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
  return data
}

export async function syncInbox() {
  const { data } = await api.post('/candidates/sync-inbox')
  return data
}

export function documentUrl(candidateId, docType) {
  return `/candidates/${candidateId}/documents/${docType}`
}

export default api
