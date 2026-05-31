import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import ActivityLog from './pages/ActivityLog'
import SupervisorBot from './pages/SupervisorBot'
import StudyCompanion from './pages/StudyCompanion'
import ConfidenceBot from './pages/ConfidenceBot'
import Mirror from './pages/Mirror'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="dashboard">
        <nav className="sidebar">
          <div className="sidebar__title">
            <span>PhD-Live</span>
            <span className="sidebar__sub">learning dashboard</span>
          </div>
          <NavLink to="/" end className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}>
            Activity Log
          </NavLink>
          <NavLink to="/supervisor" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}>
            Supervisor Bot
          </NavLink>
          <NavLink to="/companion" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}>
            Study Companion
          </NavLink>
          <NavLink to="/confidence" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}>
            Confidence Bot
          </NavLink>
          <NavLink to="/mirror" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}>
            Mirror
          </NavLink>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<ActivityLog />} />
            <Route path="/supervisor" element={<SupervisorBot />} />
            <Route path="/companion" element={<StudyCompanion />} />
            <Route path="/confidence" element={<ConfidenceBot />} />
            <Route path="/mirror" element={<Mirror />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}