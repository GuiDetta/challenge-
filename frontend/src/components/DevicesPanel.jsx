import { Image, Plus, X } from "lucide-react";

const availableDevices = [
  {
    id: "hc2",
    name: "HC2",
    model: "Carregador EV GoodWe HCA G2",
    image: null,
  },
];

function DevicesPanel({ onClose, onDeviceSelect }) {
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
      <div className="device-list">
        {availableDevices.map((device) => (
          <button
            className="device-card"
            type="button"
            key={device.id}
            onClick={() => {
              onDeviceSelect(device);
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
