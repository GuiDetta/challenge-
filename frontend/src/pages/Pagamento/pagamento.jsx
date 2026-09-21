import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { MOCK_VEHICLE_BATTERY_KWH } from "../../config";
import {
  authUser,
  createChargingOrder,
  fetchPublicCharger,
  finishChargingOrder,
  topUpWallet,
} from "../../services/api";
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import "./pagamento.css";

export default function Pagamento() {
  const { chargerCode } = useParams();
  const [charger, setCharger] = useState(null);
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState("landing");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [target, setTarget] = useState(20);
  const [balance, setBalance] = useState(0);
  const [message, setMessage] = useState("");
  const [order, setOrder] = useState(null);

  useEffect(() => {
    fetchPublicCharger(chargerCode, user?.id)
      .then(setCharger)
      .catch((error) => setMessage(error.message));
  }, [chargerCode, user?.id]);
  const energy = (target / 100) * MOCK_VEHICLE_BATTERY_KWH;
  const price =
    new Date().getHours() >= 18 && new Date().getHours() < 22 ? 2.79 : 1.99;
  const duration = Math.max(
    1,
    Math.round((energy / Number(charger?.power_kw || 7)) * 60),
  );

  async function authenticate(event) {
    event.preventDefault();
    try {
      const payload = await authUser(mode, form);
      if (mode === "register") {
        setMode("login");
        setMessage("Cadastro realizado. Faça login para continuar.");
      } else {
        setUser(payload);
        setBalance(Number(payload.wallet_balance || 0));
        setMode("booking");
      }
    } catch (error) {
      setMessage(error.message);
    }
  }
  async function startCharge(event) {
    event.preventDefault();
    try {
      const created = await createChargingOrder({
        user_id: user.id,
        charger_code: charger.code,
        energy_kwh: energy,
        payment_method: "wallet",
      });
      setOrder(created);
      setBalance((value) => value - Number(created.total_amount || 0));
      setMessage("Recarga iniciada.");
    } catch (error) {
      setMessage(error.message);
    }
  }
  async function addCredit() {
    await topUpWallet(user.id, 25);
    setBalance((value) => value + 25);
  }
  async function finishCharge() {
    const result = await finishChargingOrder(order.id, {
      user_id: user.id,
      energy_delivered_kwh: energy / 2,
    });
    setBalance(result.wallet_balance);
    setOrder(null);
    setMessage(
      `Recarga encerrada. ${formatCurrency(result.refund_amount)} devolvidos.`,
    );
  }

  if (!charger)
    return (
      <div className="chargegrid-page">
        <div className="public-panel">
          <p>{message || "Carregando estação..."}</p>
        </div>
      </div>
    );
  return (
    <div className="chargegrid-page">
      <header className="public-header">
        <span className="public-brand">ChargeGrid</span>
        <span>Estação {charger.code}</span>
      </header>
      <main
        className={`public-content ${mode === "booking" ? "booking-view-plan" : ""}`}
      >
        <section className="station-hero">
          <span className="page-kicker">Carregador conectado</span>
          <h1>{charger.name}</h1>
          <p>
            {charger.model || "GoodWe HCA G2"} · {charger.power_kw} kW ·{" "}
            {charger.status === "charging" ? "Em uso" : "Disponível"}
          </p>
        </section>
        {mode === "landing" && (
          <section className="public-panel auth-choice">
            <h2>Comece sua carga</h2>
            <button className="public-primary" onClick={() => setMode("login")}>
              Login
            </button>
            <button
              className="public-secondary"
              onClick={() => setMode("register")}
            >
              Cadastrar
            </button>
          </section>
        )}
        {["login", "register"].includes(mode) && (
          <form className="public-panel public-form" onSubmit={authenticate}>
            <h2>{mode === "login" ? "Entrar" : "Criar conta"}</h2>
            {mode === "register" && (
              <label>
                Nome
                <input
                  required
                  value={form.name}
                  onChange={(event) =>
                    setForm({ ...form, name: event.target.value })
                  }
                />
              </label>
            )}
            <label>
              E-mail
              <input
                required
                type="email"
                value={form.email}
                onChange={(event) =>
                  setForm({ ...form, email: event.target.value })
                }
              />
            </label>
            <label>
              Senha
              <input
                required
                type="password"
                value={form.password}
                onChange={(event) =>
                  setForm({ ...form, password: event.target.value })
                }
              />
            </label>
            <button className="public-primary">Continuar</button>
            {message && <p className="public-error">{message}</p>}
          </form>
        )}
        {mode === "booking" && (
          <section className="public-panel public-form">
            <div className="booking-account-panel">
              <strong>{user.name}</strong>
              <span>R$ {balance.toFixed(2).replace(".", ",")}</span>
              <button type="button" onClick={addCredit}>
                Adicionar R$ 25
              </button>
            </div>
            {order ? (
              <>
                <h2>Recarga em andamento</h2>
                <p>
                  Iniciada em {formatDateTime(order.created_at || new Date())}
                </p>
                <button
                  type="button"
                  className="public-primary"
                  onClick={finishCharge}
                >
                  Encerrar recarga
                </button>
              </>
            ) : (
              <form onSubmit={startCharge}>
                <h2>Planejar carregamento</h2>
                <label>
                  Carga alvo
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={target}
                    onChange={(event) => setTarget(Number(event.target.value))}
                  />
                  %
                </label>
                <p>
                  {energy.toFixed(1)} kWh · {duration} min · R${" "}
                  {formatCurrency(energy * price)}
                </p>
                <button className="public-primary">Iniciar com carteira</button>
              </form>
            )}
            {message && <p className="public-success">{message}</p>}
          </section>
        )}
      </main>
    </div>
  );
}
