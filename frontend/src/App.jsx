import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import CandidateProfile from './pages/CandidateProfile'
import UploadPage from './pages/UploadPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/candidates" element={<Dashboard />} />
        <Route path="/candidates/:id" element={<CandidateProfile />} />
      </Routes>
    </BrowserRouter>
  )
}
