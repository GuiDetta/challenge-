import { Download } from "lucide-react";
import { useState } from "react";

import {
  useErrorLog,
  useOperationsReport,
  useReports,
} from "../../hooks/useReports";
import { downloadReport } from "../../services/api";
import "./relatorio.css";

const EXPORTS = [
  { id: "financeiro", label: "Financeiro" },
  { id: "disponibilidade", label: "Disponibilidade" },
  { id: "falhas", label: "Falhas" },
  { id: "erros", label: "Log de erros" },
];

const money = (value) =>
  `R$ ${Number(value || 0)
    .toFixed(2)
    .replace(".", ",")}`;

const decimal = (value, digits = 1) =>
  Number(value || 0)
    .toFixed(digits)
    .replace(".", ",");

const hourLabel = (hour) => `${String(hour).padStart(2, "0")}h`;

function uptimeTone(percent) {
  if (percent >= 98) return "good";
  if (percent >= 90) return "warn";
  return "bad";
}

export default function Relatorio({ userId }) {
  const { report, error } = useReports(userId);
  const { operations, error: operationsError } = useOperationsReport(userId);
  const errorEvents = useErrorLog(userId);
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
      <ExportBar userId={userId} />
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
          {operationsError && (
            <div className="report-error">{operationsError}</div>
          )}
          {operations && (
            <>
              <header className="page-header operations-header">
                <div>
                  <span className="page-kicker">
                    Operação e atendimento · últimos {operations.days} dias
                  </span>
                  <h1>Como a estação se comportou</h1>
                </div>
                <span className="reports-period">
                  Origem dos dados: {operations.data_source}
                </span>
              </header>
              <section className="reports-grid">
                <AvailabilityPanel data={operations.availability} />
                <DemandPanel data={operations.demand} />
              </section>
              <section className="reports-grid">
                <OccupancyPanel data={operations.occupancy} />
                <FaultsPanel data={operations.faults} />
              </section>
              <section className="reports-grid reports-grid-single">
                <ErrorLogPanel events={errorEvents} />
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}

function AvailabilityPanel({ data }) {
  return (
    <article className="report-panel">
      <PanelTitle
        title="Disponibilidade"
        eyebrow="Tempo em operação"
        unit="%"
      />
      {data.samples === 0 ? (
        <EmptyPanel
          message="Ainda não há leituras suficientes."
          hint="A amostragem acontece enquanto o monitoramento está aberto."
        />
      ) : (
        <>
          <div className="fleet-uptime">
            <strong className={`tone-${uptimeTone(data.fleet_uptime_percent)}`}>
              {decimal(data.fleet_uptime_percent)}%
            </strong>
            <span>
              disponibilidade do conjunto em {data.samples} leituras por minuto
            </span>
          </div>
          <div className="charger-bars">
            {data.chargers.map((charger) => (
              <div className="charger-bar-row" key={charger.charger_id}>
                <div>
                  <strong>{charger.name}</strong>
                  <span>{charger.code}</span>
                </div>
                <div className="bar-track">
                  <i
                    className={`tone-fill-${uptimeTone(charger.uptime_percent)}`}
                    style={{
                      width: `${Math.max(3, charger.uptime_percent)}%`,
                    }}
                  />
                </div>
                <b>{decimal(charger.uptime_percent)}%</b>
              </div>
            ))}
          </div>
          <div className="chart-caption">
            <span>Carregando durante</span>
            <strong>
              {decimal(
                data.chargers.reduce(
                  (total, item) => total + item.charging_percent,
                  0,
                ) / (data.chargers.length || 1),
              )}
              % do tempo
            </strong>
          </div>
        </>
      )}
    </article>
  );
}

function DemandPanel({ data }) {
  const reference = data.contracted_kw || data.installed_kw || 1;
  const maxDay = Math.max(1, ...data.daily.map((item) => item.peak_kw));
  return (
    <article className="report-panel">
      <PanelTitle
        title="Demanda de potência"
        eyebrow="Risco de ultrapassar o contratado"
        unit="kW"
      />
      <div className="demand-headline">
        <div>
          <span>Pico simultâneo</span>
          <strong>{decimal(data.peak_kw, 2)} kW</strong>
          {data.peak_at && (
            <small>
              em {new Date(data.peak_at).toLocaleString("pt-BR").slice(0, 17)}
            </small>
          )}
        </div>
        <div>
          <span>
            {data.contracted_kw ? "Contratado" : "Capacidade instalada"}
          </span>
          <strong>
            {decimal(data.contracted_kw || data.installed_kw, 2)} kW
          </strong>
          {data.headroom_percent !== null && (
            <small>folga de {decimal(data.headroom_percent)}%</small>
          )}
        </div>
      </div>
      <div className="bar-track demand-track">
        <i
          className={
            data.peak_kw / reference > 0.85 ? "tone-fill-bad" : "tone-fill-good"
          }
          style={{
            width: `${Math.min(100, Math.max(3, (data.peak_kw / reference) * 100))}%`,
          }}
        />
      </div>
      {data.daily.length > 0 && (
        <div className="daily-chart demand-chart">
          {data.daily.map((item) => (
            <div className="daily-column" key={item.day}>
              <div
                className="daily-bar demand-bar"
                style={{ height: `${Math.max(4, (item.peak_kw / maxDay) * 100)}%` }}
                title={`${item.peak_kw} kW`}
              />
              <span>{item.day.slice(8)}</span>
            </div>
          ))}
        </div>
      )}
      <div className="chart-caption">
        <span>Pico diário de potência somada</span>
        <strong>
          {data.peak_kw / reference > 0.85
            ? "atenção ao limite"
            : "dentro do limite"}
        </strong>
      </div>
    </article>
  );
}

function OccupancyPanel({ data }) {
  const maxSessions = Math.max(1, ...data.hours.map((item) => item.sessions));
  return (
    <article className="report-panel">
      <PanelTitle
        title="Ocupação por horário"
        eyebrow="Quando os carros chegam"
        unit="sessões"
      />
      {data.total_sessions === 0 ? (
        <EmptyPanel
          message="Nenhuma recarga registrada no período."
          hint="O gráfico se preenche a partir dos pedidos de recarga."
        />
      ) : (
        <>
          <div className="occupancy-chart">
            {data.hours.map((item) => (
              <div className="occupancy-column" key={item.hour}>
                <div
                  className={`occupancy-bar ${item.hour === data.peak_hour ? "occupancy-peak" : ""}`}
                  style={{
                    height: `${Math.max(3, (item.sessions / maxSessions) * 100)}%`,
                  }}
                  title={`${hourLabel(item.hour)} · ${item.sessions} sessão(ões) · ${decimal(item.energy_kwh, 2)} kWh`}
                />
                {item.hour % 3 === 0 && <span>{item.hour}</span>}
              </div>
            ))}
          </div>
          <div className="occupancy-facts">
            <div>
              <span>Horário de pico</span>
              <strong>
                {data.peak_hour === null ? "-" : hourLabel(data.peak_hour)}
              </strong>
              <small>{data.peak_sessions} sessão(ões)</small>
            </div>
            <div>
              <span>Energia média</span>
              <strong>{decimal(data.average_energy_kwh, 2)} kWh</strong>
              <small>por sessão</small>
            </div>
            <div>
              <span>Ticket médio</span>
              <strong>{money(data.average_ticket)}</strong>
              <small>{data.total_sessions} sessão(ões)</small>
            </div>
          </div>
        </>
      )}
    </article>
  );
}

function FaultsPanel({ data }) {
  return (
    <article className="report-panel">
      <PanelTitle
        title="Falhas e o que fazer"
        eyebrow="Triagem antes de abrir chamado"
        unit={`${data.active_alarms} ativo(s)`}
      />
      {data.items.length === 0 ? (
        <EmptyPanel
          message="Nenhuma falha registrada no período."
          hint="Falhas aparecem aqui com a orientação de primeira ação."
        />
      ) : (
        <div className="fault-list">
          {data.items.map((item) => (
            <div className={`fault-row severity-${item.severity}`} key={item.code}>
              <div className="fault-head">
                <strong>{item.title}</strong>
                <span className="fault-count">
                  {item.occurrences}x · {item.chargers} carregador(es)
                </span>
              </div>
              <p className="fault-origin">Origem provável: {item.origin}</p>
              <p className="fault-action">{item.first_action}</p>
              <p className="fault-escalation">{item.escalation}</p>
              {item.active_alarms > 0 && (
                <span className="fault-active">
                  {item.active_alarms} alarme(s) ainda ativo(s)
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function ExportBar({ userId }) {
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState("");

  async function download(report) {
    setBusy(report);
    setFailure("");
    try {
      await downloadReport(report, userId, 30);
    } catch (downloadError) {
      setFailure(downloadError.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="export-bar">
      <div className="export-bar-label">
        <span className="page-kicker">Baixar em planilha</span>
        <small>Últimos 30 dias, arquivo CSV que abre no Excel</small>
      </div>
      <div className="export-buttons">
        {EXPORTS.map((item) => (
          <button
            type="button"
            key={item.id}
            className="export-button"
            onClick={() => download(item.id)}
            disabled={busy !== ""}
          >
            <Download size={13} aria-hidden="true" />
            <span>{busy === item.id ? "Gerando..." : item.label}</span>
          </button>
        ))}
      </div>
      {failure && <p className="export-failure">{failure}</p>}
    </section>
  );
}

function ErrorLogPanel({ events }) {
  return (
    <article className="report-panel">
      <PanelTitle
        title="Log de erros"
        eyebrow="Para informar ao suporte"
        unit={`${events.length} registro(s)`}
      />
      {events.length === 0 ? (
        <EmptyPanel
          message="Nenhum erro registrado nos últimos 7 dias."
          hint="Cada falha ganha um código e uma referência que o suporte usa para achar a ocorrência."
        />
      ) : (
        <div className="error-log">
          {events.map((event) => (
            <div className="error-row" key={event.id}>
              <span className="error-code">{event.code}</span>
              <span className="error-reference">ref {event.reference}</span>
              <span className="error-detail">{event.detail}</span>
              <span className="error-route">
                {event.method} {event.path}
              </span>
              <span className="error-when">
                {new Date(event.occurred_at)
                  .toLocaleString("pt-BR")
                  .slice(0, 17)}
              </span>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function EmptyPanel({ message, hint }) {
  return (
    <div className="panel-empty">
      <p>{message}</p>
      <small>{hint}</small>
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
