import { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import TopNav from "./components/TopNav";
import ParkingMap from "./components/ParkingMap";
import StatusPanel from "./components/StatusPanel";
import AssistantPanel from "./components/AssistantPanel";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function getApiError(payload, fallback) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => item?.msg || "Dados inválidos.")
      .join(" ");
  }
  return fallback;
}

function App() {
  return (
    <BrowserRouter>
      <RouterEntry />
    </BrowserRouter>
  );
}

function RouterEntry() {
  const location = useLocation();
  const isPublicPayment = location.pathname.startsWith("/pagamentos/");

  if (isPublicPayment) {
    return (
      <Routes>
        <Route path="/pagamentos/:chargerCode" element={<ChargeGridPage />} />
      </Routes>
    );
  }

  return <AppShell />;
}

function AppShell() {
  const [sessionUser, setSessionUser] = useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("goodwe-monitoring-user") || "null",
      );
    } catch {
      return null;
    }
  });
  const [uploadedPlan, setUploadedPlan] = useState(null);
  const [selectedRoomId, setSelectedRoomId] = useState("all");
  const [chargers, setChargers] = useState([]);
  const [selectedChargerId, setSelectedChargerId] = useState(null);
  const [pendingDevice, setPendingDevice] = useState(null);
  const [establishmentName, setEstablishmentName] = useState(
    () =>
      localStorage.getItem("goodwe-establishment-name") ||
      "Mapa do estabelecimento",
  );

  useEffect(() => {
    if (!sessionUser?.id) return undefined;
    const savedPlanId = localStorage.getItem(`goodwe-plan-${sessionUser.id}`);

    let active = true;
    const planRequest = savedPlanId
      ? fetch(`${API_URL}/api/plans/${encodeURIComponent(savedPlanId)}`)
      : fetch(
          `${API_URL}/api/plans?owner_id=${encodeURIComponent(sessionUser.id)}`,
        );
    planRequest
      .then((response) => (response.ok ? response.json() : null))
      .then(async (plan) => {
        plan = Array.isArray(plan) ? plan[0] : plan;
        if (!active || !plan) return;
        localStorage.setItem(`goodwe-plan-${sessionUser.id}`, plan.plan_id);
        setUploadedPlan(plan);
        const response = await fetch(
          `${API_URL}/api/plans/${plan.plan_id}/chargers?owner_id=${encodeURIComponent(sessionUser.id)}`,
        );
        if (active && response.ok) setChargers(await response.json());
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [sessionUser?.id]);

  function saveEstablishmentName(name) {
    setEstablishmentName(name);
    localStorage.setItem("goodwe-establishment-name", name);
  }

  const selectedRoom = uploadedPlan?.rooms.find(
    (room) => room.id === selectedRoomId,
  );

  function handleLogout() {
    localStorage.removeItem("goodwe-monitoring-user");
    setSessionUser(null);
  }

  useEffect(() => {
    if (!uploadedPlan?.plan_id) return undefined;
    let active = true;
    const refreshChargers = async () => {
      try {
        const response = await fetch(
          `${API_URL}/api/plans/${uploadedPlan.plan_id}/chargers?owner_id=${encodeURIComponent(sessionUser.id)}`,
        );
        if (response.ok && active) setChargers(await response.json());
      } catch {
        // A última leitura permanece disponível durante uma indisponibilidade breve.
      }
    };
    const timer = window.setInterval(refreshChargers, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [uploadedPlan?.plan_id, sessionUser?.id]);

  if (!sessionUser) {
    return <MonitoringAuthPage onAuthenticated={setSessionUser} />;
  }

  async function handlePlanUploaded(plan) {
    setUploadedPlan(plan);
    localStorage.setItem(`goodwe-plan-${sessionUser.id}`, plan.plan_id);
    setSelectedRoomId("all");
    setPendingDevice(null);
    setSelectedChargerId(null);
    try {
      const response = await fetch(
        `${API_URL}/api/plans/${plan.plan_id}/chargers?owner_id=${encodeURIComponent(sessionUser.id)}`,
      );
      if (response.ok) {
        const loadedChargers = await response.json();
        setChargers((current) => [
          ...loadedChargers,
          ...current.filter(
            (charger) =>
              charger.plan_id === plan.plan_id &&
              !loadedChargers.some((loaded) => loaded.id === charger.id),
          ),
        ]);
      }
    } catch {
      setChargers([]);
    }
  }

  function handleDeviceSelect(device) {
    setPendingDevice(device);
  }

  function handleDevicePlaced(device) {
    setChargers((current) => [
      ...current.filter((charger) => charger.id !== device.id),
      device,
    ]);
    setPendingDevice(null);
    setSelectedChargerId(null);
  }

  function handleRoomSelect(roomId) {
    setSelectedRoomId(roomId);
    setSelectedChargerId(null);
  }

  function handleChargerUpdate(updatedCharger) {
    setChargers((current) =>
      current.map((charger) =>
        charger.id === updatedCharger.id ? updatedCharger : charger,
      ),
    );
  }

  function handleChargerDelete(chargerId) {
    setChargers((current) =>
      current.filter((charger) => charger.id !== chargerId),
    );
    setSelectedChargerId((current) => (current === chargerId ? null : current));
  }

  return (
    <div className="app-shell">
      <TopNav user={sessionUser} onLogout={handleLogout} />
      <main className="app-main">
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                uploadedPlan={uploadedPlan}
                selectedRoomId={selectedRoomId}
                selectedRoom={selectedRoom}
                establishmentName={establishmentName}
                saveEstablishmentName={saveEstablishmentName}
                onPlanUploaded={handlePlanUploaded}
                onRoomSelect={handleRoomSelect}
                pendingDevice={pendingDevice}
                chargers={chargers}
                selectedChargerId={selectedChargerId}
                setSelectedChargerId={setSelectedChargerId}
                onDeviceSelect={handleDeviceSelect}
                onDevicePlaced={handleDevicePlaced}
                onChargerUpdate={handleChargerUpdate}
                onChargerDelete={handleChargerDelete}
                ownerId={sessionUser.id}
              />
            }
          />
          <Route
            path="/carregadores"
            element={
              <ChargersPage
                rooms={uploadedPlan?.rooms || []}
                ownerId={sessionUser.id}
              />
            }
          />
          <Route
            path="/relatorios"
            element={<ReportsPage userId={sessionUser.id} />}
          />
          <Route
            path="/configuracoes"
            element={<InfoPage title="Configurações" />}
          />
          <Route path="/ajuda" element={<InfoPage title="Ajuda" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function MonitoringAuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setMessage("");
    setLoading(true);
    const endpoint =
      mode === "login" ? "/api/auth/login" : "/api/auth/register";
    const body = mode === "login" ? form : { ...form, role: "lojista" };
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        setMessage(getApiError(payload, "Não foi possível concluir."));
        return;
      }
      if (mode === "register") {
        setMode("login");
        setForm({ name: "", email: form.email, password: "" });
        setMessage(
          "Cadastro realizado. Faça login para acessar o monitoramento.",
        );
        return;
      }
      localStorage.setItem("goodwe-monitoring-user", JSON.stringify(payload));
      onAuthenticated(payload);
    } catch {
      setMessage("Não foi possível conectar ao servidor.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="monitoring-auth-page">
      <section className="monitoring-auth-brand">
        <span className="public-brand">GOODWE</span>
        <span>EV SOLUTIONS</span>
        <h1>Monitoramento de carregadores</h1>
        <p>Entre para acompanhar a operação do seu estabelecimento.</p>
      </section>
      <form className="monitoring-auth-card" onSubmit={submit}>
        <div className="auth-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setMessage("");
            }}
          >
            Login
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setMessage("");
            }}
          >
            Cadastro
          </button>
        </div>
        <div className="auth-card-heading">
          <span className="page-kicker">Acesso do lojista</span>
          <h2>{mode === "login" ? "Bem-vindo de volta" : "Criar acesso"}</h2>
        </div>
        {mode === "register" && (
          <label>
            Nome
            <input
              required
              minLength="2"
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
            minLength="6"
            type="password"
            value={form.password}
            onChange={(event) =>
              setForm({ ...form, password: event.target.value })
            }
          />
        </label>
        <button className="auth-submit" disabled={loading}>
          {loading
            ? "Aguarde..."
            : mode === "login"
              ? "Entrar no monitoramento"
              : "Criar conta"}
        </button>
        {message && (
          <p
            className={
              message.startsWith("Cadastro realizado")
                ? "auth-success"
                : "auth-error"
            }
          >
            {message}
          </p>
        )}
      </form>
    </main>
  );
}

function DashboardPage({
  uploadedPlan,
  selectedRoomId,
  selectedRoom,
  establishmentName,
  saveEstablishmentName,
  onPlanUploaded,
  onRoomSelect,
  pendingDevice,
  chargers,
  selectedChargerId,
  setSelectedChargerId,
  onDeviceSelect,
  onDevicePlaced,
  onChargerUpdate,
  onChargerDelete,
  ownerId,
}) {
  return (
    <div className="dashboard-main">
      <div className="dashboard-grid">
        <ParkingMap
          uploadedPlan={uploadedPlan}
          onPlanUploaded={onPlanUploaded}
          selectedRoomId={selectedRoomId}
          selectedRoomName={selectedRoom?.name}
          establishmentName={establishmentName}
          onEstablishmentNameChange={saveEstablishmentName}
          onRoomSelect={onRoomSelect}
          pendingDevice={pendingDevice}
          devices={chargers}
          selectedChargerId={selectedChargerId}
          onChargerSelect={setSelectedChargerId}
          onDevicePlaced={onDevicePlaced}
          onChargerUpdate={onChargerUpdate}
          onChargerDelete={onChargerDelete}
          ownerId={ownerId}
        />
        <StatusPanel
          rooms={uploadedPlan?.rooms || []}
          selectedRoomId={selectedRoomId}
          onRoomSelect={onRoomSelect}
          pendingDevice={pendingDevice}
          onDeviceSelect={onDeviceSelect}
          chargers={chargers}
          selectedChargerId={selectedChargerId}
          onChargerSelect={setSelectedChargerId}
        />
      </div>
      <AssistantPanel ownerId={ownerId} />
    </div>
  );
}

function ChargersPage({ rooms = [], ownerId }) {
  const [ownedChargers, setOwnedChargers] = useState([]);
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/chargers?owner_id=${encodeURIComponent(ownerId)}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((items) => {
        if (active) setOwnedChargers(items);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [ownerId]);

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function deactivateCharger(charger, code) {
    const response = await fetch(
      `${API_URL}/api/plans/${charger.plan_id}/chargers/${charger.id}?code=${encodeURIComponent(code)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(
        getApiError(payload, "Não foi possível desativar o carregador."),
      );
    }
    setOwnedChargers((current) =>
      current.filter((currentCharger) => currentCharger.id !== charger.id),
    );
  }

  const realChargers = useMemo(
    () =>
      [...ownedChargers]
        .filter(
          (charger) => String(charger.kind || "").toLowerCase() === "real",
        )
        .sort((a, b) => a.name.localeCompare(b.name)),
    [ownedChargers],
  );

  return (
    <div className="page-shell">
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
        <div className="charger-sections">
          <section className="charger-section">
            <div className="section-title-row">
              <h2>Aparelhos instalados</h2>
              <span>{realChargers.length}</span>
            </div>
            <div
              className={`charger-grid ${realChargers.length > 4 ? "has-many" : ""}`}
            >
              {renderChargerCards(
                realChargers,
                rooms,
                currentTime,
                deactivateCharger,
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function renderChargerCards(chargers, rooms, currentTime, onDeactivate) {
  return chargers.map((charger) => {
    const roomName =
      rooms.find((room) => room.id === charger.room_id)?.name || "Mapa geral";
    const liveSession = getLiveSession(charger, currentTime);
    const chargePercent = liveSession?.progressPercent || 0;
    const statusText = getStatusLabel(charger.telemetry?.status);
    const isStandby = !liveSession;

    return (
      <ChargerCard
        key={charger.id}
        charger={charger}
        roomName={roomName}
        liveSession={liveSession}
        chargePercent={chargePercent}
        statusText={statusText}
        onDeactivate={onDeactivate}
      />
    );
  });
}

function ChargerCard({
  charger,
  roomName,
  liveSession,
  chargePercent,
  statusText,
  onDeactivate,
}) {
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(charger.name);
  const [savedName, setSavedName] = useState(charger.name);
  const [nameError, setNameError] = useState("");
  const [deactivating, setDeactivating] = useState(false);
  const [deactivationOpen, setDeactivationOpen] = useState(false);
  const [deactivationCode, setDeactivationCode] = useState("");
  const [deactivationError, setDeactivationError] = useState("");
  const [qrSource, setQrSource] = useState("");
  const isStandby = !liveSession;

  async function saveName() {
    const name = nameDraft.trim();
    if (!name || name === savedName) {
      setEditingName(false);
      return;
    }
    try {
      const response = await fetch(
        `${API_URL}/api/plans/${charger.plan_id}/chargers/${charger.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        },
      );
      if (!response.ok) throw new Error("Não foi possível salvar o nome.");
      setSavedName(name);
      setNameDraft(name);
      setNameError("");
      setEditingName(false);
    } catch (error) {
      setNameError(error.message);
    }
  }

  async function requestDeactivation() {
    setDeactivationCode("");
    setDeactivationError("");
    setDeactivationOpen(true);
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

  function downloadQrCode() {
    if (!qrSource) return;
    const link = document.createElement("a");
    link.href = qrSource;
    link.download = `qrcode-${charger.code || "HC2-0000"}.png`;
    link.click();
  }

  return (
    <article key={charger.id} className="charger-card">
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
                value={nameDraft}
                autoFocus
                onChange={(event) => setNameDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") saveName();
                  if (event.key === "Escape") setEditingName(false);
                }}
              />
              <button type="button" onClick={saveName} aria-label="Salvar nome">
                OK
              </button>
            </div>
          ) : (
            <div className="charger-name-line">
              <h2>{savedName}</h2>
              <button
                type="button"
                className="edit-name-button"
                onClick={() => setEditingName(true)}
                aria-label={`Editar nome de ${savedName}`}
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
            onClick={requestDeactivation}
            disabled={deactivating}
          >
            {deactivating ? "..." : "Desativar"}
          </button>
        </div>
      </div>

      <div className="charger-identity-row">
        <div className="charger-qr-row">
          <ChargerQrCode code={charger.code} onSourceChange={setQrSource} />
          <div>
            <span>QR permanente</span>
            <strong>/pagamentos/{charger.code}</strong>
            <button
              type="button"
              className="download-qr-button"
              onClick={downloadQrCode}
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
              <strong>{chargePercent}%</strong>
            </div>

            <div
              className="charge-bar"
              aria-label={`Carga atual do carregador ${charger.name}`}
            >
              <span
                style={{ width: `${chargePercent}%` }}
                className="charge-fill"
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
          {charger.power_kw ?? charger.telemetry?.power_kw ?? 11} kW
        </strong>
      </div>
      <div className="charger-info-row">
        <span>Estado</span>
        <strong>{statusText}</strong>
      </div>

      {nameError && !editingName && (
        <small className="name-edit-error">{nameError}</small>
      )}
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
              aria-label="Fechar confirmação de desativação"
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
              <label htmlFor={`deactivation-code-${charger.id}`}>
                Código do carregador
              </label>
              <input
                id={`deactivation-code-${charger.id}`}
                type="text"
                value={deactivationCode}
                autoFocus
                onChange={(event) =>
                  setDeactivationCode(event.target.value.toUpperCase())
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") confirmDeactivation();
                  if (event.key === "Escape") setDeactivationOpen(false);
                }}
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

function ChargerQrCode({ code, onSourceChange }) {
  const [source, setSource] = useState("");

  useEffect(() => {
    let active = true;
    QRCode.toDataURL(`${window.location.origin}/pagamentos/${code}`, {
      errorCorrectionLevel: "M",
      margin: 1,
      width: 92,
    })
      .then((nextSource) => {
        if (active) {
          setSource(nextSource);
          onSourceChange?.(nextSource);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [code, onSourceChange]);

  return source ? (
    <img src={source} alt={`QR Code do carregador ${code}`} />
  ) : (
    <span className="qr-placeholder" aria-hidden="true" />
  );
}

function ChargeGridPage() {
  const { chargerCode } = useParams();
  const [charger, setCharger] = useState(null);
  const [user, setUser] = useState(null);
  const [walletBalance, setWalletBalance] = useState(0);
  const [mode, setMode] = useState("landing");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [order, setOrder] = useState({
    energy_kwh: 20,
    payment_method: "pix",
  });

  const currentDate = new Date();
  const isPeakHour =
    currentDate.getHours() >= 18 && currentDate.getHours() < 22;
  const calculatedPrice = isPeakHour ? 2.79 : 1.99;
  const calculatedDuration = Math.max(
    1,
    Math.round((order.energy_kwh / Number(charger?.power_kw || 11)) * 60),
  );

  useEffect(() => {
    fetch(`${API_URL}/api/chargegrid/${encodeURIComponent(chargerCode)}`)
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("Carregador não encontrado.")),
      )
      .then(setCharger)
      .catch((error) => setMessage(error.message));
  }, [chargerCode]);

  async function submitAuth(event) {
    event.preventDefault();
    const endpoint =
      mode === "register" ? "/api/auth/register" : "/api/auth/login";
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = await response.json();
      if (!response.ok)
        return setMessage(getApiError(payload, "Não foi possível continuar."));
      if (mode === "register") {
        setForm({ name: "", email: form.email, password: "" });
        setMode("landing");
        return setMessage("Cadastro realizado. Faça login para continuar.");
      }
      setUser(payload);
      setWalletBalance(Number(payload.wallet_balance || 0));
      setMode("booking");
      setMessage("");
    } catch {
      setMessage("Não foi possível conectar ao servidor.");
    }
  }

  async function submitOrder(event) {
    event.preventDefault();
    try {
      const response = await fetch(`${API_URL}/api/charging-orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...order,
          user_id: user.id,
          charger_code: charger.code,
          price_per_kwh: calculatedPrice,
          scheduled_at: currentDate.toISOString(),
          estimated_duration_minutes: calculatedDuration,
        }),
      });
      const payload = await response.json();
      setMessage(
        response.ok
          ? `Solicitação criada. Total: R$ ${Number(payload.total_amount).toFixed(2).replace(".", ",")}`
          : payload.detail || "Não foi possível criar a solicitação.",
      );
    } catch {
      setMessage("Não foi possível conectar ao servidor.");
    }
  }

  async function topUp(amount) {
    try {
      const response = await fetch(`${API_URL}/api/wallet/top-ups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id, amount }),
      });
      if (response.ok) {
        setWalletBalance((current) => current + amount);
        setMessage(`Crédito de R$ ${amount},00 adicionado à carteira.`);
      } else {
        setMessage("Não foi possível adicionar o crédito.");
      }
    } catch {
      setMessage("Não foi possível conectar ao servidor.");
    }
  }

  if (message && !charger)
    return (
      <div className="chargegrid-page">
        <div className="public-panel">
          <p>{message}</p>
        </div>
      </div>
    );
  if (!charger)
    return (
      <div className="chargegrid-page">
        <div className="public-panel">
          <p>Carregando estação...</p>
        </div>
      </div>
    );

  return (
    <div className="chargegrid-page">
      <header className="public-header">
        <span className="public-brand">ChargeGrid</span>
        <span>Estação {charger.code}</span>
      </header>
      <main className="public-content">
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
            <p>Entre na sua conta para planejar e pagar uma sessão.</p>
            <button
              type="button"
              className="public-primary"
              onClick={() => setMode("login")}
            >
              Login
            </button>
            <button
              type="button"
              className="public-secondary"
              onClick={() => setMode("register")}
            >
              Cadastrar
            </button>
            {message && <p className="public-success">{message}</p>}
          </section>
        )}
        {(mode === "login" || mode === "register") && (
          <form className="public-panel public-form" onSubmit={submitAuth}>
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
            <button
              type="button"
              className="public-text-button"
              onClick={() => setMode("landing")}
            >
              Voltar
            </button>
            {message && <p className="public-error">{message}</p>}
          </form>
        )}
        {mode === "booking" && (
          <>
            <div className="account-bar">
              <div>
                <span>Cliente</span>
                <strong>{user.name}</strong>
              </div>
              <div>
                <span>Saldo disponível</span>
                <strong>R$ {walletBalance.toFixed(2).replace(".", ",")}</strong>
              </div>
            </div>
            <form className="public-panel public-form" onSubmit={submitOrder}>
              <div className="booking-heading">
                <div>
                  <span className="page-kicker">Nova sessão</span>
                  <h2>Planejar carregamento</h2>
                </div>
                <span className="station-status">
                  {charger.status === "charging" ? "Em uso" : "Livre"}
                </span>
              </div>
              <label>
                Quantidade de carga (kWh)
                <input
                  required
                  type="number"
                  min="1"
                  step="1"
                  value={order.energy_kwh}
                  onChange={(event) =>
                    setOrder({
                      ...order,
                      energy_kwh: Number(event.target.value),
                    })
                  }
                />
              </label>
              <div className="calculated-summary">
                <div>
                  <span>Preço atual do kWh</span>
                  <strong>
                    R$ {calculatedPrice.toFixed(2).replace(".", ",")}
                  </strong>
                </div>
                <div>
                  <span>Horário</span>
                  <strong>
                    {currentDate.toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    · {isPeakHour ? "Pico" : "Fora de pico"}
                  </strong>
                </div>
                <div>
                  <span>Previsão de carga</span>
                  <strong>{calculatedDuration} min</strong>
                </div>
                <div>
                  <span>Total estimado</span>
                  <strong>
                    R${" "}
                    {(order.energy_kwh * calculatedPrice)
                      .toFixed(2)
                      .replace(".", ",")}
                  </strong>
                </div>
              </div>
              <fieldset>
                <legend>Selecionar pagamento</legend>
                <div className="payment-options">
                  <button
                    type="button"
                    className={order.payment_method === "pix" ? "selected" : ""}
                    onClick={() =>
                      setOrder({ ...order, payment_method: "pix" })
                    }
                  >
                    PIX
                  </button>
                  <button
                    type="button"
                    className={
                      order.payment_method === "paypal" ? "selected" : ""
                    }
                    onClick={() =>
                      setOrder({ ...order, payment_method: "paypal" })
                    }
                  >
                    PayPal
                  </button>
                  <button
                    type="button"
                    className={
                      order.payment_method === "wallet" ? "selected" : ""
                    }
                    onClick={() =>
                      setOrder({ ...order, payment_method: "wallet" })
                    }
                  >
                    Carteira
                  </button>
                </div>
              </fieldset>
              <div className="wallet-options">
                <span>Adicionar saldo fixo</span>
                {[10, 25, 50, 100].map((amount) => (
                  <button
                    type="button"
                    key={amount}
                    onClick={() => topUp(amount)}
                  >
                    R$ {amount}
                  </button>
                ))}
              </div>
              <button className="public-primary">Selecionar pagamento</button>
              {message && <p className="public-success">{message}</p>}
            </form>
          </>
        )}
      </main>
    </div>
  );
}

