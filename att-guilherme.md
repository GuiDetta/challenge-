# Atualização do Guilherme — relatórios de operação e suporte

Guilherme Detta, RM569666. Escrito em 22/09/2026.

Essa atualização pega o gancho do que a GoodWe falou na mentoria de 13/05/2026 e
mexe em um ponto que o projeto ainda não tinha coberto: reduzir o atendimento
que hoje cairia em cima da fabricante. A tela de relatórios só mostrava receita e
consumo; agora ela também responde se o equipamento está funcionando, se a loja
está perto de estourar a potência contratada, quando os carros chegam e o que
fazer quando aparece uma falha.

## O que entrou

### Quatro relatórios novos em `/relatorios`

**Demanda de potência.** Mostra o pico de potência simultânea no período contra
o que a loja tem contratado, com a folga em percentual e o pico de cada dia. É o
painel que fala direto da dor que a GoodWe descreveu como principal, a de estourar
o limite e tomar multa de demanda.

**Disponibilidade por carregador.** Percentual do tempo em operação, carregando,
em falha e offline, por carregador e do conjunto. Responde "meu equipamento está
funcionando", que é a pergunta que vira ligação.

**Falhas com triagem.** Cada falha aparece com origem provável, o que tentar
primeiro e quando escalar. Em vez de "Sobretensão — crítica" e mais nada, o
lojista lê o que fazer. Três das seis falhas passam a ter uma ação que ele
resolve sozinho.

**Ocupação por horário.** Sessões por hora do dia com o pico destacado, energia
média e ticket médio. É a base para sustentar preço por faixa horária, que foi a
dúvida que a própria GoodWe levantou.

Tudo isso vem de um endpoint só, `GET /api/reports/operations`, com os parâmetros
`owner_id`, `days` e `contracted_kw`.

### Download em planilha

Quatro arquivos para baixar, em `GET /api/reports/export/{relatorio}`: financeiro
(uma linha por recarga), disponibilidade, falhas e log de erros. Na tela é uma
barra de botões no topo de `/relatorios`.

O arquivo sai com ponto e vírgula, vírgula decimal e marca de ordem de bytes no
começo. É o que faz o Excel em português abrir com duplo clique, já nas colunas
certas e sem quebrar acento. Vale lembrar que a GoodWe mencionou que o SEMS+ já
exporta relatório da planta em Excel, então isso segue o que o cliente dela já
está acostumado.

### Registro de erros

O backend não tinha nenhuma linha de log. Agora todo erro passa por um handler
que gera um código curto e uma referência única, grava numa tabela nova
(`error_events`) e escreve no log do servidor.

Na prática, quando alguém erra a senha a tela mostra "E-mail ou senha inválidos.
(ECT-401 · ref 44FECD)". O cliente informa essa referência e quem atende acha a
ocorrência. O erro de validação também ficou melhor: antes dizia só "Field
required", agora diz "owner_id: Field required".

## Arquivos

Criados:

- `backend/app/core/errors.py` — os handlers de erro e a geração de código e referência
- `backend/app/services/report_service.py` — a lógica dos quatro relatórios e dos CSV
- `backend/app/services/fault_catalog.py` — a triagem das falhas do HCA G2
- `backend/app/services/csv_export.py` — geração dos arquivos para Excel
- `backend/app/schemas/report.py` — modelos Pydantic dos relatórios

Alterados: `database.py` (consultas novas e a tabela `error_events`),
`report_controller.py`, `main.py`, `container.py`, `schemas/__init__.py`,
`tests/test_api.py`, e no frontend `relatorio.jsx`, `relatorio.css`,
`useReports.js`, `api.js` e `formatters.js`.

## Como testar

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
uvicorn app.main:app --reload --port 8000
```

Frontend em outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

Entrar com uma conta de lojista, subir uma planta, cadastrar carregadores e abrir
`/relatorios`. Os painéis novos ficam abaixo dos antigos, na seção "Como a estação
se comportou".

## O que vocês precisam saber antes de usar

**Os textos da triagem de falhas precisam de revisão.** Eles são conservadores de
propósito, mas foram escritos a partir do nome de cada falha, não do manual.
Antes de mostrar isso para qualquer cliente real, alguém tem que conferir contra
o `GW_HCA-G2_User-Manual-PT.pdf` e o datasheet que estão em `docs/`. Errar uma
orientação sobre falha elétrica é pior do que não dar orientação nenhuma.

**Dois testes falham à noite e não é defeito do teste.** O
`test_charging_order_requires_and_debits_wallet_balance` e o
`test_finishing_order_refunds_undelivered_energy` já falhavam antes dessa
atualização. Eles colocam R$ 25 na carteira e pedem 10 kWh. De dia isso custa
R$ 19,90 e passa; depois das 18h custa R$ 27,90 e o pedido é recusado por saldo
insuficiente.

A causa é que o preço está calculado em dois lugares, no
`order_service.py` e de novo no `pagamento.jsx`, usando o relógio do celular do
motorista. Isso não é só um teste chato: é a mesma regra que vai fazer o valor
exibido divergir do valor cobrado, e divergência de preço na hora de pagar não
termina em orientação, termina em estorno. Acho que vale arrumar antes da
apresentação, deixando o preço só no backend.

**A amostragem da disponibilidade depende do painel estar aberto.** Hoje a
telemetria é gravada a cada leitura da tela, então o histórico é meio um registro
de quem abriu o sistema. Os relatórios contornam isso usando uma amostra por
carregador por minuto, mas o certo mesmo é a telemetria virar tarefa periódica.

**A marca está dividida.** O repositório, o logo e o chatbot dizem EcoTwin; a
página pública do motorista e a rota `/api/chargegrid/{codigo}` dizem ChargeGrid,
que é o nome que usamos nas Sprints 1 e 2. São dois nomes para a mesma coisa.
Vale a gente decidir qual fica antes de apresentar.
