import { useReports } from "../../hooks/useReports";
import "./relatorio.css";

const money = (value) =>
  `R$ ${Number(value || 0)
    .toFixed(2)
    .replace(".", ",")}`;

export default function Relatorio({ userId }) {
  const { report, error } = useReports(userId);
  const maxEnergy = Math.max(
    1,
    ...(report?.chargers || []).map((item) => Number(item.energy_kwh || 0)),
  );
  const maxDaily = Math.max(
    1,
    ...(report?.daily || []).map((item) => Number(item.energy_kwh || 0)),
  );

  return (
    <div className="page-shell reports-shell">
      <header className="page-header">
        <div>
          <span className="page-kicker">Visão financeira e energética</span>
          <h1>Relatórios</h1>
        </div>
        <span className="reports-period">Mês atual</span>
      </header>
      {error && <div className="report-error">{error}</div>}
      {!report ? (
        <div className="empty-page-card">
          <p>Carregando dados...</p>
        </div>
      ) : (
        <>
          <section className="report-kpis">
            <Kpi
              label="Carregadores ativos"
              value={report.charger_count}
              note="Equipamentos reais cadastrados"
            />
            <Kpi
              label="Consumo no mês"
              value={`${Number(report.month_energy_kwh).toFixed(1).replace(".", ",")} kWh`}
              note="Energia solicitada pelos clientes"
            />
            <Kpi
              label="Receita no mês"
              value={money(report.month_revenue)}
              note="Pagamentos confirmados"
            />
            <Kpi
              label="Receita acumulada"
              value={money(report.revenue_total)}
              note="Saldo gerado pelos clientes"
              accent
            />
          </section>
          <section className="reports-grid">
            <article className="report-panel">
              <PanelTitle
                title="Consumo por carregador"
                eyebrow="Distribuição"
                unit="kWh"
              />
              <div className="charger-bars">
                {report.chargers.slice(0, 12).map((item) => (
                  <div className="charger-bar-row" key={item.code}>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.code}</span>
                    </div>
                    <div className="bar-track">
                      <i
                        style={{
                          width: `${Math.max(3, (Number(item.energy_kwh) / maxEnergy) * 100)}%`,
                        }}
                      />
                    </div>
                    <b>{Number(item.energy_kwh).toFixed(1)}</b>
                  </div>
                ))}
              </div>
            </article>
            <article className="report-panel">
              <PanelTitle
                title="Energia e receita"
                eyebrow="Últimos 7 dias"
                unit="kWh"
              />
              <div className="daily-chart">
                {report.daily.map((item) => (
                  <div className="daily-column" key={item.day}>
                    <div
                      className="daily-bar"
                      style={{
                        height: `${Math.max(4, (Number(item.energy_kwh) / maxDaily) * 100)}%`,
                      }}
                      title={`${item.energy_kwh} kWh`}
                    />
                    <span>{item.day.slice(8)}</span>
                  </div>
                ))}
              </div>
              <div className="chart-caption">
                <span>Energia entregue</span>
                <strong>
                  {Number(report.generated_energy_kwh)
                    .toFixed(1)
                    .replace(".", ",")}{" "}
                  kWh monitorados
                </strong>
              </div>
            </article>
          </section>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, note, accent }) {
  return (
    <div className={`report-kpi ${accent ? "report-kpi-accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function PanelTitle({ eyebrow, title, unit }) {
  return (
    <div className="report-panel-heading">
      <div>
        <span className="page-kicker">{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      <span className="report-unit">{unit}</span>
    </div>
  );
}
