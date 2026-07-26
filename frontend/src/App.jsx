import { NavLink, Route, Routes } from "react-router-dom";
import shasan from "./assets/shasan.svg";
import Home from "./pages/Home.jsx";
import Analyze from "./pages/Analyze.jsx";
import Search from "./pages/Search.jsx";
import Copilot from "./pages/Copilot.jsx";

function Navbar() {
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
            Home
          </NavLink>
          <NavLink to="/search" className={({ isActive }) => (isActive ? "active" : "")}>
            Search
          </NavLink>
          <NavLink to="/analyze" className={({ isActive }) => (isActive ? "active" : "")}>
            Analyze
          </NavLink>
          <NavLink to="/copilot" className={({ isActive }) => (isActive ? "active" : "")}>
            Copilot
          </NavLink>
        </div>

        <NavLink to="/copilot" className="nav-cta">
          AI Copilot <span>→</span>
        </NavLink>
      </nav>
    </div>
  );
}

export default function App() {
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
