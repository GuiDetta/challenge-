import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { fetchUserOrders } from "../../services/api";
import { formatCurrency, formatDateTime } from "../../utils/formatters";

const STATUS_LABELS = {
  active: "Em andamento",
  completed: "Concluída",
  pending: "Pendente",
};

export default function HistoricoTab() {
  const { user, balance } = useOutletContext();
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchUserOrders(user.id)
      .then(setOrders)
      .catch((reason) => setError(reason.message));
  }, [user.id, balance]);

  if (error) return <p className="public-error">{error}</p>;
  if (!orders) return <p className="pay-empty">Carregando histórico...</p>;
  if (orders.length === 0)
    return (
      <p className="pay-empty">
        Você ainda não fez nenhuma recarga. Ela aparece aqui depois do primeiro
        pagamento.
      </p>
    );

  const completed = orders.filter((order) => order.status === "completed");
  const energy = completed.reduce((sum, order) => sum + order.energy_kwh, 0);
  const spent = completed.reduce((sum, order) => sum + order.energy_kwh * order.price_per_kwh, 0);

  return (
    <>
      <section className="pay-totals">
        <div>
          <span>Recargas</span>
          <strong>{orders.length}</strong>
        </div>
        <div>
          <span>Energia</span>
          <strong>{energy.toFixed(1).replace(".", ",")} kWh</strong>
        </div>
        <div>
          <span>Gasto</span>
          <strong>R$ {formatCurrency(spent)}</strong>
        </div>
      </section>
      <section className="pay-list">
        <ul>
          {orders.map((order) => (
            <li key={order.id}>
              <div>
                <strong>{order.charger_name || order.charger_code}</strong>
                <small>
                  {formatDateTime(order.created_at)} ·{" "}
                  {order.energy_kwh.toFixed(1).replace(".", ",")} kWh · R${" "}
                  {formatCurrency(order.price_per_kwh)}/kWh
                </small>
              </div>
              <div className="pay-order-side">
                <span>R$ {formatCurrency(order.energy_kwh * order.price_per_kwh)}</span>
                <small className={`pay-order-status ${order.status}`}>
                  {STATUS_LABELS[order.status] || order.status}
                </small>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
