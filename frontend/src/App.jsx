import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard/dashboard";
import Info from "./pages/Info/info";
import Carregadores from "./pages/Carregadores/carregadores";
import Login from "./pages/Login/login";
import Pagamento, { BackToStation } from "./pages/Pagamento/pagamento";
import CarteiraTab from "./pages/Pagamento/CarteiraTab";
import ExtratoTab from "./pages/Pagamento/ExtratoTab";
import HistoricoTab from "./pages/Pagamento/HistoricoTab";
import RecargaTab from "./pages/Pagamento/RecargaTab";
import Relatorio from "./pages/Relatorio/relatorio";
import { fetchPlan } from "./services/api";
import { useChargerPolling } from "./hooks/useChargerPolling";
import { useStoredUser } from "./hooks/useStoredUser";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <RouterEntry />
    </BrowserRouter>
  );
}

function RouterEntry() {
  return useLocation().pathname.startsWith("/pagamentos/") ? (
    <Routes>
      <Route path="/pagamentos/:chargerCode" element={<Pagamento />}>
        <Route index element={<RecargaTab />} />
        <Route path="carteira" element={<CarteiraTab />} />
        <Route path="extrato" element={<ExtratoTab />} />
        <Route path="historico" element={<HistoricoTab />} />
        <Route path="*" element={<BackToStation />} />
      </Route>
    </Routes>
  ) : (
    <AppShell />
  );
}

function AppShell() {
  const [user, setUser] = useStoredUser();
  const [plan, setPlan] = useState(null);
  const [roomId, setRoomId] = useState("all");
  const [chargers, setChargers] = useChargerPolling(plan?.plan_id, user?.id);
  const [selectedChargerId, setSelectedChargerId] = useState(null);
  const [pendingDevice, setPendingDevice] = useState(null);
  const [establishmentName, setEstablishmentName] = useState(
    "Mapa do estabelecimento",
  );

  useEffect(() => {
    setPlan(null);
    setChargers([]);
    setRoomId("all");
    if (!user?.id) return undefined;
    setEstablishmentName(
      localStorage.getItem(`goodwe-establishment-name-${user.id}`) ||
        "Mapa do estabelecimento",
    );
    let active = true;
    const savedPlanId = localStorage.getItem(`goodwe-plan-${user.id}`);
    fetchPlan(user.id, savedPlanId)
      .then((nextPlan) => {
        if (!active || !nextPlan) return;
        localStorage.setItem(`goodwe-plan-${user.id}`, nextPlan.plan_id);
        setPlan(nextPlan);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user?.id, setChargers]);

  if (!user) return <Login onAuthenticated={setUser} />;

  const selectedRoom = plan?.rooms.find((room) => room.id === roomId);
  const updateName = (name) => {
    setEstablishmentName(name);
    localStorage.setItem(`goodwe-establishment-name-${user.id}`, name);
  };
  const handlePlanUploaded = (nextPlan) => {
    setPlan(nextPlan);
    localStorage.setItem(`goodwe-plan-${user.id}`, nextPlan.plan_id);
    setRoomId("all");
    setPendingDevice(null);
    setSelectedChargerId(null);
  };
  const handleDevicePlaced = (device) => {
    setChargers((items) => [
      ...items.filter((item) => item.id !== device.id),
      device,
    ]);
    setPendingDevice(null);
    setSelectedChargerId(null);
  };
  const handleRoomSelect = (nextRoomId) => {
    setRoomId(nextRoomId);
    setSelectedChargerId(null);
  };
  const handleChargerUpdate = (updated) =>
    setChargers((items) =>
      items.map((item) => (item.id === updated.id ? updated : item)),
    );
  const handleChargerDelete = (id) => {
    setChargers((items) => items.filter((item) => item.id !== id));
    setSelectedChargerId((current) => (current === id ? null : current));
  };

  return (
    <div className="app-shell">
      <TopNav user={user} onLogout={() => setUser(null)} />
      <main className="app-main">
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                uploadedPlan={plan}
                selectedRoomId={roomId}
                selectedRoom={selectedRoom}
                establishmentName={establishmentName}
                saveEstablishmentName={updateName}
                onPlanUploaded={handlePlanUploaded}
                onRoomSelect={handleRoomSelect}
                pendingDevice={pendingDevice}
                chargers={chargers}
                selectedChargerId={selectedChargerId}
                setSelectedChargerId={setSelectedChargerId}
                onDeviceSelect={setPendingDevice}
                onDevicePlaced={handleDevicePlaced}
                onChargerUpdate={handleChargerUpdate}
                onChargerDelete={handleChargerDelete}
                ownerId={user.id}
              />
            }
          />
          <Route
            path="/carregadores"
            element={
              <Carregadores rooms={plan?.rooms || []} ownerId={user.id} />
            }
          />
          <Route path="/relatorios" element={<Relatorio userId={user.id} />} />
          <Route
            path="/configuracoes"
            element={<Info title="Configurações" />}
          />
          <Route path="/ajuda" element={<Info title="Ajuda" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
