"""Geração dos arquivos que o lojista baixa.

O separador é ponto e vírgula e os números usam vírgula decimal, que é como o
Excel em português abre o arquivo sem pedir configuração. A marca de ordem de
bytes no início existe para o Excel reconhecer o UTF-8 e não quebrar os acentos.
"""

import csv
import io

BYTE_ORDER_MARK = "﻿"


def decimal(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}".replace(".", ",")


def build(header: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return BYTE_ORDER_MARK + buffer.getvalue()


def filename(prefix: str, generated_at: str) -> str:
    stamp = generated_at[:16].replace("-", "").replace(":", "").replace("T", "-")
    return f"ecotwin-{prefix}-{stamp}.csv"
