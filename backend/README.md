# GoodWe EV Plan API

API em FastAPI para processar uma planta baixa 2D e retornar um mapa vetorial consumível pelo frontend.

## Executar

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Documentação interativa: http://127.0.0.1:8000/docs

## Endpoints

- `GET /health`
- `POST /api/plans` com campo multipart `file`
- `GET /api/plans/{plan_id}`
- `GET /api/plans/{plan_id}/devices`
- `POST /api/plans/{plan_id}/devices`
- `DELETE /api/plans/{plan_id}/devices/{device_id}`
- `POST /api/plans/{plan_id}/chargers`
- `GET /api/plans/{plan_id}/chargers`
- `GET /api/plans/{plan_id}/chargers/{charger_id}/telemetry`
- `GET /api/plans/{plan_id}/chargers/{charger_id}/telemetry/history`
- `GET /api/plans/{plan_id}/alarms?active_only=true`
- `GET /api/plans/{plan_id}/sessions`
- `POST /api/plans/{plan_id}/simulation/tick`

O processamento usa OpenCV para detectar áreas fechadas e paredes. O OCR usa `pytesseract`; além do pacote Python, o executável Tesseract precisa estar instalado no sistema. Sem ele, a API continua funcionando e retorna `ocr_available: false` com um aviso.

Os dados são armazenados localmente em `backend/data` para facilitar o desenvolvimento inicial. Em produção, substitua `LocalStore` por um banco de dados e armazenamento de arquivos.

O banco SQLite `backend/data/goodwe.sqlite3` contém plantas, cômodos, dispositivos, snapshots de telemetria, sessões e alarmes. A simulação segue o domínio do HCA G2: estados operacionalmente relevantes, potência de 7/11/22 kW, tensão monofásica/trifásica, corrente, energia acumulada, energia da sessão, temperatura, conexão do veículo, falhas e alarmes. O campo `source` diferencia `mock`, `modbus` e `ocpp` para a futura troca do simulador por integração real.

### Fluxo de um carregador no mapa

1. Faça o upload da planta em `POST /api/plans` e guarde o `plan_id`.
2. Crie o ponto físico em `POST /api/plans/{plan_id}/chargers`, informando `x`, `y`, `room_id`, modelo e potência.
3. Consulte `GET /api/plans/{plan_id}/chargers` para receber cada ponto com a telemetria simulada atual.
4. Consulte o histórico em `/telemetry/history`, alarmes em `/alarms` e sessões em `/sessions`.
5. Use `/simulation/tick` para gerar uma nova leitura simulada para os carregadores da planta.

Os valores simulados foram modelados a partir do datasheet e do mapa MODBUS HCA G2. Eles não representam conexão real com um equipamento e devem ser substituídos por um adaptador MODBUS TCP ou OCPP quando o hardware estiver disponível.
