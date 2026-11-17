import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { LazyMotion, MotionConfig, domAnimation } from 'framer-motion'
import App from './App'
import { AuthProvider } from './lib/auth'
// Fonts bundled with the app (the lab network has no internet): only the weights used.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* Framer animations follow the operating system's reduced-motion
        setting, as the CSS ones already do. */}
    {/* 2026-11-17 optimisation: lean framer-motion (m components + domAnimation only; no layout/drag features are used) */}
    <LazyMotion features={domAnimation} strict>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </MotionConfig>
    </LazyMotion>
  </React.StrictMode>,
)