function InfoPage({ title }) {
  const location = useLocation();
  const currentPath = location.pathname;

  return (
    <div className="page-shell">
      <div className="empty-page-card">
        <p>{title}</p>
        <p className="stub-path">Rota em desenvolvimento: {currentPath}</p>
        <NavLink to="/" className="primary-link">
          Voltar para visão geral
        </NavLink>
      </div>
    </div>
  );
}

function ReportsPage({ userId }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(
      `${API_URL}/api/reports/summary?owner_id=${encodeURIComponent(userId)}`,
    )
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(
              new Error("Não foi possível carregar os relatórios."),
            ),
      )
      .then(setReport)
      .catch((requestError) => setError(requestError.message));
  }, [userId]);

  const money = (value) =>
    `R$ ${Number(value || 0)
      .toFixed(2)
      .replace(".", ",")}`;
  const maxEnergy = Math.max(
    1,
    ...(report?.chargers || []).map((item) => Number(item.energy_kwh || 0)),
  );
  const maxDaily = Math.max(
    1,
    ...(report?.daily || []).map((item) => Number(item.energy_kwh || 0)),
  );

  return (
    <div className="page-shell reports-shell">
      <header className="page-header">
        <div>
          <span className="page-kicker">Visão financeira e energética</span>
          <h1>Relatórios</h1>
        </div>
        <span className="reports-period">Mês atual</span>
      </header>
      {error && <div className="report-error">{error}</div>}
      {!report ? (
        <div className="empty-page-card">
          <p>Carregando dados...</p>
        </div>
      ) : (
        <>
          <section className="report-kpis">
            <div className="report-kpi">
              <span>Carregadores ativos</span>
              <strong>{report.charger_count}</strong>
              <small>Equipamentos reais cadastrados</small>
            </div>
            <div className="report-kpi">
              <span>Consumo no mês</span>
              <strong>
                {Number(report.month_energy_kwh).toFixed(1).replace(".", ",")}{" "}
                kWh
              </strong>
              <small>Energia solicitada pelos clientes</small>
            </div>
            <div className="report-kpi">
              <span>Receita no mês</span>
              <strong>{money(report.month_revenue)}</strong>
              <small>Pagamentos confirmados</small>
            </div>
            <div className="report-kpi report-kpi-accent">
              <span>Receita acumulada</span>
              <strong>{money(report.revenue_total)}</strong>
              <small>Saldo gerado pelos clientes</small>
            </div>
          </section>
          <section className="reports-grid">
            <article className="report-panel">
              <div className="report-panel-heading">
                <div>
                  <span className="page-kicker">Distribuição</span>
                  <h2>Consumo por carregador</h2>
                </div>
                <span className="report-unit">kWh</span>
              </div>
              <div className="charger-bars">
                {report.chargers.slice(0, 12).map((item) => (
                  <div className="charger-bar-row" key={item.code}>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.code}</span>
                    </div>
                    <div className="bar-track">
                      <i
                        style={{
                          width: `${Math.max(3, (Number(item.energy_kwh) / maxEnergy) * 100)}%`,
                        }}
                      />
                    </div>
                    <b>{Number(item.energy_kwh).toFixed(1)}</b>
                  </div>
                ))}
              </div>
            </article>
            <article className="report-panel">
              <div className="report-panel-heading">
                <div>
                  <span className="page-kicker">Últimos 7 dias</span>
                  <h2>Energia e receita</h2>
                </div>
                <span className="report-unit">kWh</span>
              </div>
              <div className="daily-chart">
                {report.daily.map((item) => (
                  <div className="daily-column" key={item.day}>
                    <div
                      className="daily-bar"
                      style={{
                        height: `${Math.max(4, (Number(item.energy_kwh) / maxDaily) * 100)}%`,
                      }}
                      title={`${item.energy_kwh} kWh`}
                    />
                    <span>{item.day.slice(8)}</span>
                  </div>
                ))}
              </div>
              <div className="chart-caption">
                <span>Energia entregue</span>
                <strong>
                  {Number(report.generated_energy_kwh)
                    .toFixed(1)
                    .replace(".", ",")}{" "}
                  kWh monitorados
                </strong>
              </div>
            </article>
          </section>
        </>
      )}
    </div>
  );
}

function getStatusLabel(status) {
  if (status === "charging") return "Carregando";
  if (["available", "preparing", "suspended", "finished"].includes(status))
    return "Standby";
  if (status === "faulted" || status === "offline") return "Falha";
  return "Disponível";
}

function formatDateTime(date) {
  const value = date instanceof Date ? date : new Date(date);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(value);
}

function getLiveSession(charger, currentTime) {
  if (
    !charger.active_session_started_at ||
    !charger.active_session_duration_minutes
  )
    return null;
  const startedAt = new Date(charger.active_session_started_at);
  const totalSeconds = charger.active_session_duration_minutes * 60;
  const elapsedSeconds = Math.max(
    0,
    Math.floor((currentTime - startedAt.getTime()) / 1000),
  );
  const remainingSeconds = Math.max(0, totalSeconds - elapsedSeconds);
  if (remainingSeconds === 0) return null;
  return {
    startedAt,
    endsAt: new Date(startedAt.getTime() + totalSeconds * 1000),
    remainingSeconds,
    progressPercent: Math.min(
      100,
      Math.round((elapsedSeconds / totalSeconds) * 100),
    ),
  };
}

function formatRemaining(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}min ${seconds}s`;
  return `${minutes}min ${seconds}s`;
}

export default App;
