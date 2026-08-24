import { Image, Plus, X } from "lucide-react";
import { useState } from "react";

const availableDevices = [
  {
    id: "hc2",
    name: "HC2",
    model: "Carregador EV GoodWe HCA G2",
    image: null,
  },
];

function DevicesPanel({ onClose, onDeviceSelect }) {
  const [selectedKind, setSelectedKind] = useState("simulated");

  return (
    <section className="side-panel devices-panel">
      <div className="devices-heading">
        <div>
          <p className="panel-kicker">Biblioteca de dispositivos</p>
          <h2>Adicionar aparelhos</h2>
        </div>
        <button
          className="panel-close-button"
          type="button"
          aria-label="Fechar aparelhos"
          onClick={onClose}
        >
          <X size={15} />
        </button>
      </div>
      <p className="devices-description">
        Selecione um aparelho para posicioná-lo no mapa.
      </p>
      <div className="device-kind-selector" role="group" aria-label="Tipo do carregador">
        <button
          type="button"
          className={selectedKind === "simulated" ? "is-selected" : ""}
          onClick={() => setSelectedKind("simulated")}
        >
          Simulado
        </button>
        <button
          type="button"
          className={selectedKind === "real" ? "is-selected" : ""}
          onClick={() => setSelectedKind("real")}
        >
          Real
        </button>
      </div>
      <div className="device-list">
        {availableDevices.map((device) => (
          <button
            className="device-card"
            type="button"
            key={device.id}
            onClick={() => {
              onDeviceSelect({ ...device, kind: selectedKind });
              onClose();
            }}
          >
            <div className="device-image-placeholder">
              {device.image ? (
                <img src={device.image} alt="" />
              ) : (
                <Image size={24} strokeWidth={1.4} />
              )}
            </div>
            <div className="device-card-copy">
              <strong>{device.name}</strong>
              <span>{device.model}</span>
            </div>
            <Plus className="device-add-icon" size={17} />
          </button>
        ))}
      </div>
    </section>
  );
}

export default DevicesPanel;
