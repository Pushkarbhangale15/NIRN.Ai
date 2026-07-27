import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

//import { NavLink, Route, Routes } from "react-router-dom";
import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Analyze from "./pages/Analyze.jsx";
import Search from "./pages/Search.jsx";
import Copilot from "./pages/Copilot.jsx";
import { useLanguage } from "./LanguageContext.jsx";
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
    <div className={`container ${siteLanguage === 'mr' ? 'lang-mr' : ''}`}>
      <nav className="nav">
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
          <NavLink to="/search" className={({ isActive }) => (isActive ? "active" : "")}>
            {t('nav_search')}
          </NavLink>
          <NavLink to="/analyze" className={({ isActive }) => (isActive ? "active" : "")}>
            {t('nav_analyze')}
          </NavLink>
          <NavLink to="/copilot" className={({ isActive }) => (isActive ? "active" : "")}>
            {t('nav_copilot')}
          </NavLink>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={toggleLanguage}
            className="btn btn-ghost"
            style={{ padding: '6px 12px', fontSize: '14px', borderRadius: '20px' }}
          >
            {siteLanguage === 'en' ? 'मराठी' : 'English'}
          </button>
        </div>
      </nav>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  const { siteLanguage } = useLanguage();

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
            path="/search"
            element={
              <PageWrapper>
                <Search />
              </PageWrapper>
            }
          />

          <Route
            path="/analyze"
            element={
              <PageWrapper>
                <Analyze />
              </PageWrapper>
            }
          />

          <Route
            path="/copilot"
            element={
              <PageWrapper>
                <Copilot />
              </PageWrapper>
            }
          />
        </Routes>
      </AnimatePresence>
    </>
  );
}
