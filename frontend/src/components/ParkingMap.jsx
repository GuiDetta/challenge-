import {
  FileUp,
  LoaderCircle,
  Maximize2,
  Minus,
  MoreHorizontal,
  Plus,
  RotateCcw,
  RotateCw,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  createCharger,
  deleteCharger,
  fetchChargerTelemetry,
  updateCharger,
  uploadPlan,
} from "../services/api";

function ParkingMap({
  uploadedPlan,
  onPlanUploaded,
  selectedRoomId,
  selectedRoomName,
  establishmentName,
  onEstablishmentNameChange,
  onRoomSelect,
  pendingDevice,
  devices = [],
  selectedChargerId,
  onChargerSelect = () => {},
  onDevicePlaced = () => {},
  onChargerUpdate = () => {},
  onChargerDelete = () => {},
  ownerId = null,
}) {
  const [uploadState, setUploadState] = useState("idle");
  const [uploadError, setUploadError] = useState("");
  const [uploadNotice, setUploadNotice] = useState("");
  const [showReference, setShowReference] = useState(true);
  const [showMapOptions, setShowMapOptions] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(establishmentName);
  const [viewport, setViewport] = useState({
    scale: 1,
    x: 0,
    y: 0,
    rotation: 0,
  });
  const [planSize, setPlanSize] = useState({ width: 0, height: 0 });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteCode, setDeleteCode] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const dragRef = useRef(null);
  const chargerDragRef = useRef(null);
  const planRef = useRef(null);
  const canvasRef = useRef(null);
  const markerRefs = useRef({});
  const fileInputRef = useRef(null);
  const [popupPosition, setPopupPosition] = useState(null);
  const focusedRoom = uploadedPlan?.rooms.find(
    (room) => room.id === selectedRoomId,
  );
  const selectedCharger = devices.find(
    (device) => device.id === selectedChargerId,
  );
  const focusStyle = focusedRoom
    ? {
        "--room-focus-x": `${((focusedRoom.bounds.x + focusedRoom.bounds.width / 2) / uploadedPlan.width) * 100}%`,
        "--room-focus-y": `${((focusedRoom.bounds.y + focusedRoom.bounds.height / 2) / uploadedPlan.height) * 100}%`,
      }
    : undefined;

  useEffect(() => {
    planRef.current
      ?.querySelectorAll("text[data-room-label]")
      .forEach((label) => {
        const x = label.getAttribute("x");
        const y = label.getAttribute("y");
        label.setAttribute(
          "transform",
          `rotate(${-viewport.rotation} ${x} ${y})`,
        );
      });
  }, [uploadedPlan, viewport.rotation]);

  useEffect(() => {
    const node = planRef.current;
    if (!node) return undefined;
    const updatePlanSize = () =>
      setPlanSize({ width: node.clientWidth, height: node.clientHeight });
    updatePlanSize();
    const observer = new ResizeObserver(updatePlanSize);
    observer.observe(node);
    return () => observer.disconnect();
  }, [uploadedPlan]);

  useEffect(() => {
    if (!selectedChargerId) {
      setPopupPosition(null);
      return undefined;
    }

    function updatePopupPosition() {
      const canvas = canvasRef.current;
      const marker = markerRefs.current[selectedChargerId];
      if (!canvas || !marker) return;
      const canvasRect = canvas.getBoundingClientRect();
      const markerRect = marker.getBoundingClientRect();
      setPopupPosition({
        left: markerRect.left - canvasRect.left + markerRect.width / 2,
        top: markerRect.top - canvasRect.top,
      });
    }

    updatePopupPosition();
    const frame = window.requestAnimationFrame(updatePopupPosition);
    window.addEventListener("resize", updatePopupPosition);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", updatePopupPosition);
    };
  }, [
    selectedChargerId,
    viewport,
    planSize,
    uploadedPlan,
    selectedRoomId,
    devices,
  ]);

  async function handlePlanUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadState("uploading");
    setUploadError("");
    try {
      const payload = await uploadPlan(file, ownerId);
      onPlanUploaded(payload);
      setUploadState("success");
      setUploadNotice(
        payload.warnings?.length
          ? "Planta processada com observações."
          : "Planta digital carregada.",
      );
      window.setTimeout(() => setUploadNotice(""), 2600);
    } catch (error) {
      setUploadState("error");
      setUploadError(
        error instanceof TypeError
          ? "API offline. Inicie o backend em http://127.0.0.1:8000 e tente novamente."
          : error instanceof Error
            ? error.message
            : "Falha ao enviar a planta.",
      );
    } finally {
      event.target.value = "";
    }
  }

  function updateZoom(delta) {
    setViewport((current) => ({
      ...current,
      scale: Math.min(4, Math.max(0.55, current.scale + delta)),
    }));
  }

  function rotateMap(delta) {
    setViewport((current) => ({
      ...current,
      rotation: current.rotation + delta,
    }));
  }

  function resetViewport() {
    setViewport({ scale: 1, x: 0, y: 0, rotation: 0 });
  }

  async function handleCanvasClick(event) {
    if (
      event.target.closest(
        ".map-controls, .map-toolbar, .device-marker, .charger-popup, .delete-confirm-backdrop, .delete-confirm-modal",
      )
    )
      return;

    if (selectedChargerId && !pendingDevice) {
      onChargerSelect(null);
    }

    if (pendingDevice && uploadedPlan) {
      const svg = planRef.current?.querySelector("svg");
      const matrix = svg?.getScreenCTM?.();
      if (!svg || !matrix) return;
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const transformedPoint = point.matrixTransform(matrix.inverse());
      const viewBox = svg.viewBox.baseVal;
      const mapPoint = {
        x: Math.min(
          viewBox.x + viewBox.width,
          Math.max(viewBox.x, transformedPoint.x),
        ),
        y: Math.min(
          viewBox.y + viewBox.height,
          Math.max(viewBox.y, transformedPoint.y),
        ),
      };
      const room = uploadedPlan.rooms.find(
        (candidate) =>
          mapPoint.x >= candidate.bounds.x &&
          mapPoint.x <= candidate.bounds.x + candidate.bounds.width &&
          mapPoint.y >= candidate.bounds.y &&
          mapPoint.y <= candidate.bounds.y + candidate.bounds.height,
      );
      try {
        const created = await createCharger(
          uploadedPlan.plan_id,
          {
            name: pendingDevice.name,
            x: mapPoint.x,
            y: mapPoint.y,
            room_id:
              room?.id || (selectedRoomId === "all" ? null : selectedRoomId),
            model: "GW7K-HCA-20",
            power_kw: 7,
            phase: "three",
            kind: pendingDevice.kind || "simulated",
          },
          ownerId,
        );
        const telemetry = await fetchChargerTelemetry(
          uploadedPlan.plan_id,
          created.id,
        ).catch(() => null);
        onDevicePlaced({ ...created, telemetry });
        setUploadNotice(`${created.name} adicionado ao mapa.`);
        window.setTimeout(() => setUploadNotice(""), 2600);
      } catch (error) {
        setUploadError(
          error instanceof TypeError
            ? "API offline. Inicie o backend para salvar o aparelho."
            : error instanceof Error
              ? error.message
              : "Falha ao salvar o aparelho.",
        );
        setUploadState("error");
      }
      return;
    }
    if (selectedRoomId === "all" || event.target.closest("[data-room-id]"))
      return;
    onRoomSelect("all");
    setShowReference(true);
    resetViewport();
  }

  function saveEstablishmentName() {
    const nextName = nameDraft.trim();
    if (nextName) onEstablishmentNameChange(nextName);
    setEditingName(false);
  }

  function handleWheel(event) {
    updateZoom(event.deltaY < 0 ? 0.12 : -0.12);
  }

  function handlePointerDown(event) {
    if (
      event.target.closest(
        "[data-room-id], .map-controls, .map-toolbar, .device-marker, .charger-popup, .delete-confirm-backdrop, .delete-confirm-modal",
      )
    )
      return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      initial: viewport,
    };
  }

  function handlePointerMove(event) {
    if (chargerDragRef.current) {
      handleChargerMove(event);
      return;
    }
    if (!dragRef.current) return;
    const { startX, startY, initial } = dragRef.current;
    const deltaX = event.clientX - startX;
    const deltaY = event.clientY - startY;
    if (event.shiftKey && selectedRoomId === "all") {
      setViewport((current) => ({
        ...current,
        rotation: initial.rotation + deltaX * 0.45,
      }));
    } else {
      setViewport((current) => ({
        ...current,
        x: initial.x + deltaX,
        y: initial.y + deltaY,
      }));
    }
  }

  function handlePointerUp() {
    if (chargerDragRef.current && uploadedPlan) {
      const { deviceId, initial } = chargerDragRef.current;
      const nextPoint = chargerDragRef.current.preview;
      if (nextPoint) {
        const room = uploadedPlan.rooms.find(
          (candidate) =>
            nextPoint.x >= candidate.bounds.x &&
            nextPoint.x <= candidate.bounds.x + candidate.bounds.width &&
            nextPoint.y >= candidate.bounds.y &&
            nextPoint.y <= candidate.bounds.y + candidate.bounds.height,
        );
        const payload = {
          x: nextPoint.x,
          y: nextPoint.y,
          room_id: room?.id || null,
        };

        updateCharger(uploadedPlan.plan_id, deviceId, payload, ownerId)
          .then(onChargerUpdate)
          .catch(() => {
            setUploadNotice("Não foi possível mover o carregador no mapa.");
            window.setTimeout(() => setUploadNotice(""), 2600);
            onChargerUpdate({
              ...devices.find((device) => device.id === deviceId),
              x: initial.x,
              y: initial.y,
            });
          });
      }
    }
    dragRef.current = null;
    chargerDragRef.current = null;
  }

  function getMapPointFromEvent(event) {
    const svg = planRef.current?.querySelector("svg");
    if (!svg) return null;
    const matrix = svg.getScreenCTM?.();
    if (!matrix) return null;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const transformedPoint = point.matrixTransform(matrix.inverse());
    const viewBox = svg.viewBox.baseVal;
    return {
      x: Math.min(
        viewBox.x + viewBox.width,
        Math.max(viewBox.x, transformedPoint.x),
      ),
      y: Math.min(
        viewBox.y + viewBox.height,
        Math.max(viewBox.y, transformedPoint.y),
      ),
    };
  }

  function beginChargerDrag(event, device) {
    if (!uploadedPlan) return;
    event.preventDefault();
    event.stopPropagation();
    const nextPreview = { x: device.x, y: device.y };
    chargerDragRef.current = {
      deviceId: device.id,
      initial: { x: device.x, y: device.y },
      preview: nextPreview,
    };
    onChargerSelect(device.id);
  }

  function handleChargerMove(event) {
    if (!chargerDragRef.current || !uploadedPlan) return;
    const mapPoint = getMapPointFromEvent(event);
    if (!mapPoint) return;
    const { deviceId, initial } = chargerDragRef.current;
    if (!deviceId) return;
    const nextPreview = {
      x: Number(
        Math.min(Math.max(mapPoint.x, 0), uploadedPlan.width).toFixed(2),
      ),
      y: Number(
        Math.min(Math.max(mapPoint.y, 0), uploadedPlan.height).toFixed(2),
      ),
    };
    chargerDragRef.current = {
      ...chargerDragRef.current,
      initial,
      preview: nextPreview,
    };
    onChargerUpdate({
      ...devices.find((device) => device.id === deviceId),
      x: nextPreview.x,
      y: nextPreview.y,
    });
  }

  async function confirmDelete(targetCharger) {
    if (!targetCharger || !uploadedPlan) return;
    const closeDeleteModal = () => {
      setDeleteTarget(null);
      setDeleteCode("");
      setDeleteError("");
      onChargerSelect(null);
    };

    try {
      if (targetCharger.kind !== "real") {
        try {
          await deleteCharger(
            uploadedPlan.plan_id,
            targetCharger.id,
            "",
            ownerId,
          );
        } catch {
          setUploadNotice("Não foi possível excluir o carregador simulado.");
          window.setTimeout(() => setUploadNotice(""), 2600);
          return;
        }
        onChargerDelete(targetCharger.id);
        closeDeleteModal();
        return;
      }

      const normalizedCode = deleteCode.trim();
      if (!normalizedCode) {
        setDeleteError(
          "Digite o código do carregador para confirmar a exclusão.",
        );
        return;
      }

      try {
        await deleteCharger(
          uploadedPlan.plan_id,
          targetCharger.id,
          normalizedCode,
          ownerId,
        );
      } catch {
        setDeleteError(
          "Código inválido. Verifique o código exibido no carregador.",
        );
        return;
      }

      onChargerDelete(targetCharger.id);
      closeDeleteModal();
    } catch (error) {
      setDeleteError("Não foi possível concluir a exclusão. Tente novamente.");
      console.error("delete charger failed", error);
    }
  }

  const closeDeleteModal = () => {
    setDeleteTarget(null);
    setDeleteCode("");
    setDeleteError("");
    onChargerSelect(null);
  };

  function chargerStatusClass(status) {
    if (status === "charging") return "charging";
    if (["faulted", "offline"].includes(status)) return "fault";
    return "standby";
  }

  function markerPosition(device) {
    const width = planSize.width || uploadedPlan.width;
    const height = planSize.height || uploadedPlan.height;
    const scale = Math.min(
      width / uploadedPlan.width,
      height / uploadedPlan.height,
    );
    const offsetX = (width - uploadedPlan.width * scale) / 2;
    const offsetY = (height - uploadedPlan.height * scale) / 2;
    return {
      left: `${offsetX + device.x * scale}px`,
      top: `${offsetY + device.y * scale}px`,
    };
  }

  return (
    <section className="map-panel panel-frame">
      <div className="map-toolbar">
        <div className="map-title-wrap">
          {editingName && selectedRoomId === "all" ? (
            <input
              className="map-title-input"
              value={nameDraft}
              autoFocus
              onChange={(event) => setNameDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") saveEstablishmentName();
                if (event.key === "Escape") setEditingName(false);
              }}
              onBlur={saveEstablishmentName}
              aria-label="Nome do estabelecimento"
            />
          ) : (
            <span className="map-label">
              {selectedRoomId === "all"
                ? establishmentName
                : `Mapa: ${selectedRoomName || "Cômodo"}`}
            </span>
          )}
          {selectedRoomId === "all" && !editingName && (
            <button
              className="edit-map-title"
              type="button"
              aria-label="Editar nome do estabelecimento"
              onClick={() => {
                setNameDraft(establishmentName);
                setEditingName(true);
              }}
            >
              ✎
            </button>
          )}
        </div>
        <div className="map-upload-control">
          {uploadedPlan && (
            <label className="map-mode-toggle">
              <input
                type="checkbox"
                checked={!showReference}
                onChange={(event) => setShowReference(!event.target.checked)}
              />{" "}
              <span>Somente digital</span>
            </label>
          )}
          <input
            ref={fileInputRef}
            className="map-file-input"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/bmp"
            onChange={handlePlanUpload}
          />
          <button
            className="map-layer-button"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadState === "uploading"}
          >
            {uploadState === "uploading" ? (
              <LoaderCircle className="spin" size={13} />
            ) : (
              <FileUp size={13} />
            )}{" "}
            {uploadState === "uploading" ? "Processando" : "UPLOAD"}
          </button>
        </div>
      </div>
      <div
        ref={canvasRef}
        className="map-canvas"
        aria-label="Mapa visual do estacionamento"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onClick={handleCanvasClick}
      >
        <div className="map-controls" aria-label="Controles do mapa">
          <button
            type="button"
            aria-label="Aumentar zoom"
            onClick={() => updateZoom(0.2)}
          >
            <Plus size={15} />
          </button>
          <button
            type="button"
            aria-label="Diminuir zoom"
            onClick={() => updateZoom(-0.2)}
          >
            <Minus size={15} />
          </button>
          <button
            type="button"
            aria-label="Recentrar e resetar mapa"
            onClick={resetViewport}
          >
            <Maximize2 size={14} />
          </button>
          <button
            type="button"
            aria-label="Abrir opções do mapa"
            aria-expanded={showMapOptions}
            onClick={() => setShowMapOptions((current) => !current)}
          >
            <MoreHorizontal size={15} />
          </button>
          {showMapOptions && (
            <div
              className="map-options"
              role="group"
              aria-label="Opções do mapa"
            >
              <button
                type="button"
                aria-label="Girar mapa 90 graus para a esquerda"
                onClick={() => rotateMap(-90)}
              >
                <RotateCcw size={14} />
              </button>
              <button
                type="button"
                aria-label="Girar mapa 90 graus para a direita"
                onClick={() => rotateMap(90)}
              >
                <RotateCw size={14} />
              </button>
            </div>
          )}
        </div>
        {uploadState === "uploading" ? (
          <div className="map-loading" role="status" aria-live="polite">
            <LoaderCircle className="map-loading-spinner" size={46} />
            <span>Transformando planta em mapa digital...</span>
          </div>
        ) : uploadedPlan ? (
          <div
            ref={(node) => {
              planRef.current = node;
              if (!node) return;
              node.querySelectorAll("[data-room-id]").forEach((roomNode) => {
                const isSelected =
                  selectedRoomId !== "all" &&
                  roomNode.dataset.roomId === selectedRoomId;
                roomNode.classList.toggle("room-selected", isSelected);
                roomNode.classList.toggle(
                  "room-hidden",
                  selectedRoomId !== "all" && !isSelected,
                );
                roomNode.onclick = () => {
                  if (!pendingDevice) onRoomSelect(roomNode.dataset.roomId);
                };
              });
            }}
            className={`digital-plan ${showReference ? "" : "digital-only"} ${selectedRoomId !== "all" ? "room-focused" : ""}`}
            style={{
              ...focusStyle,
              transform: `translate(${viewport.x}px, ${viewport.y}px) rotate(${viewport.rotation}deg) scale(${viewport.scale})`,
            }}
          >
            <div
              className="digital-plan-art"
              dangerouslySetInnerHTML={{ __html: uploadedPlan.svg }}
            />
            <div
              className="device-marker-layer"
              aria-label="Carregadores no mapa"
            >
              {devices
                .filter(
                  (device) =>
                    selectedRoomId === "all" ||
                    device.room_id === selectedRoomId,
                )
                .map((device) => (
                  <button
                    ref={(node) => {
                      if (node) markerRefs.current[device.id] = node;
                      else delete markerRefs.current[device.id];
                    }}
                    className={`device-marker device-status-${chargerStatusClass(device.telemetry?.status)}`}
                    style={markerPosition(device)}
                    type="button"
                    key={device.id}
                    aria-label={`${device.name} - ${device.telemetry?.status || "sem status"}`}
                    onPointerDown={(event) => beginChargerDrag(event, device)}
                    onClick={(event) => {
                      event.stopPropagation();
                      onChargerSelect(device.id);
                    }}
                  >
                    <span className="device-marker-dot" />
                    <span className="device-marker-label">{device.name}</span>
                  </button>
                ))}
            </div>
          </div>
        ) : (
          <div className="map-empty-state">
            <FileUp size={24} />
            <span>Envie uma planta 2D para visualizar o mapa digital.</span>
          </div>
        )}
        {selectedCharger && popupPosition && (
          <div
            className="charger-popup charger-popup-overlay"
            style={{
              left: `${popupPosition.left}px`,
              top: `${popupPosition.top}px`,
            }}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="charger-popup-close"
              aria-label="Fechar dados do carregador"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={() => onChargerSelect(null)}
            >
              ×
            </button>
            <strong>{selectedCharger.name}</strong>
            <span>{selectedCharger.model || "GoodWe HCA G2"}</span>
            <span className="charger-popup-code">
              Código: {selectedCharger.code || "HC2-0000"}
            </span>
            <dl>
              <div>
                <dt>Estado</dt>
                <dd>
                  {selectedCharger.telemetry?.status === "charging"
                    ? "Carregando"
                    : [
                          "available",
                          "preparing",
                          "suspended",
                          "finished",
                        ].includes(selectedCharger.telemetry?.status)
                      ? "Standby"
                      : "Falha"}
                </dd>
              </div>
              <div>
                <dt>Potência</dt>
                <dd>
                  {selectedCharger.telemetry?.power_kw ??
                    selectedCharger.power_kw}{" "}
                  kW
                </dd>
              </div>
              <div>
                <dt>Tensão</dt>
                <dd>{selectedCharger.telemetry?.voltage_v ?? "400"} V</dd>
              </div>
              <div>
                <dt>Corrente</dt>
                <dd>{selectedCharger.telemetry?.current_a ?? "0"} A</dd>
              </div>
              <div>
                <dt>Energia sessão</dt>
                <dd>
                  {selectedCharger.telemetry?.session_energy_kwh ?? "0"} kWh
                </dd>
              </div>
              <div>
                <dt>Energia total</dt>
                <dd>{selectedCharger.telemetry?.energy_kwh ?? "0"} kWh</dd>
              </div>
              <div>
                <dt>Temperatura</dt>
                <dd>{selectedCharger.telemetry?.temperature_c ?? "-"} °C</dd>
              </div>
              <div>
                <dt>Veículo</dt>
                <dd>
                  {selectedCharger.telemetry?.connection_status === "connected"
                    ? "Conectado"
                    : "Desconectado"}
                </dd>
              </div>
            </dl>
            <button
              type="button"
              className="delete-charger-button"
              onClick={() => {
                setDeleteTarget(selectedCharger);
                setDeleteCode("");
                setDeleteError("");
              }}
            >
              Desativar carregador
            </button>
          </div>
        )}
        {deleteTarget && (
          <div
            className="delete-confirm-backdrop"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={closeDeleteModal}
          >
            <div
              className="delete-confirm-modal"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="delete-confirm-close"
                aria-label="Fechar confirmação de desativação"
                onClick={closeDeleteModal}
              >
                ×
              </button>
              <h3>Deseja desativar?</h3>
              <p>
                {deleteTarget.kind === "real"
                  ? "Este aparelho será desativado e continuará disponível no histórico. Para confirmar, digite o código único abaixo."
                  : "Este carregador será desativado e poderá ser consultado posteriormente."}
              </p>
              {deleteTarget.kind === "real" && (
                <div className="delete-code-field">
                  <label htmlFor="delete-code-input">
                    Código do carregador
                  </label>
                  <div className="delete-code-input-shell">
                    <span className="delete-code-hint">
                      {deleteTarget.code || "HC2-0000"}
                    </span>
                    <input
                      id="delete-code-input"
                      type="text"
                      value={deleteCode}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          confirmDelete(deleteTarget);
                        }
                      }}
                      onChange={(event) =>
                        setDeleteCode(event.target.value.toUpperCase())
                      }
                      placeholder=""
                    />
                  </div>
                </div>
              )}
              {deleteError && (
                <p className="delete-confirm-error">{deleteError}</p>
              )}
              <div className="delete-confirm-actions">
                <button type="button" onClick={closeDeleteModal}>
                  Cancelar
                </button>
                <button
                  type="button"
                  className="delete-confirm-primary"
                  onClick={() => confirmDelete(deleteTarget)}
                >
                  Confirmar
                </button>
              </div>
            </div>
          </div>
        )}
        {uploadState === "error" && (
          <p className="map-upload-feedback is-error">{uploadError}</p>
        )}
        {uploadNotice && <p className="map-upload-feedback">{uploadNotice}</p>}
      </div>
    </section>
  );
}

export default ParkingMap;
