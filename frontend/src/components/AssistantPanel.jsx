import { ArrowUp, Bot, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function formatMessageTime(timestamp) {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(timestamp));
}

function AssistantPanel({ ownerId }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStartedAt, setLoadingStartedAt] = useState(null);

  useEffect(() => {
    if (!ownerId) return undefined;
    let active = true;
    fetch(`${API_URL}/api/assistant/alerts?owner_id=${encodeURIComponent(ownerId)}`)
      .then((response) => (response.ok ? response.json() : { alerts: [] }))
      .then((payload) => {
        if (active) {
          setMessages(
            (payload.alerts || []).map((content) => ({
              role: "system",
              content,
              timestamp: Date.now(),
            })),
          );
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [ownerId]);

  async function submit(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || loading) return;
    const userMessage = {
      role: "user",
      content: message,
      timestamp: Date.now(),
    };
    setDraft("");
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    setLoadingStartedAt(Date.now());
    try {
      const response = await fetch(`${API_URL}/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_id: ownerId,
          message,
          history: messages
            .filter((item) => item.role === "user" || item.role === "assistant")
            .slice(-20),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Falha no terminal.");
      setMessages((current) => [
        ...current,
        ...(payload.system_alerts || []).map((content) => ({
          role: "system",
          content,
          timestamp: Date.now(),
        })),
        { role: "assistant", content: payload.content, timestamp: Date.now() },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: error.message, timestamp: Date.now() },
      ]);
    } finally {
      setLoading(false);
      setLoadingStartedAt(null);
    }
  }

  return (
    <section className="assistant-panel panel-frame">
      <div className="assistant-header">
        <div className="assistant-title">
          <span className="assistant-icon"><Bot size={15} /></span>
          <span>ECOTWIN Chatbot</span>
          <span className="online-mark" />
        </div>
        <button className="icon-button" type="button" aria-label="Configurar assistente">
          <SlidersHorizontal size={16} />
        </button>
      </div>
      <div className="assistant-body">
        {messages.length === 0 && (
          <p className="assistant-intro">Terminal pronto para consultar a operação.</p>
        )}
        {messages.map((message, index) => (
          <div className={`assistant-message message-${message.role}`} key={`${message.role}-${index}`}>
            <span className="message-avatar">
              {message.role === "system" ? "SYS" : message.role === "user" ? "VOCÊ" : "AI"}
            </span>
            <span className="assistant-message-content">
              <span>{message.content}</span>
              <small>
                {message.role === "user" ? "Enviado" : "Recebido"} às {formatMessageTime(message.timestamp)}
              </small>
            </span>
          </div>
        ))}
        {loading && loadingStartedAt && <div className="assistant-message message-assistant"><span className="message-avatar">AI</span><span className="assistant-message-content"><span>Consultando dados...</span><small>Enviado às {formatMessageTime(loadingStartedAt)}</small></span></div>}
      </div>
      <form className="assistant-input" onSubmit={submit}>
        <input value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Mensagem para o assistente" placeholder="Escreva uma pergunta..." disabled={loading} />
        <button type="submit" aria-label="Enviar mensagem" disabled={loading || !draft.trim()}><ArrowUp size={16} /></button>
      </form>
    </section>
  );
}

export default AssistantPanel