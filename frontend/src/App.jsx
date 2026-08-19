import { useEffect, useState } from "react";
import TopNav from "./components/TopNav";
import ParkingMap from "./components/ParkingMap";
import StatusPanel from "./components/StatusPanel";
import AssistantPanel from "./components/AssistantPanel";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
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

  function saveEstablishmentName(name) {
    setEstablishmentName(name);
    localStorage.setItem("goodwe-establishment-name", name);
  }
  const selectedRoom = uploadedPlan?.rooms.find(
    (room) => room.id === selectedRoomId,
  );

  useEffect(() => {
    if (!uploadedPlan?.plan_id) return undefined;
    let active = true;
    const refreshChargers = async () => {
      try {
        const response = await fetch(
          `${API_URL}/api/plans/${uploadedPlan.plan_id}/chargers`,
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
  }, [uploadedPlan?.plan_id]);

  async function handlePlanUploaded(plan) {
    setUploadedPlan(plan);
    setSelectedRoomId("all");
    setPendingDevice(null);
    setSelectedChargerId(null);
    try {
      const response = await fetch(
        `${API_URL}/api/plans/${plan.plan_id}/chargers`,
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
    setSelectedChargerId(device.id);
  }

  function handleRoomSelect(roomId) {
    setSelectedRoomId(roomId);
    setSelectedChargerId(null);
  }

  return (
    <div className="app-shell">
      <TopNav />
      <main className="dashboard-main">
        <div className="dashboard-grid">
          <ParkingMap
            uploadedPlan={uploadedPlan}
            onPlanUploaded={handlePlanUploaded}
            selectedRoomId={selectedRoomId}
            selectedRoomName={selectedRoom?.name}
            establishmentName={establishmentName}
            onEstablishmentNameChange={saveEstablishmentName}
            onRoomSelect={handleRoomSelect}
            pendingDevice={pendingDevice}
            devices={chargers}
            selectedChargerId={selectedChargerId}
            onChargerSelect={setSelectedChargerId}
            onDevicePlaced={handleDevicePlaced}
          />
          <StatusPanel
            rooms={uploadedPlan?.rooms || []}
            selectedRoomId={selectedRoomId}
            onRoomSelect={handleRoomSelect}
            pendingDevice={pendingDevice}
            onDeviceSelect={handleDeviceSelect}
            chargers={chargers}
            selectedChargerId={selectedChargerId}
            onChargerSelect={setSelectedChargerId}
          />
        </div>
        <AssistantPanel />
      </main>
    </div>
  );
}

export default App;
