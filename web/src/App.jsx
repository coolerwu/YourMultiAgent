import { BrowserRouter, Route, Routes } from 'react-router-dom'
import LoginGate from './components/LoginGate'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <LoginGate>
      <BrowserRouter>
        <Routes>
          <Route path="/*" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </LoginGate>
  )
}
