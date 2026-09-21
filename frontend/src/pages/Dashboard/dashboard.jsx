import AssistantPanel from "../../components/AssistantPanel";
import ParkingMap from "../../components/ParkingMap";
import StatusPanel from "../../components/StatusPanel";
import "./dashboard.css";

export default function Dashboard({
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
