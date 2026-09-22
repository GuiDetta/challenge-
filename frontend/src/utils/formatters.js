export function getApiError(payload, fallback) {
  let message = fallback;
  if (typeof payload?.detail === "string") message = payload.detail;
  else if (Array.isArray(payload?.detail)) {
    message = payload.detail
      .map((item) => item?.msg || "Dados inválidos.")
      .join(" ");
  }
  // o código e a referência são o que o cliente informa ao suporte
  if (payload?.code && payload?.reference)
    return `${message} (${payload.code} · ref ${payload.reference})`;
  return message;
}

export function formatCurrency(value) {
  return (Math.round((Number(value) + Number.EPSILON) * 100) / 100)
    .toFixed(2)
    .replace(".", ",");
}

export function formatDateTime(date) {
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

export function getStatusLabel(status) {
  if (status === "charging") return "Carregando";
  if (["available", "preparing", "suspended", "finished"].includes(status))
    return "Standby";
  if (status === "faulted" || status === "offline") return "Falha";
  return "Disponível";
}

export function getLiveSession(charger, currentTime) {
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
    remainingSeconds,
    endsAt: new Date(startedAt.getTime() + totalSeconds * 1000),
    progressPercent: Math.min(
      100,
      Math.floor((elapsedSeconds / totalSeconds) * 100),
    ),
  };
}

export function readStoredUser(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch {
    return null;
  }
}
