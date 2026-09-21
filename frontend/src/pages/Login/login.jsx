import { useState } from "react";

import logo from "../../assets/ecotwin_logo.svg";
import { authUser } from "../../services/api";
import "./login.css";

export default function Login({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setMessage("");
    setLoading(true);
    try {
      const payload = await authUser(
        mode,
        mode === "login" ? form : { ...form, role: "lojista" },
      );
      if (mode === "register") {
        setMode("login");
        setForm({ name: "", email: form.email, password: "" });
        setMessage(
          "Cadastro realizado. Faça login para acessar o monitoramento.",
        );
      } else {
        onAuthenticated(payload);
      }
    } catch (error) {
      setMessage(error.message || "Não foi possível conectar ao servidor.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="monitoring-auth-page">
      <section className="monitoring-auth-brand">
        <img className="auth-logo" src={logo} alt="GoodWe EcoTwin" />
        <h1>Monitoramento de carregadores</h1>
        <p>Entre para acompanhar a operação do seu estabelecimento.</p>
      </section>
      <form className="monitoring-auth-card" onSubmit={submit}>
        <div className="auth-tabs">
          {["login", "register"].map((item) => (
            <button
              key={item}
              type="button"
              className={mode === item ? "active" : ""}
              onClick={() => {
                setMode(item);
                setMessage("");
              }}
            >
              {item === "login" ? "Login" : "Cadastro"}
            </button>
          ))}
        </div>
        <div className="auth-card-heading">
          <span className="page-kicker">Acesso do lojista</span>
          <h2>{mode === "login" ? "Bem-vindo de volta" : "Criar acesso"}</h2>
        </div>
        {mode === "register" && (
          <label>
            Nome
            <input
              required
              minLength="2"
              value={form.name}
              onChange={(event) =>
                setForm({ ...form, name: event.target.value })
              }
            />
          </label>
        )}
        <label>
          E-mail
          <input
            required
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm({ ...form, email: event.target.value })
            }
          />
        </label>
        <label>
          Senha
          <input
            required
            minLength="6"
            type="password"
            value={form.password}
            onChange={(event) =>
              setForm({ ...form, password: event.target.value })
            }
          />
        </label>
        <button className="auth-submit" disabled={loading}>
          {loading
            ? "Aguarde..."
            : mode === "login"
              ? "Entrar no monitoramento"
              : "Criar conta"}
        </button>
        {message && (
          <p
            className={
              message.startsWith("Cadastro realizado")
                ? "auth-success"
                : "auth-error"
            }
          >
            {message}
          </p>
        )}
      </form>
    </main>
  );
}
