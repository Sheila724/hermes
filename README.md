<div align="center">
  <h1>🤖 Hermes Agent</h1>
  <h3>Automação de monitoramento de e-mail com SLA, dashboard e relatórios</h3>
  <p><i>Python &nbsp;•&nbsp; IMAP &nbsp;•&nbsp; Google Sheets API &nbsp;•&nbsp; WhatsApp &nbsp;•&nbsp; cron</i></p>
</div>

## 📖 Visão Geral

Hermes é um sistema de automação em **Python** que opera uma caixa de suporte de e-mail de ponta a ponta — do recebimento da mensagem ao relatório gerencial. Roda continuamente em uma VM e foi o projeto que mais me aproximou de práticas de **SRE**: monitoramento contínuo, alertas de SLA, gestão de plantão e foco em resiliência.

> 🔒 Repositório com versão **sanitizada** para fins de portfólio: sem dados internos, identificadores de pessoas, endereços reais ou credenciais.

## 🏗️ Arquitetura

> 📐 *Diagrama*

```
        ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
        │  Caixa IMAP  │ ──▶ │  Monitor (cron) │ ──▶ │  Classificação   │
        └──────────────┘     └─────────────────┘     │  (spam/categoria/│
                                                      │   status)        │
                                                      └────────┬─────────┘
                                                               │
                    ┌──────────────────────────────────────────┼───────────────────────┐
                    ▼                          ▼                ▼                        ▼
            ┌───────────────┐        ┌─────────────────┐  ┌───────────┐        ┌─────────────────┐
            │ Google Sheets │        │ Alertas de SLA  │  │ Dashboard │        │   Relatórios    │
            │   (logging)   │        │   (WhatsApp)    │  │    web    │        │ diário/sem/mês  │
            └───────────────┘        └─────────────────┘  └───────────┘        └─────────────────┘
```

## ⚙️ Funcionalidades

**Monitoramento em tempo real (IMAP)**
Processa e-mails novos via cron com controle **idempotente** por UID — o ponteiro de leitura só avança após a gravação ser confirmada no destino, evitando registros perdidos ou duplicados.

**Classificação automática**
Filtra spam e mensagens de teste por regras configuráveis, categoriza por área e determina o status do atendimento (respondido, pendente, aguardando retorno).

**Alertas de SLA**
Em horário comercial, dispara aviso via WhatsApp após 2h sem resposta e repete a cada 1h enquanto o caso permanece pendente.

**Gestão de plantão (on-call)**
Rotação automática do responsável da semana, com ordem pré-definida.

**Logging e dashboard**
Registra os atendimentos em Google Sheets (via API) e alimenta um dashboard web com gráficos de volume, status, categorias e tempo médio de atendimento.

**Relatórios automatizados**
Gera e envia relatórios em HTML — diário, semanal e mensal — por e-mail.

## 🧠 Decisões de Engenharia

O foco do projeto não é só "funcionar", e sim **funcionar de forma confiável**:

- **Idempotência:** o estado de leitura (`last_uid`) só avança após confirmação de sucesso na gravação — sem isso, uma falha intermitente geraria e-mails órfãos ou duplicados.
- **Resiliência:** detecção e *refresh* automático de token OAuth do Google, caminho de *fallback* para envio de notificação quando o canal principal falha.
- **Defensividade:** descarte total de mensagens de gateways de spam (sem ruído em log/alerta) e regras explícitas para nunca bloquear remetentes legítimos.
- **Observabilidade:** dashboard e relatórios dão visibilidade de volume, gargalos e SLA em tempo quase real.

## 🗂️ Estrutura (exemplo)

> *Nomes genéricos  ajuste para os seus.*

| Script | Função |
|---|---|
| `email_monitor.py` | Processa e-mails novos e classifica |
| `sla_alert.py` | Verifica e dispara alertas de SLA |
| `reports.py` | Gera e envia relatórios (diário/semanal/mensal) |
| `oncall_rotation.py` | Define/avança o responsável da semana |
| `dashboard_data.py` | Gera o JSON que alimenta o dashboard |
| `whatsapp_notify.py` | Envia notificação via WhatsApp |
| `sheets_auth.py` | Renova o token do Google Sheets |

## 🛠️ Stack

<div align="center">
  <img src="https://skillicons.dev/icons?i=python,linux" />
</div>

Python · IMAP · Google Sheets API · integração WhatsApp · cron · HTML/JS (dashboard)

## ▶️ Como rodar

> *Esqueleto — adapte ao seu ambiente.*

```bash
# 1. Configurar variáveis de ambiente (nunca commite credenciais)
cp .env.example .env
# editar .env com suas credenciais

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Executar manualmente
python3 email_monitor.py

# 4. Agendar via cron (exemplo: a cada 5 min)
*/5 * * * * /usr/bin/python3 /caminho/email_monitor.py
```

---

<div align="center">
  <i>Confiabilidade primeiro — um e-mail processado por vez.</i>
</div>
