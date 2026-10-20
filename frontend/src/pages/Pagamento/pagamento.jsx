import { useCallback, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useParams } from "react-router-dom";
import { History, LogOut, ReceiptText, Wallet, Zap } from "lucide-react";

import { DRIVER_STORAGE_KEY } from "../../config";
import { useStoredUser } from "../../hooks/useStoredUser";
import { authUser, fetchPublicCharger, fetchWallet } from "../../services/api";
import { formatCurrency } from "../../utils/formatters";
import "./pagamento.css";

const CHARGER_REFRESH_MS = 5000;

const TABS = [
  { to: "", label: "Recarga", icon: Zap, end: true },
  { to: "carteira", label: "Carteira", icon: Wallet },
  { to: "extrato", label: "Extrato", icon: ReceiptText },
  { to: "historico", label: "Histórico", icon: History },
];

export function BackToStation() {
  const { chargerCode } = useParams();
  return <Navigate to={`/pagamentos/${chargerCode}`} replace />;
}

export default function Pagamento() {
  const { chargerCode } = useParams();
  const [user, setUser] = useStoredUser(DRIVER_STORAGE_KEY);
  const [charger, setCharger] = useState(null);
  const [balance, setBalance] = useState(null);
  const [loadError, setLoadError] = useState("");

  const refreshCharger = useCallback(
    () =>
      fetchPublicCharger(chargerCode, user?.id)
        .then((next) => {
          setCharger(next);
          setLoadError("");
          return next;
        })
        .catch((error) => setLoadError(error.message)),
    [chargerCode, user?.id],
  );

  const userId = user?.id;
  const refreshBalance = useCallback(() => {
    if (!userId) return Promise.resolve();
    return fetchWallet(userId)
      .then((wallet) => setBalance(wallet.balance))
      .catch((error) => {
        if (error.status === 404) setUser(null);
      });
  }, [userId, setUser]);

  useEffect(() => {
    refreshCharger();
    const timer = setInterval(refreshCharger, CHARGER_REFRESH_MS);
    return () => clearInterval(timer);
  }, [refreshCharger]);

  useEffect(() => {
    refreshBalance();
  }, [refreshBalance]);

  if (!charger)
    return (
      <div className="pay-app">
        <div className="pay-loading">
          {loadError || "Carregando estação..."}
        </div>
      </div>
    );

  if (!user)
    return (
      <div className="pay-app">
        <AppHeader charger={charger} />
        <main className="pay-content">
          <StationCard charger={charger} />
          <AuthPanel onAuthenticated={setUser} />
        </main>
      </div>
    );

  return (
    <div className="pay-app">
      <AppHeader charger={charger} user={user} onLogout={() => setUser(null)} />
      <main className="pay-content with-tabs">
        <section className="pay-balance-card">
          <span>Saldo disponível</span>
          <strong>
            {balance === null ? "..." : `R$ ${formatCurrency(balance)}`}
          </strong>
          <small>Olá, {user.name.split(" ")[0]}</small>
        </section>
        <Outlet
          context={{
            charger,
            user,
            balance: balance ?? 0,
            refreshCharger,
            refreshBalance,
          }}
        />
      </main>
      <nav className="pay-tabs" aria-label="Seções do app">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <NavLink
              key={tab.label}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <Icon size={20} aria-hidden="true" />
              <span>{tab.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}

function AppHeader({ charger, user, onLogout }) {
  return (
    <header className="pay-header">
      <div>
        <span className="pay-brand">ChargeGrid</span>
        <span className="pay-station-code">Estação {charger.code}</span>
      </div>
      {user && (
        <button
          type="button"
          className="pay-icon-button"
          onClick={onLogout}
          aria-label="Sair da conta"
        >
          <LogOut size={18} aria-hidden="true" />
        </button>
      )}
    </header>
  );
}

export function StationCard({ charger }) {
  const inUse = charger.status === "charging";
  return (
    <section className="pay-station">
      <span className="page-kicker">Carregador conectado</span>
      <h1>{charger.name}</h1>
      <p>
        {charger.model || "GoodWe HCA G2"} · {charger.power_kw} kW ·{" "}
        <span className={inUse ? "pay-status busy" : "pay-status free"}>
          {inUse ? "Em uso" : "Disponível"}
        </span>
      </p>
    </section>
  );
}

function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState("landing");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function authenticate(event) {
    event.preventDefault();
    setSending(true);
    try {
      const payload = await authUser(mode, form, "cliente");
      if (mode === "register") {
        const logged = await authUser("login", form);
        onAuthenticated(logged);
      } else onAuthenticated(payload);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSending(false);
    }
  }

  if (mode === "landing")
    return (
      <section className="pay-panel pay-auth-choice">
        <h2>Comece sua carga</h2>
        <p>
          Entre na sua conta para pagar a recarga, colocar saldo e acompanhar
          seus gastos.
        </p>
        <button className="public-primary" onClick={() => setMode("login")}>
          Entrar
        </button>
        <button className="public-secondary" onClick={() => setMode("register")}>
          Criar conta
        </button>
      </section>
    );

  const update = (field) => (event) =>
    setForm({ ...form, [field]: event.target.value });

  return (
    <form className="pay-panel pay-form" onSubmit={authenticate}>
      <h2>{mode === "login" ? "Entrar" : "Criar conta"}</h2>
      {mode === "register" && (
        <label>
          Nome
          <input
            required
            autoComplete="name"
            value={form.name}
            onChange={update("name")}
          />
        </label>
      )}
      <label>
        E-mail
        <input
          required
          type="email"
          autoComplete="email"
          inputMode="email"
          value={form.email}
          onChange={update("email")}
        />
      </label>
      <label>
        Senha
        <input
          required
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={form.password}
          onChange={update("password")}
        />
      </label>
      <button className="public-primary" disabled={sending}>
        {sending ? "Aguarde..." : "Continuar"}
      </button>
      <button
        type="button"
        className="public-text-button"
        onClick={() => {
          setMessage("");
          setMode(mode === "login" ? "register" : "login");
        }}
      >
        {mode === "login" ? "Ainda não tenho conta" : "Já tenho conta"}
      </button>
      {message && <p className="public-error">{message}</p>}
    </form>
  );
}
