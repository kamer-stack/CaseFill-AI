import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { CaseProvider } from './context/CaseContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CaseProvider>
      <App />
    </CaseProvider>
  </StrictMode>,
)
