import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'
import './styles/theme.css'

// FIX: BrowserRouter had no basename set, so React Router matched
// routes against the FULL URL path including the /mmc/ subpath prefix
// — e.g. it looked for a route literally named "/mmc/login" instead of
// "/login", found no match, and silently rendered nothing (no error,
// just blank — exactly the reported symptom). import.meta.env.BASE_URL
// is set automatically by Vite from the `base` config value we just
// fixed (e.g. '/mmc/'), so this stays correct for both production
// (served under /mmc/) and local dev (base defaults to '/', so
// basename becomes '/', i.e. no-op) without needing a second separate
// env var or any manual sync between the two configs.
ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter basename={import.meta.env.BASE_URL}>
    <App />
    <Toaster position="top-right" toastOptions={{
      style: { background: '#1E293B', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' },
      success: { iconTheme: { primary: '#10B981', secondary: '#fff' } },
      error:   { iconTheme: { primary: '#EF4444', secondary: '#fff' } },
    }}/>
  </BrowserRouter>
)

// import React from 'react'
// import ReactDOM from 'react-dom/client'
// import { BrowserRouter } from 'react-router-dom'
// import { Toaster } from 'react-hot-toast'
// import App from './App'
// import './index.css'
// import './styles/theme.css'

// ReactDOM.createRoot(document.getElementById('root')).render(
//   <BrowserRouter>
//     <App />
//     <Toaster position="top-right" toastOptions={{
//       style: { background: '#1E293B', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' },
//       success: { iconTheme: { primary: '#10B981', secondary: '#fff' } },
//       error:   { iconTheme: { primary: '#EF4444', secondary: '#fff' } },
//     }}/>
//   </BrowserRouter>
// )
