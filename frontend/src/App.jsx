import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import CandidateProfile from './pages/CandidateProfile'
import UploadPage from './pages/UploadPage'
import { ToastProvider } from './context/ToastContext'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/candidates" element={<Dashboard />} />
          <Route path="/candidates/:id" element={<CandidateProfile />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
