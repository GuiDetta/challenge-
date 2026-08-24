import {
  BarChart3,
  Bell,
  CircleHelp,
  LayoutDashboard,
  Settings,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import BrandMark from "./BrandMark";

const navigationItems = [
  { label: "Visão Geral", to: "/", icon: LayoutDashboard },
  { label: "Carregadores", to: "/carregadores", icon: ZapIcon },
  { label: "Relatórios", to: "/relatorios", icon: BarChart3 },
  { label: "Configurações", to: "/configuracoes", icon: Settings },
  { label: "Ajuda", to: "/ajuda", icon: CircleHelp },
];

function ZapIcon({ size, strokeWidth }) {
  return (
    <span
      className="nav-zap"
      style={{ width: size, height: size, borderWidth: strokeWidth }}
    />
  );
}

function TopNav({ user = null, onLogout = () => {} }) {
  return (
    <header className="top-nav">
      <BrandMark />
      <nav aria-label="Navegação principal">
        {navigationItems.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={label}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? "is-active" : ""}`}
          >
            <Icon size={15} strokeWidth={2} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      {user && <span className="top-nav-user">{user.name}</span>}
      <button className="icon-button notification-button" type="button" aria-label="Notificações">
        <Bell size={17} />
        <span className="notification-dot" />
      </button>
      <button className="top-nav-logout" type="button" onClick={onLogout}>Sair</button>
    </header>
  );
}

export default TopNav;