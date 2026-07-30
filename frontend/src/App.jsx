import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

//import { NavLink, Route, Routes } from "react-router-dom";
import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Draft from "./pages/Draft.jsx";
import Chat from "./pages/Chat.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Admin from "./pages/Admin.jsx";
import ChatWidget from "./components/ChatWidget.jsx";
import { useLanguage } from "./LanguageContext.jsx";
import { useAuth } from "./AuthContext.jsx";
import { useEffect, useState } from "react";

// Gate for pages that need a signed-in officer (e.g. drafting a GR).
// Browsing/search stays open to anyone — only shown when a logged-out
// visitor actually tries to reach a protected page.
function RequireAuth({ children }) {
  const { officer } = useAuth();

  if (!officer) {
    return (
      <main className="container" style={{ maxWidth: 560, marginTop: 80, marginBottom: 80 }}>
        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Sign in required</span>
          </div>
          <div className="panel-body" style={{ textAlign: "center" }}>
            <p style={{ marginBottom: 20 }}>
              Drafting a Government Resolution requires an officer account.
              Sign in or register to continue — searching and browsing GRs
              stays free for everyone.
            </p>
            <div className="btn-row" style={{ justifyContent: "center", gap: 12 }}>
              <Link to="/login" className="btn btn-primary">Sign in</Link>
              <Link to="/register" className="btn btn-secondary">Register</Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return children;
}

const IconMenu = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" fill="currentColor" viewBox="0 0 24 24">
    <path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z" />
  </svg>
);
const IconClose = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
    <path d="M18.3 5.71 12 12.01l-6.3-6.3-1.4 1.41 6.29 6.3-6.3 6.29 1.41 1.41 6.3-6.3 6.29 6.3 1.41-1.41-6.3-6.29 6.3-6.3z" />
  </svg>
);


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
  const { officer, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const isAdmin = officer?.role === "admin";

  return (
    <nav className={`nav ${siteLanguage === 'mr' ? 'lang-mr' : ''}`}>
      <div className="container nav-inner">
        <NavLink to="/" className="brand">
          <img src={shasan} alt="Government of Maharashtra" className="brand-logo" />
          <span className="brand-marathi">
            <span className="brand-maha">महाराष्ट्र</span>
            <span className="brand-shasan">शासन</span>
          </span>
        </NavLink>

        <div className="nav-links nav-links-desktop">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            {t('nav_home')}
          </NavLink>
          <NavLink to="/draft" className={({ isActive }) => (isActive ? "active" : "")}>
            {t('nav_draft')}
          </NavLink>
          {isAdmin && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_admin')}
            </NavLink>
          )}
        </div>

        <div className="nav-actions-desktop">
          <button
            onClick={toggleLanguage}
            className="nav-lang-toggle"
          >
            {siteLanguage === 'en' ? 'मराठी' : 'English'}
          </button>
          {officer ? (
            <button
              type="button"
              onClick={logout}
              className="nav-lang-toggle"
              title={`Signed in as ${officer.name}`}
            >
              Sign out
            </button>
          ) : (
            <NavLink to="/login" className="nav-cta-primary">
              Login / Register
            </NavLink>
          )}
        </div>

        <button
          type="button"
          className="nav-hamburger"
          onClick={() => setMobileOpen((prev) => !prev)}
          aria-label={mobileOpen ? t('nav_close_menu') : t('nav_open_menu')}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <IconClose /> : <IconMenu />}
        </button>
      </div>

      {mobileOpen && (
        <div className="container">
          <div className="nav-mobile-panel">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-mobile-link active" : "nav-mobile-link")}>
              {t('nav_home')}
            </NavLink>
            <NavLink to="/draft" className={({ isActive }) => (isActive ? "nav-mobile-link active" : "nav-mobile-link")}>
              {t('nav_draft')}
            </NavLink>
            {isAdmin && (
              <NavLink to="/admin" className={({ isActive }) => (isActive ? "nav-mobile-link active" : "nav-mobile-link")}>
                {t('nav_admin')}
              </NavLink>
            )}
            {officer ? (
              <button
                type="button"
                onClick={logout}
                className="nav-mobile-link"
                style={{ background: "none", border: "none", textAlign: "left", cursor: "pointer" }}
              >
                Sign out
              </button>
            ) : (
              <NavLink to="/login" className="nav-mobile-link nav-mobile-link--cta">
                Login / Register
              </NavLink>
            )}
            <button onClick={toggleLanguage} className="nav-lang-toggle nav-mobile-lang">
              {siteLanguage === 'en' ? 'मराठी' : 'English'}
            </button>
          </div>
        </div>
      )}
    </nav>
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
          <p className="footer-copy">© 2026 NIRN.Ai | Developed for the Government of Maharashtra Hackathon</p>
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
  const { loading } = useAuth();

  if (loading) {
    return (
      <main className="container" style={{ marginTop: 120, textAlign: "center" }}>
        Loading…
      </main>
    );
  }

  return (
    <>
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
                <RequireAuth>
                  <Draft />
                </RequireAuth>
              </PageWrapper>
            }
          />

          <Route
            path="/login"
            element={
              <PageWrapper>
                <Login />
              </PageWrapper>
            }
          />

          <Route
            path="/register"
            element={
              <PageWrapper>
                <Register />
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

          <Route
            path="/admin"
            element={
              <PageWrapper>
                <Admin />
              </PageWrapper>
            }
          />
        </Routes>
      </AnimatePresence>

      <Footer />
      <ChatWidget />
    </>
  );
}
