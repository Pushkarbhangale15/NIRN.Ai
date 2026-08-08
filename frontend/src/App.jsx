import { useEffect } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Draft from "./pages/Draft.jsx";
import CheckConflicts from "./pages/CheckConflicts.jsx";
import Login from "./pages/Login.jsx";
import History from "./pages/History.jsx";
import Admin from "./pages/Admin.jsx";
import Approval from "./pages/Approval.jsx";
import { useLanguage } from "./LanguageContext.jsx";
import { useAuth } from "./AuthContext.jsx";
import { DraftProvider } from "./DraftContext.jsx";


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

// Login-required routes (Task 2: generating a draft; saving, history,
// exports, admin). Anonymous visitors are sent to /login with a
// returnTo so they land back where they were, not on the home page.
//
// Redirects fire from a useEffect keyed on the actual auth booleans,
// not by rendering <Navigate> directly. <Navigate>'s own effect has no
// dependency array — it re-fires on every render of the component that
// returns it — and while a guarded page is unmounting under
// AnimatePresence's exit transition (see PageWrapper), framer-motion
// re-renders that subtree many times per second, which was re-invoking
// navigate() dozens of times a second and tripping React's "Maximum
// update depth exceeded" safeguard. Tying the redirect to an effect
// with real dependencies makes it fire once, when the auth state
// actually changes, regardless of how many extra times the component
// re-renders during exit.
function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      navigate("/login", { state: { returnTo: location.pathname }, replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, isAuthenticated]);

  if (loading || !isAuthenticated) return null;
  return children;
}

// A non-admin hitting /admin directly is redirected home — never a
// blank page, never a crash.
function RequireAdmin({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      navigate("/login", { state: { returnTo: location.pathname }, replace: true });
    } else if (!isAdmin) {
      navigate("/", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, isAuthenticated, isAdmin]);

  if (loading || !isAuthenticated || !isAdmin) return null;
  return children;
}

// The Approval tab is only for the Reviewing Officer / Approving
// Authority roles. A Drafting Officer or anonymous visitor hitting
// /approval directly is redirected home — never a blank page.
function RequireReviewerOrAdmin({ children }) {
  const { isAuthenticated, isAdmin, isReviewer, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      navigate("/login", { state: { returnTo: location.pathname }, replace: true });
    } else if (!isAdmin && !isReviewer) {
      navigate("/", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, isAuthenticated, isAdmin, isReviewer]);

  if (loading || !isAuthenticated || (!isAdmin && !isReviewer)) return null;
  return children;
}

function Navbar() {
  const { t, siteLanguage, toggleLanguage } = useLanguage();
  const { officer, isAuthenticated, isAdmin, isReviewer, loading, logout } = useAuth();
  const navigate = useNavigate();

  // The red button is the single auth control now — it never opens
  // chat. Logged out it routes to /login; logged in it signs out and
  // returns home. Rendered only once loading resolves so it never
  // flashes one label and swaps to the other.
  const handleAuthClick = () => {
    if (isAuthenticated) {
      logout();
      navigate("/");
    } else {
      navigate("/login");
    }
  };

  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 100, background: 'color-mix(in srgb, var(--cream) 82%, transparent)', backdropFilter: 'blur(6px)', borderBottom: '1px solid var(--line)' }} className={siteLanguage === 'mr' ? 'lang-mr' : ''}>
      <div className="container">
        <nav className="nav" style={{ borderBottom: 'none', background: 'transparent', backdropFilter: 'none', top: 'auto', position: 'static' }}>
          <NavLink to="/" className="brand nav-cell-left">
            <img src={shasan} alt="Government of Maharashtra" className="brand-logo" />
            <span className="brand-marathi">
              <span className="brand-maha">महाराष्ट्र</span>
              <span className="brand-shasan">शासन</span>
            </span>
          </NavLink>

          <div className="nav-links nav-cell-center">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_home')}
            </NavLink>
            <NavLink to="/draft" className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_draft')}
            </NavLink>
            <NavLink to="/check-conflicts" className={({ isActive }) => (isActive ? "active" : "")}>
              {t('nav_check_conflicts')}
            </NavLink>
            {/* Rendered only once the role is known, so nothing flashes
                into view and then disappears once auth resolves. */}
            {!loading && isAuthenticated && (
              <NavLink to="/history" className={({ isActive }) => (isActive ? "active" : "")}>
                {t('nav_history')}
              </NavLink>
            )}
            {/* Approval tab: Reviewing Officer / Approving Authority only —
                hidden for Drafting Officer and anonymous visitors. */}
            {!loading && (isReviewer || isAdmin) && (
              <NavLink to="/approval" className={({ isActive }) => (isActive ? "active" : "")}>
                {t('nav_approval')}
              </NavLink>
            )}
            {!loading && isAdmin && (
              <NavLink to="/admin" className={({ isActive }) => `nav-admin-link ${isActive ? "active" : ""}`}>
                {t('nav_admin')}
              </NavLink>
            )}
          </div>

          <div className="nav-cell-right">
            <button
              onClick={toggleLanguage}
              className="nav-lang-toggle"
            >
              {siteLanguage === 'en' ? 'मराठी' : 'English'}
            </button>
            {!loading && (
              <button
                onClick={handleAuthClick}
                className="nav-cta-primary"
                title={isAuthenticated ? officer?.name : undefined}
              >
                {isAuthenticated ? t('nav_logout') : t('nav_login')}
              </button>
            )}
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

  // The login screen is full-viewport and self-contained — no site
  // nav, no footer.
  const isBareRoute = location.pathname === "/login";

  return (
    <DraftProvider>
      {!isBareRoute && <Navbar />}

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

          <Route path="/login" element={<Login />} />

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
            path="/check-conflicts"
            element={
              <PageWrapper>
                <RequireAuth>
                  <CheckConflicts />
                </RequireAuth>
              </PageWrapper>
            }
          />

          {/* Legacy paths from before the "Upload GR" -> "Check Conflicts"
              rename — kept working via redirect rather than breaking
              anyone's bookmark or in-flight link. */}
          <Route path="/upload-gr" element={<Navigate to="/check-conflicts" replace />} />
          <Route path="/upload" element={<Navigate to="/check-conflicts" replace />} />

          <Route
            path="/history"
            element={
              <PageWrapper>
                <RequireAuth>
                  <History />
                </RequireAuth>
              </PageWrapper>
            }
          />

          <Route
            path="/approval"
            element={
              <PageWrapper>
                <RequireReviewerOrAdmin>
                  <Approval />
                </RequireReviewerOrAdmin>
              </PageWrapper>
            }
          />

          <Route
            path="/admin"
            element={
              <PageWrapper>
                <RequireAdmin>
                  <Admin />
                </RequireAdmin>
              </PageWrapper>
            }
          />

        </Routes>
      </AnimatePresence>

      {!isBareRoute && <Footer />}
    </DraftProvider>
  );
}
