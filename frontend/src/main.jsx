import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'
import './styles/theme.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
    <Toaster position="top-right" toastOptions={{
      style: { background: '#1E293B', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' },
      success: { iconTheme: { primary: '#10B981', secondary: '#fff' } },
      error:   { iconTheme: { primary: '#EF4444', secondary: '#fff' } },
    }}/>
  </BrowserRouter>
)
