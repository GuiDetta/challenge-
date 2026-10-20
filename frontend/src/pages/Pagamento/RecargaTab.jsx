import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { MOCK_VEHICLE_BATTERY_KWH } from "../../config";
import {
  createChargingOrder,
  fetchTariff,
  finishChargingOrder,
} from "../../services/api";
import {
  formatCurrency,
  formatDateTime,
  getLiveSession,
} from "../../utils/formatters";
import { StationCard } from "./pagamento";

const TARGET_SHORTCUTS = [20, 50, 80, 100];

export default function RecargaTab() {
  const { charger, user, balance, refreshCharger, refreshBalance } =
    useOutletContext();
  const [tariff, setTariff] = useState(null);
  const [target, setTarget] = useState(50);
  const [message, setMessage] = useState(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchTariff()
      .then(setTariff)
      .catch((error) => setMessage({ type: "error", text: error.message }));
  }, []);

  const energy = (target / 100) * MOCK_VEHICLE_BATTERY_KWH;
  const total = tariff ? energy * tariff.price_per_kwh : null;
  const duration = Math.max(
    1,
    Math.round((energy / Number(charger.power_kw || 7)) * 60),
  );
  const missing = total !== null ? total - balance : 0;
  const busyByOther = charger.status === "charging" && !charger.active_order_id;

  async function startCharge(event) {
    event.preventDefault();
    setSending(true);
    setMessage(null);
    try {
      await createChargingOrder({
        user_id: user.id,
        charger_code: charger.code,
        energy_kwh: energy,
        payment_method: "wallet",
      });
      await Promise.all([refreshCharger(), refreshBalance()]);
      setMessage({ type: "success", text: "Pagamento aprovado. Recarga iniciada." });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <StationCard charger={charger} />
      {charger.active_order_id ? (
        <ActiveCharge
          charger={charger}
          user={user}
          onFinished={async (text) => {
            await Promise.all([refreshCharger(), refreshBalance()]);
            setMessage({ type: "success", text });
          }}
          onError={(text) => setMessage({ type: "error", text })}
        />
      ) : (
        <form className="pay-panel pay-form" onSubmit={startCharge}>
          <h2>Planejar recarga</h2>
          {tariff && (
            <p className={tariff.is_peak ? "pay-tariff peak" : "pay-tariff"}>
              R$ {formatCurrency(tariff.price_per_kwh)}/kWh agora
              {tariff.is_peak
                ? ` · horário de pico (${tariff.peak_window})`
                : ` · pico das ${tariff.peak_window} custa R$ ${formatCurrency(tariff.peak_price_per_kwh)}`}
            </p>
          )}
          <div className="pay-chips" role="group" aria-label="Carga alvo">
            {TARGET_SHORTCUTS.map((value) => (
              <button
                key={value}
                type="button"
                className={target === value ? "selected" : ""}
                onClick={() => setTarget(value)}
              >
                {value}%
              </button>
            ))}
          </div>
          <label>
            Ou digite a carga alvo (%)
            <input
              type="number"
              inputMode="numeric"
              min="1"
              max="100"
              required
              value={target}
              onChange={(event) => setTarget(Number(event.target.value))}
            />
          </label>
          <dl className="pay-summary">
            <div>
              <dt>Energia</dt>
              <dd>{energy.toFixed(1).replace(".", ",")} kWh</dd>
            </div>
            <div>
              <dt>Tempo estimado</dt>
              <dd>{duration} min</dd>
            </div>
            <div className="total">
              <dt>Total</dt>
              <dd>{total === null ? "..." : `R$ ${formatCurrency(total)}`}</dd>
            </div>
          </dl>
          {missing > 0 && (
            <p className="pay-warning">
              Faltam R$ {formatCurrency(missing)} de saldo.{" "}
              <Link to="carteira">Adicionar saldo</Link>
            </p>
          )}
          <button
            className="public-primary"
            disabled={sending || !tariff || missing > 0 || busyByOther}
          >
            {busyByOther
              ? "Carregador em uso"
              : sending
                ? "Processando..."
                : "Pagar com saldo e iniciar"}
          </button>
          <small className="pay-hint">
            Se a recarga terminar antes, a energia não usada volta para o seu
            saldo.
          </small>
        </form>
      )}
      {message && (
        <p className={message.type === "error" ? "public-error" : "public-success"}>
          {message.text}
        </p>
      )}
    </>
  );
}

function ActiveCharge({ charger, user, onFinished, onError }) {
  const [now, setNow] = useState(() => Date.now());
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const session = getLiveSession(charger, now);
  const contracted = Number(charger.active_session_energy_kwh || 0);
  const totalSeconds = Number(charger.active_session_duration_minutes || 0) * 60;
  const elapsedShare = session
    ? 1 - session.remainingSeconds / totalSeconds
    : 1;
  const delivered = contracted * elapsedShare;
  const minutesLeft = session ? Math.ceil(session.remainingSeconds / 60) : 0;

  async function finish() {
    setSending(true);
    try {
      const result = await finishChargingOrder(charger.active_order_id, {
        user_id: user.id,
        energy_delivered_kwh: Number(delivered.toFixed(3)),
      });
      await onFinished(
        result.refund_amount > 0
          ? `Recarga encerrada. R$ ${formatCurrency(result.refund_amount)} voltaram para o saldo.`
          : "Recarga encerrada.",
      );
    } catch (error) {
      onError(error.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="pay-panel pay-form">
      <h2>Recarga em andamento</h2>
      <div
        className="pay-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={session?.progressPercent ?? 100}
      >
        <span style={{ width: `${session?.progressPercent ?? 100}%` }} />
      </div>
      <dl className="pay-summary">
        <div>
          <dt>Entregue</dt>
          <dd>
            {delivered.toFixed(2).replace(".", ",")} de{" "}
            {contracted.toFixed(1).replace(".", ",")} kWh
          </dd>
        </div>
        <div>
          <dt>Tempo restante</dt>
          <dd>{minutesLeft} min</dd>
        </div>
        <div>
          <dt>Início</dt>
          <dd>{formatDateTime(charger.active_session_started_at)}</dd>
        </div>
      </dl>
      <button
        type="button"
        className="public-primary"
        onClick={finish}
        disabled={sending}
      >
        {sending ? "Encerrando..." : "Encerrar recarga"}
      </button>
    </section>
  );
}
