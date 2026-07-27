import { NavLink, Route, Routes } from "react-router-dom";
import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Analyze from "./pages/Analyze.jsx";
import Search from "./pages/Search.jsx";
import Copilot from "./pages/Copilot.jsx";
import { useLanguage } from "./LanguageContext.jsx";
import { useEffect } from "react";

function Navbar() {
  const { t, siteLanguage, toggleLanguage } = useLanguage();

  return (
    <div className="container">
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
          <NavLink to="/copilot" className="nav-cta">
            {t('nav_ai_copilot')}
          </NavLink>
        </div>
      </nav>
    </div>
  );
}

export default function App() {
  const { siteLanguage } = useLanguage();

  useEffect(() => {
    if (siteLanguage === 'mr') {
      document.body.classList.add('lang-mr');
    } else {
      document.body.classList.remove('lang-mr');
    }
  }, [siteLanguage]);

  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/search" element={<Search />} />
        <Route path="/copilot" element={<Copilot />} />
      </Routes>
    </>
  );
}
