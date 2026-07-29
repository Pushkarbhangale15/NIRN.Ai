import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

//import { NavLink, Route, Routes } from "react-router-dom";
import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Draft from "./pages/Draft.jsx";
import Chat from "./pages/Chat.jsx";
import { useLanguage } from "./LanguageContext.jsx";
import { DraftProvider } from "./DraftContext.jsx";
import { useEffect } from "react";


function PageWrapper({ children }) {
  const { siteLanguage } = useLanguage();
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.25 }}
      className={siteLanguage === 'mr' ? 'lang-mr' : ''}
    >
      {children}
    </motion.div>
  );
}

function Navbar() {
  const { t, siteLanguage, toggleLanguage } = useLanguage();

  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 100, background: 'color-mix(in srgb, var(--cream) 82%, transparent)', backdropFilter: 'blur(6px)', borderBottom: '1px solid var(--line)' }} className={siteLanguage === 'mr' ? 'lang-mr' : ''}>
      <div className="container">
        <nav className="nav" style={{ borderBottom: 'none', background: 'transparent', backdropFilter: 'none', top: 'auto', position: 'static' }}>
          <NavLink to="/" className="brand">
            <img src={shasan} alt="Government of Maharashtra" className="brand-logo" />
            <span className="brand-marathi">
              <span className="brand-maha">महाराष्ट्र</span>
              <span className="brand-shasan">शासन</span>
            </span>
          </NavLink>

          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_home')}
            </NavLink>
            <NavLink to="/draft" className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_draft')}
            </NavLink>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <button
              onClick={toggleLanguage}
              className="nav-lang-toggle"
            >
              {siteLanguage === 'en' ? 'मराठी' : 'English'}
            </button>
            <NavLink to="/chat" className="nav-cta-primary">
              {t('nav_ai_copilot')}
            </NavLink>
          </div>
        </nav>
      </div>
    </div>
  );
}

function Footer() {
  const { siteLanguage } = useLanguage();
  return (
    <footer className={`footer ${siteLanguage === 'mr' ? 'lang-mr' : ''}`}>
      <div className="container">
        <hr className="footer-divider" />

        <div className="footer-content">
          <div className="footer-left">
            <div className="footer-brand">NIRN.Ai</div>
            <div className="footer-tagline">AI-assisted Government Resolution Search & Drafting Platform</div>
            <div className="footer-section">
              <span className="footer-label">Developed at</span>
              <div className="footer-value">Veermata Jijabai Technological Institute (VJTI), Mumbai</div>
              <div className="footer-value">Master of Computer Applications (MCA)</div>
            </div>
          </div>

          <div className="footer-right">
            <div className="footer-team-title">Project Team (SYMCA)</div>
            <ul className="footer-team-list">
              <li>Pushkar Bhangale</li>
              <li>Kumar Tambe</li>
              <li>Tanmay Shinde</li>
              <li>Prasad Aher</li>
            </ul>
          </div>
        </div>

        <hr className="footer-divider" />

        <div className="footer-bottom">
          <p className="footer-copy">© 2026 NIRN.AI | Developed for the Government of Maharashtra Hackathon</p>
          <p className="footer-disclaimer">
            This project is an academic prototype developed at VJTI for research and
            demonstration purposes. It is not an official Government of Maharashtra service.
          </p>
        </div>
      </div>
    </footer>
  );
}

export default function App() {
  const location = useLocation();
  const { siteLanguage } = useLanguage();

  return (
    <DraftProvider>
      <Navbar />

      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname + siteLanguage}>
          <Route
            path="/"
            element={
              <PageWrapper>
                <Home />
              </PageWrapper>
            }
          />

          <Route
            path="/draft"
            element={
              <PageWrapper>
                <Draft />
              </PageWrapper>
            }
          />

          <Route
            path="/chat"
            element={
              <PageWrapper>
                <Chat />
              </PageWrapper>
            }
          />

          <Route
            path="/copilot"
            element={
              <PageWrapper>
                <Chat />
              </PageWrapper>
            }
          />
        </Routes>
      </AnimatePresence>

      <Footer />
    </DraftProvider>
  );
}
