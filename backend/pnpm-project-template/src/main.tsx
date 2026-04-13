import React from 'react'
import ReactDOM from 'react-dom/client'
import { AuthGate } from './auth/AuthGate'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate>
      <App />
    </AuthGate>
  </React.StrictMode>,
)
