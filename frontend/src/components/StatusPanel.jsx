import { ChevronDown } from "lucide-react";
import { useState } from "react";
import DevicesPanel from "./DevicesPanel";

function telemetryLabel(status) {
  if (status === "charging") return "Carregando";
  if (["available", "preparing", "suspended", "finished"].includes(status))
    return "Standby";
  return "Falha";
}

function StatusPanel({
  rooms = [],
  selectedRoomId = "all",
  onRoomSelect = () => {},
  pendingDevice = null,
  onDeviceSelect = () => {},
  chargers = [],
  selectedChargerId = null,
  onChargerSelect = () => {},
}) {
  const [showDevices, setShowDevices] = useState(false);
  const selectedCharger = chargers.find(
    (charger) => charger.id === selectedChargerId,
  );

  return (
    <aside className="status-column">
      <section className="side-panel selector-panel">
        <label htmlFor="sector">Contexto de visualização</label>
        <div className="select-wrap">
          <select
            id="sector"
            value={selectedRoomId}
            onChange={(event) => onRoomSelect(event.target.value)}
          >
            <option value="all">Todos</option>
            {rooms.map((room) => (
              <option value={room.id} key={room.id}>
                {room.name}
              </option>
            ))}
          </select>
          <ChevronDown size={14} aria-hidden="true" />
        </div>
      </section>
      {showDevices ? (
        <DevicesPanel
          onClose={() => setShowDevices(false)}
          onDeviceSelect={onDeviceSelect}
        />
      ) : (
        <section className="side-panel status-panel">
          <div className="section-heading">
            <h2>Status dos carregadores</h2>
            <span className="live-indicator">ao vivo</span>
          </div>
          <button
            className="add-devices-button"
            type="button"
            onClick={() => setShowDevices(true)}
          >
            <span>Adicionar aparelhos</span>
            <span className="add-devices-plus">+</span>
          </button>
          {pendingDevice && (
            <div className="placement-notice">
              Clique no mapa para posicionar{" "}
              <strong>{pendingDevice.name}</strong>.
            </div>
          )}
          {selectedCharger ? (
            <div className="selected-charger-status">
              <div className="selected-charger-header">
                <div>
                  <span className="panel-kicker">Carregador selecionado</span>
                  <strong>{selectedCharger.name}</strong>
                </div>
                <button
                  type="button"
                  className="panel-close-button"
                  aria-label="Fechar dados do carregador"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={() => onChargerSelect(null)}
                >
                  ×
                </button>
              </div>
              <p className="selected-charger-model">
                {selectedCharger.model || "GoodWe HCA G2"}
              </p>
              <div className="selected-status-line">
                <span
                  className={`status-dot status-dot-${telemetryLabel(selectedCharger.telemetry?.status).toLowerCase()}`}
                />
                {telemetryLabel(selectedCharger.telemetry?.status)}
                <span className="live-indicator">mock ao vivo</span>
              </div>
              <div className="telemetry-grid">
                <div>
                  <span>Potência</span>
                  <strong>
                    {selectedCharger.telemetry?.power_kw ??
                      selectedCharger.power_kw}{" "}
                    kW
                  </strong>
                </div>
                <div>
                  <span>Tensão</span>
                  <strong>
                    {selectedCharger.telemetry?.voltage_v ?? "-"} V
                  </strong>
                </div>
                <div>
                  <span>Corrente</span>
                  <strong>
                    {selectedCharger.telemetry?.current_a ?? "-"} A
                  </strong>
                </div>
                <div>
                  <span>Energia sessão</span>
                  <strong>
                    {selectedCharger.telemetry?.session_energy_kwh ?? "-"} kWh
                  </strong>
                </div>
                <div>
                  <span>Energia total</span>
                  <strong>
                    {selectedCharger.telemetry?.energy_kwh ?? "-"} kWh
                  </strong>
                </div>
                <div>
                  <span>Temperatura</span>
                  <strong>
                    {selectedCharger.telemetry?.temperature_c ?? "-"} °C
                  </strong>
                </div>
                <div>
                  <span>Veículo</span>
                  <strong>
                    {selectedCharger.telemetry?.connection_status ===
                    "connected"
                      ? "Conectado"
                      : "Desconectado"}
                  </strong>
                </div>
              </div>
            </div>
          ) : chargers.length === 0 ? (
            <div className="empty-state">
              <span className="empty-pulse" />
              <p>Aguardando dados dos carregadores</p>
              <small>
                Os dados operacionais aparecerão aqui quando o backend estiver
                conectado.
              </small>
            </div>
          ) : null}
          {!selectedCharger && chargers.length > 0 && (
            <div className="charger-status-list">
              {chargers
                .filter(
                  (charger) =>
                    selectedRoomId === "all" ||
                    charger.room_id === selectedRoomId,
                )
                .map((charger) => {
                  const status = charger.telemetry?.status || "offline";
                  const statusLabel = telemetryLabel(status);
                  return (
                    <button
                      className="charger-status-row"
                      type="button"
                      onClick={() => onChargerSelect(charger.id)}
                      key={charger.id}
                    >
                      <span
                        className={`status-dot status-dot-${statusLabel.toLowerCase()}`}
                      />
                      <div className="charger-status-copy">
                        <strong>{charger.name}</strong>
                        <span>
                          {statusLabel} ·{" "}
                          {charger.telemetry?.power_kw ?? charger.power_kw} kW
                        </span>
                      </div>
                      <span className="charger-status-room">
                        {rooms.find((room) => room.id === charger.room_id)
                          ?.name || "Mapa"}
                      </span>
                    </button>
                  );
                })}
            </div>
          )}
        </section>
      )}
    </aside>
  );
}

export default StatusPanel;
