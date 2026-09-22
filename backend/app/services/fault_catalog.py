"""Catálogo de triagem das falhas do HCA G2.

As orientações são conservadoras de propósito: quando há qualquer dúvida sobre a
instalação elétrica, o encaminhamento é o instalador. Os textos devem ser
revisados contra o manual e o datasheet em `docs/` antes de uso com cliente real.
"""

from typing import Literal

Severity = Literal["info", "warning", "critical"]

CATALOG: dict[int, dict[str, str]] = {
    1: {
        "title": "Falha de comunicação CAN",
        "severity": "warning",
        "origin": "Interna do carregador",
        "first_action": "Reinicie o carregador pelo disjuntor e aguarde um minuto.",
        "escalation": "Se repetir após o reinício, acione o instalador.",
    },
    2: {
        "title": "Sobretensão",
        "severity": "critical",
        "origin": "Rede elétrica do estabelecimento",
        "first_action": "Interrompa o uso e verifique se outros equipamentos da loja oscilam.",
        "escalation": "Acione o instalador; pode ser necessário abrir chamado na distribuidora.",
    },
    4: {
        "title": "Sobrecorrente",
        "severity": "critical",
        "origin": "Veículo ou cabo",
        "first_action": "Encerre a sessão e teste a mesma vaga com outro veículo.",
        "escalation": "Se falhar também com o segundo veículo, acione o instalador.",
    },
    8: {
        "title": "Subtensão",
        "severity": "warning",
        "origin": "Rede elétrica ou demanda simultânea alta",
        "first_action": "Confira quantos carregadores estão em uso ao mesmo tempo.",
        "escalation": "Recorrente em horário de pico indica revisão da demanda contratada.",
    },
    16: {
        "title": "Falha de conexão do cabo",
        "severity": "warning",
        "origin": "Conector ou entrada do veículo",
        "first_action": "Reencaixe o conector até travar e reinicie a sessão.",
        "escalation": "Se repetir em veículos diferentes, o cabo precisa de troca.",
    },
    32: {
        "title": "Falha de aterramento",
        "severity": "critical",
        "origin": "Instalação elétrica",
        "first_action": "Não insista na recarga. Interrompa o uso da vaga.",
        "escalation": "Acione o instalador antes de liberar o carregador novamente.",
    },
}

UNKNOWN = {
    "title": "Falha não catalogada",
    "severity": "warning",
    "origin": "Não identificada",
    "first_action": "Reinicie o carregador e registre o código exibido.",
    "escalation": "Abra chamado informando o código e o horário da ocorrência.",
}


def describe(code: int) -> dict[str, str]:
    return CATALOG.get(code, UNKNOWN)
