import { NavLink, useLocation } from "react-router-dom";
import "./info.css";

export default function Info({ title }) {
  const { pathname } = useLocation();
  return (
    <div className="page-shell info-page">
      <div className="empty-page-card">
        <p>{title}</p>
        <p className="stub-path">Rota em desenvolvimento: {pathname}</p>
        <NavLink to="/" className="primary-link">
          Voltar para visão geral
        </NavLink>
      </div>
    </div>
  );
}
