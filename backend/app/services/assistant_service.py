import json
import os
from datetime import datetime

from app.repositories import Database
from app.schemas import AssistantChatRequest, AssistantChatResponse
from app.services.charger_service import ChargerService


class AssistantService:
    def __init__(self, database: Database, chargers: ChargerService) -> None:
        self.database = database
        self.chargers = chargers

    def context(self, owner_id: str) -> dict:
        self.database.complete_due_orders()
        plans = self.database.list_plans_for_owner(owner_id)
        chargers = []
        for plan in plans:
            for charger in self.database.list_devices(plan["plan_id"], "charger", owner_id, True):
                chargers.append({**charger, "telemetry": self.chargers.snapshot(charger)})
        return {"estabelecimento": "Mapa do estabelecimento", "plantas": [{"plan_id": plan["plan_id"], "rooms": plan["rooms"]} for plan in plans], "carregadores": chargers, "relatorios": self.database.report_summary(owner_id), "pagamentos": self.database.assistant_orders(owner_id)}

    @staticmethod
    def alerts(context: dict) -> list[str]:
        alerts = []
        for charger in context["carregadores"]:
            telemetry = charger.get("telemetry", {})
            if charger.get("active", True) and telemetry.get("status") in {"faulted", "offline"}:
                alerts.append(f"{charger['name']} está em estado {telemetry['status']}.")
        if 18 <= datetime.now().astimezone().hour < 22:
            alerts.append("Horário de pico ativo: a tarifa vigente pode ser maior.")
        return alerts

    @staticmethod
    def local_answer(message: str, context: dict) -> str:
        lowered = message.lower()
        if "quant" in lowered and "carreg" in lowered:
            return f"Você tem {sum(1 for charger in context['carregadores'] if charger.get('active', True))} carregador(es) ativo(s)."
        if "relat" in lowered or "fatur" in lowered:
            report = context["relatorios"]
            return f"O relatório registra R$ {report['revenue_total']:.2f} em receita e {report['month_energy_kwh']:.2f} kWh no mês."
        if "pag" in lowered:
            return f"Encontrei {len(context['pagamentos'])} pagamento(s) ou pedido(s) registrado(s)."
        return "Estou em modo local. Configure OPENAI_API_KEY no backend para ativar o ECOTWIN Chatbot com respostas inteligentes sobre seus dados."

    def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        context = self.context(request.owner_id)
        alerts = self.alerts(context)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return AssistantChatResponse(content=self.local_answer(request.message, context), system_alerts=alerts, provider="local")
        try:
            from openai import OpenAI
            response = OpenAI(api_key=api_key).responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), instructions="Você é o ECOTWIN Chatbot. Responda em português do Brasil, de forma objetiva. Use somente o contexto fornecido. Não invente dados, não revele segredos e diferencie fatos de sugestões.", input=[{"role": "system", "content": f"Contexto privado do lojista em JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"}, *[{"role": item.role, "content": item.content} for item in request.history[-20:]], {"role": "user", "content": request.message}])
            return AssistantChatResponse(content=response.output_text, system_alerts=alerts, provider="openai")
        except Exception:
            return AssistantChatResponse(content="Não consegui acessar o ECOTWIN Chatbot agora. Verifique a configuração da OpenAI e tente novamente.", system_alerts=alerts, provider="local")
