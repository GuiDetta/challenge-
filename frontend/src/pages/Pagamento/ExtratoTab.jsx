import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { fetchWallet } from "../../services/api";
import { formatCurrency } from "../../utils/formatters";

const METHOD_LABELS = {
  pix: "Saldo via Pix",
  card: "Saldo via cartão",
  refund: "Estorno de energia não usada",
  charge: "Pagamento de recarga",
};

const dayFormat = new Intl.DateTimeFormat("pt-BR", {
  weekday: "short",
  day: "2-digit",
  month: "short",
});
const timeFormat = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

function describe(transaction) {
  if (METHOD_LABELS[transaction.method]) return METHOD_LABELS[transaction.method];
  return transaction.type === "top_up" ? "Entrada de saldo" : "Débito";
}

function groupByDay(transactions) {
  const groups = [];
  for (const item of transactions) {
    const label = dayFormat.format(new Date(item.created_at));
    const last = groups[groups.length - 1];
    if (last?.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

export default function ExtratoTab() {
  const { user, balance } = useOutletContext();
  const [transactions, setTransactions] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchWallet(user.id)
      .then((wallet) => setTransactions(wallet.transactions))
      .catch((reason) => setError(reason.message));
  }, [user.id, balance]);

  if (error) return <p className="public-error">{error}</p>;
  if (!transactions) return <p className="pay-empty">Carregando extrato...</p>;
  if (transactions.length === 0)
    return (
      <p className="pay-empty">
        Nenhuma movimentação ainda. Adicione saldo na aba Carteira.
      </p>
    );

  const totalIn = transactions
    .filter((item) => item.type === "top_up")
    .reduce((sum, item) => sum + item.amount, 0);
  const totalOut = transactions
    .filter((item) => item.type === "debit")
    .reduce((sum, item) => sum + item.amount, 0);

  return (
    <>
      <section className="pay-totals">
        <div>
          <span>Entradas</span>
          <strong className="pay-in">+ R$ {formatCurrency(totalIn)}</strong>
        </div>
        <div>
          <span>Saídas</span>
          <strong className="pay-out">- R$ {formatCurrency(totalOut)}</strong>
        </div>
      </section>
      {groupByDay(transactions).map((group) => (
        <section key={group.label} className="pay-list">
          <h3>{group.label}</h3>
          <ul>
            {group.items.map((item) => (
              <li key={item.id}>
                <div>
                  <strong>{describe(item)}</strong>
                  <small>{timeFormat.format(new Date(item.created_at))}</small>
                </div>
                <span className={item.type === "top_up" ? "pay-in" : "pay-out"}>
                  {item.type === "top_up" ? "+" : "-"} R${" "}
                  {formatCurrency(item.amount)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
