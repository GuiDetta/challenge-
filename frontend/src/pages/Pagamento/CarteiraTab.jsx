import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import QRCode from "qrcode";
import { Copy, CreditCard, QrCode } from "lucide-react";

import { WALLET_TOP_UP_AMOUNTS } from "../../config";
import { topUpWallet } from "../../services/api";
import { formatCurrency } from "../../utils/formatters";

// código fictício: o pagamento é simulado e nada sai daqui para um banco
function fakePixCode(userId, amount) {
  const value = amount.toFixed(2);
  return `00020126360014BR.GOV.BCB.PIX0114CHARGEGRID-SIM5204000053039865406${value}5802BR5910CHARGEGRID6009SAO PAULO62140510${userId.slice(0, 10).toUpperCase()}6304SIMU`;
}

function onlyDigits(value, max) {
  return value.replace(/\D/g, "").slice(0, max);
}

export default function CarteiraTab() {
  const { user, balance, refreshBalance } = useOutletContext();
  const [amount, setAmount] = useState(25);
  const [method, setMethod] = useState("pix");
  const [step, setStep] = useState("choose");
  const [message, setMessage] = useState(null);
  const [sending, setSending] = useState(false);

  async function confirmPayment() {
    setSending(true);
    setMessage(null);
    try {
      await topUpWallet(user.id, amount, method);
      await refreshBalance();
      setStep("choose");
      setMessage({
        type: "success",
        text: `R$ ${formatCurrency(amount)} adicionados via ${method === "pix" ? "Pix" : "cartão"}.`,
      });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <section className="pay-panel pay-form">
        <div className="pay-panel-heading">
          <h2>Adicionar saldo</h2>
          <span className="pay-sim-badge">Pagamento simulado</span>
        </div>
        {step === "choose" ? (
          <>
            <span className="pay-label">Valor</span>
            <div className="pay-chips" role="group" aria-label="Valor">
              {WALLET_TOP_UP_AMOUNTS.map((value) => (
                <button
                  key={value}
                  type="button"
                  className={amount === value ? "selected" : ""}
                  onClick={() => setAmount(value)}
                >
                  R$ {value}
                </button>
              ))}
            </div>
            <span className="pay-label">Forma de pagamento</span>
            <div className="pay-methods" role="radiogroup">
              <button
                type="button"
                role="radio"
                aria-checked={method === "pix"}
                className={method === "pix" ? "selected" : ""}
                onClick={() => setMethod("pix")}
              >
                <QrCode size={22} aria-hidden="true" />
                <strong>Pix</strong>
                <small>Cai na hora</small>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={method === "card"}
                className={method === "card" ? "selected" : ""}
                onClick={() => setMethod("card")}
              >
                <CreditCard size={22} aria-hidden="true" />
                <strong>Cartão</strong>
                <small>Crédito ou débito</small>
              </button>
            </div>
            <p className="pay-hint">
              Saldo depois do pagamento: R$ {formatCurrency(balance + amount)}
            </p>
            <button
              type="button"
              className="public-primary"
              onClick={() => {
                setMessage(null);
                setStep(method);
              }}
            >
              Continuar
            </button>
          </>
        ) : step === "pix" ? (
          <PixStep
            code={fakePixCode(user.id, amount)}
            amount={amount}
            sending={sending}
            onConfirm={confirmPayment}
            onBack={() => setStep("choose")}
          />
        ) : (
          <CardStep
            amount={amount}
            sending={sending}
            onConfirm={confirmPayment}
            onBack={() => setStep("choose")}
          />
        )}
      </section>
      {message && (
        <p className={message.type === "error" ? "public-error" : "public-success"}>
          {message.text}
        </p>
      )}
    </>
  );
}

function PixStep({ code, amount, sending, onConfirm, onBack }) {
  const [qrSource, setQrSource] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    QRCode.toDataURL(code, { margin: 1, width: 220 })
      .then(setQrSource)
      .catch(() => setQrSource(""));
  }, [code]);

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <>
      <p className="pay-step-title">
        Pague R$ {formatCurrency(amount)} com o app do seu banco
      </p>
      {qrSource && (
        <img className="pay-pix-qr" src={qrSource} alt="QR Code Pix simulado" />
      )}
      <button type="button" className="public-secondary pay-copy" onClick={copyCode}>
        <Copy size={16} aria-hidden="true" />
        {copied ? "Código copiado" : "Copiar código Pix"}
      </button>
      <button
        type="button"
        className="public-primary"
        onClick={onConfirm}
        disabled={sending}
      >
        {sending ? "Confirmando..." : "Já paguei"}
      </button>
      <button type="button" className="public-text-button" onClick={onBack}>
        Voltar
      </button>
    </>
  );
}

function CardStep({ amount, sending, onConfirm, onBack }) {
  const [card, setCard] = useState({ number: "", holder: "", expiry: "", cvv: "" });
  const expiryDigits = onlyDigits(card.expiry, 4);
  const month = Number(expiryDigits.slice(0, 2));
  const valid =
    card.number.length >= 13 &&
    card.holder.trim().length > 2 &&
    expiryDigits.length === 4 &&
    month >= 1 &&
    month <= 12 &&
    card.cvv.length >= 3;

  function submit(event) {
    event.preventDefault();
    if (valid) onConfirm();
  }

  return (
    <form className="pay-form" onSubmit={submit}>
      <p className="pay-step-title">
        Pagar R$ {formatCurrency(amount)} no cartão
      </p>
      <label>
        Número do cartão
        <input
          inputMode="numeric"
          autoComplete="cc-number"
          placeholder="0000 0000 0000 0000"
          value={card.number.replace(/(\d{4})(?=\d)/g, "$1 ")}
          onChange={(event) =>
            setCard({ ...card, number: onlyDigits(event.target.value, 19) })
          }
        />
      </label>
      <label>
        Nome impresso
        <input
          autoComplete="cc-name"
          value={card.holder}
          onChange={(event) =>
            setCard({ ...card, holder: event.target.value.toUpperCase() })
          }
        />
      </label>
      <div className="pay-form-row">
        <label>
          Validade
          <input
            inputMode="numeric"
            autoComplete="cc-exp"
            placeholder="MM/AA"
            value={expiryDigits.replace(/^(\d{2})(\d)/, "$1/$2")}
            onChange={(event) =>
              setCard({ ...card, expiry: event.target.value })
            }
          />
        </label>
        <label>
          CVV
          <input
            inputMode="numeric"
            autoComplete="cc-csc"
            value={card.cvv}
            onChange={(event) =>
              setCard({ ...card, cvv: onlyDigits(event.target.value, 4) })
            }
          />
        </label>
      </div>
      <small className="pay-hint">
        Simulação: os dados do cartão não são enviados nem guardados.
      </small>
      <button className="public-primary" disabled={!valid || sending}>
        {sending ? "Processando..." : `Pagar R$ ${formatCurrency(amount)}`}
      </button>
      <button type="button" className="public-text-button" onClick={onBack}>
        Voltar
      </button>
    </form>
  );
}
