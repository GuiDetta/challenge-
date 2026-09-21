import { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import { Link } from "react-router-dom";

import {
  deleteCharger,
  fetchOwnedChargers,
  updateCharger,
} from "../../services/api";
import {
  formatDateTime,
  getLiveSession,
  getStatusLabel,
} from "../../utils/formatters";
import "./carregadores.css";

export default function Carregadores({ rooms = [], ownerId }) {
  const [chargers, setChargers] = useState([]);
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  useEffect(() => {
    fetchOwnedChargers(ownerId)
      .then(setChargers)
      .catch(() => {});
  }, [ownerId]);
  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const realChargers = useMemo(
    () =>
      chargers
        .filter((charger) => charger.kind === "real")
        .sort((a, b) => a.name.localeCompare(b.name)),
    [chargers],
  );
  async function deactivate(charger, code) {
    await deleteCharger(charger.plan_id, charger.id, code, ownerId);
    setChargers((items) => items.filter((item) => item.id !== charger.id));
  }

  return (
    <div className="page-shell chargers-page">
      <header className="page-header">
        <div>
          <span className="page-kicker">Carregadores</span>
          <h1>Operação e cobrança</h1>
        </div>
        <Link to="/" className="secondary-link">
          Voltar ao mapa
        </Link>
      </header>
      {realChargers.length === 0 ? (
        <div className="empty-page-card">
          <p>Nenhum carregador real cadastrado ainda.</p>
          <Link to="/" className="primary-link">
            Adicionar HC2 no mapa
          </Link>
        </div>
      ) : (
        <section className="charger-section">
          <div className="section-title-row">
            <h2>Aparelhos instalados</h2>
            <span>{realChargers.length}</span>
          </div>
          <div
            className={`charger-grid ${realChargers.length > 4 ? "has-many" : ""}`}
          >
            {realChargers.map((charger) => (
              <ChargerCard
                key={charger.id}
                charger={charger}
                roomName={
                  rooms.find((room) => room.id === charger.room_id)?.name ||
                  "Mapa geral"
                }
                currentTime={currentTime}
                onDeactivate={deactivate}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ChargerCard({ charger, roomName, currentTime, onDeactivate }) {
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(charger.name);
  const [nameError, setNameError] = useState("");
  const [deactivationOpen, setDeactivationOpen] = useState(false);
  const [deactivationCode, setDeactivationCode] = useState("");
  const [deactivationError, setDeactivationError] = useState("");
  const [deactivating, setDeactivating] = useState(false);
  const [qrSource, setQrSource] = useState("");
  const liveSession = getLiveSession(charger, currentTime);
  const statusText = getStatusLabel(charger.telemetry?.status);
  const isStandby = !liveSession;

  useEffect(() => {
    QRCode.toDataURL(`${window.location.origin}/pagamentos/${charger.code}`, {
      errorCorrectionLevel: "M",
      margin: 1,
      width: 92,
    })
      .then(setQrSource)
      .catch(() => {});
  }, [charger.code]);
  async function saveName() {
    const nextName = name.trim();
    if (!nextName || nextName === charger.name) return setEditingName(false);
    try {
      await updateCharger(charger.plan_id, charger.id, { name: nextName });
      setName(nextName);
      setNameError("");
      setEditingName(false);
    } catch (error) {
      setNameError(error.message);
    }
  }
  async function confirmDeactivation() {
    setDeactivating(true);
    setDeactivationError("");
    try {
      await onDeactivate(charger, deactivationCode.trim());
      setDeactivationOpen(false);
    } catch (error) {
      setDeactivationError(error.message);
    } finally {
      setDeactivating(false);
    }
  }
  function downloadQr() {
    if (!qrSource) return;
    const link = document.createElement("a");
    link.href = qrSource;
    link.download = `qrcode-${charger.code || "HC2-0000"}.png`;
    link.click();
  }

  return (
    <article className="charger-card">
      <div className="charger-card-header">
        <div className="charger-card-heading">
          <div className="charger-card-topline">
            <span
              className={`card-badge ${charger.kind === "real" ? "is-real" : "is-simulated"}`}
            >
              {statusText}
            </span>
            <span className="device-code-badge">
              {charger.code || "HC2-0000"}
            </span>
          </div>
          {editingName ? (
            <div className="charger-name-editor">
              <input
                value={name}
                autoFocus
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") saveName();
                  if (event.key === "Escape") setEditingName(false);
                }}
              />
              <button type="button" onClick={saveName}>
                OK
              </button>
            </div>
          ) : (
            <div className="charger-name-line">
              <h2>{name}</h2>
              <button
                type="button"
                className="edit-name-button"
                onClick={() => setEditingName(true)}
                aria-label={`Editar nome de ${name}`}
              >
                ✎
              </button>
            </div>
          )}
          {nameError && <small className="name-edit-error">{nameError}</small>}
        </div>
        <div className="charger-card-actions">
          <span className="charger-room">{roomName}</span>
          <button
            type="button"
            className="deactivate-charger-button"
            onClick={() => {
              setDeactivationCode("");
              setDeactivationError("");
              setDeactivationOpen(true);
            }}
          >
            {"Desativar"}
          </button>
        </div>
      </div>
      <div className="charger-identity-row">
        <div className="charger-qr-row">
          {qrSource ? (
            <img src={qrSource} alt={`QR Code do carregador ${charger.code}`} />
          ) : (
            <span className="qr-placeholder" aria-hidden="true" />
          )}
          <div>
            <span>QR permanente</span>
            <strong>/pagamentos/{charger.code}</strong>
            <button
              type="button"
              className="download-qr-button"
              onClick={downloadQr}
              disabled={!qrSource}
            >
              Baixar QR Code para impressão
            </button>
          </div>
        </div>
      </div>
      <p className="charger-model">{charger.model || "GoodWe HCA G2"}</p>
      <div className={`charger-session-slot ${isStandby ? "is-standby" : ""}`}>
        {isStandby ? (
          <div className="standby-empty-state">
            <span>Sem sessão em andamento</span>
          </div>
        ) : (
          <>
            <div className="charge-meta">
              <span>Carga atual</span>
              <strong>{liveSession.progressPercent}%</strong>
            </div>
            <div
              className="charge-bar"
              aria-label={`Carga atual do carregador ${name}`}
            >
              <span
                className="charge-fill"
                style={{ width: `${liveSession.progressPercent}%` }}
              />
            </div>
            <div className="time-grid">
              <div className="time-stat">
                <span>Início</span>
                <strong>{formatDateTime(liveSession.startedAt)}</strong>
              </div>
              <div className="time-stat">
                <span>Previsão</span>
                <strong>{formatRemaining(liveSession.remainingSeconds)}</strong>
              </div>
            </div>
            <div className="meta-card">
              <span>Final previsto</span>
              <strong>{formatDateTime(liveSession.endsAt)}</strong>
            </div>
          </>
        )}
      </div>
      <div className="charger-info-row">
        <span>Potência</span>
        <strong>
          {charger.power_kw ?? charger.telemetry?.power_kw ?? 7} kW
        </strong>
      </div>
      <div className="charger-info-row">
        <span>Estado</span>
        <strong>{statusText}</strong>
      </div>
      <Link
        className="manage-payment-button"
        to={`/pagamentos/${charger.code}`}
      >
        Gerenciar pagamento
      </Link>
      {deactivationOpen && (
        <div
          className="delete-confirm-backdrop"
          onClick={() => setDeactivationOpen(false)}
        >
          <div
            className="delete-confirm-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="delete-confirm-close"
              onClick={() => setDeactivationOpen(false)}
            >
              ×
            </button>
            <h3>Deseja desativar?</h3>
            <p>
              Este aparelho continuará disponível para consulta depois de ser
              desativado.
            </p>
            <div className="delete-code-field">
              <label htmlFor={`code-${charger.id}`}>Código do carregador</label>
              <input
                id={`code-${charger.id}`}
                value={deactivationCode}
                autoFocus
                onChange={(event) =>
                  setDeactivationCode(event.target.value.toUpperCase())
                }
                onKeyDown={(event) =>
                  event.key === "Enter" && confirmDeactivation()
                }
              />
            </div>
            {deactivationError && (
              <p className="delete-confirm-error">{deactivationError}</p>
            )}
            <div className="delete-confirm-actions">
              <button type="button" onClick={() => setDeactivationOpen(false)}>
                Cancelar
              </button>
              <button
                type="button"
                className="delete-confirm-primary"
                onClick={confirmDeactivation}
                disabled={deactivating}
              >
                {deactivating ? "Desativando..." : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function formatRemaining(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours > 0
    ? `${hours}h ${minutes}min ${seconds}s`
    : `${minutes}min ${seconds}s`;
}
