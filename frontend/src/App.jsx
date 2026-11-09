import BodyViewer from './BodyViewer'
import './App.css'

// Set to a real session_id once you have one from POST /api/sessions
// (backend/smoke_test.py creates one, or use the upload form directly).
const TEST_SESSION_ID = "6abfc7a3b533768198aad72f"

function App() {
  return (
    <div style={{ width: '100vw', height: '100vh', margin: 0, overflow: 'hidden' }}>
      <BodyViewer sessionId={TEST_SESSION_ID} apiBase="http://localhost:5000" />
    </div>
  )
}

export default App