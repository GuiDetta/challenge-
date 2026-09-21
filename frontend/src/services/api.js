import { API_URL } from "../config";
import { getApiError } from "../utils/formatters";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      getApiError(payload, "Não foi possível concluir a operação."),
    );
  return payload;
}

export function authUser(mode, form) {
  return request(`/api/auth/${mode === "register" ? "register" : "login"}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      mode === "register" ? { ...form, role: "lojista" } : form,
    ),
  });
}

export function fetchPlan(ownerId, savedPlanId) {
  const path = savedPlanId
    ? `/api/plans/${encodeURIComponent(savedPlanId)}?owner_id=${encodeURIComponent(ownerId)}`
    : `/api/plans?owner_id=${encodeURIComponent(ownerId)}`;
  return request(path).then((plan) => (Array.isArray(plan) ? plan[0] : plan));
}

export function fetchChargers(planId, ownerId) {
  return request(
    `/api/plans/${planId}/chargers?owner_id=${encodeURIComponent(ownerId)}`,
  );
}

export function fetchOwnedChargers(ownerId) {
  return request(`/api/chargers?owner_id=${encodeURIComponent(ownerId)}`);
}

export function fetchPublicCharger(code, userId) {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request(`/api/chargegrid/${encodeURIComponent(code)}${query}`);
}

export function fetchReport(ownerId) {
  return request(
    `/api/reports/summary?owner_id=${encodeURIComponent(ownerId)}`,
  );
}

export function fetchAssistantAlerts(ownerId) {
  return request(
    `/api/assistant/alerts?owner_id=${encodeURIComponent(ownerId)}`,
  );
}

export function sendAssistantMessage(payload) {
  return request("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadPlan(file, ownerId) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/plans", {
    method: "POST",
    headers: { "X-User-Id": ownerId || "" },
    body: formData,
  });
}

export function createCharger(planId, charger, ownerId) {
  return request(`/api/plans/${planId}/chargers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": ownerId || "",
    },
    body: JSON.stringify(charger),
  });
}

export function fetchChargerTelemetry(planId, chargerId) {
  return request(`/api/plans/${planId}/chargers/${chargerId}/telemetry`);
}

export function updateCharger(planId, chargerId, updates, ownerId) {
  return request(`/api/plans/${planId}/chargers/${chargerId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-User-Id": ownerId || "" },
    body: JSON.stringify(updates),
  });
}

export function deleteCharger(planId, chargerId, code, ownerId) {
  return request(
    `/api/plans/${planId}/chargers/${chargerId}?code=${encodeURIComponent(code || "")}`,
    {
      method: "DELETE",
      headers: { "X-User-Id": ownerId || "" },
    },
  );
}

export function topUpWallet(userId, amount) {
  return request("/api/wallet/top-ups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, amount }),
  });
}

export function createChargingOrder(order) {
  return request("/api/charging-orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order),
  });
}

export function finishChargingOrder(orderId, payload) {
  return request(`/api/charging-orders/${orderId}/finish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
