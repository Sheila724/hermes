"""Render do relatório periódico no padrão visual da Com4 Data Center.

Paleta e tipografia extraídas do site oficial (com4.com.br):
laranja de marca #e77600 -> #f29e04 (gradiente), texto #595959, borda #e2e2e2.
"""

COM4_LOGO_URL = "https://com4.com.br/frontend/img/main/logo.png"

_STYLE = """
<style>
  .c4-report {
    font-family: 'Goldplay Alt', 'Segoe UI', system-ui, -apple-system, Roboto, Arial, sans-serif;
    max-width: 720px;
    margin: 0 auto;
    color: #2b2b2b;
    background: #f4f5f6;
  }
  .c4-report * { box-sizing: border-box; }

  .c4-header {
    background: #ffffff;
    border-radius: 18px 18px 0 0;
    border-bottom: 4px solid transparent;
    border-image: linear-gradient(90deg, #e77600, #f29e04) 1;
    padding: 26px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    box-shadow: 0 2px 10px rgba(20, 20, 20, 0.05);
  }
  .c4-header img { height: 38px; display: block; }
  .c4-header-meta { text-align: right; }
  .c4-header-meta .eyebrow {
    margin: 0; font-size: 11px; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #e77600;
  }
  .c4-header-meta h1 {
    margin: 4px 0 0; font-size: 21px; font-weight: 800; color: #1f1f1f;
  }
  .c4-header-meta p {
    margin: 6px 0 0; font-size: 12.5px; color: #8a8a8a;
  }

  .c4-body { background: #ffffff; padding: 30px 32px; }

  .c4-section-title {
    display: flex; align-items: center; justify-content: space-between;
    margin: 0 0 16px;
  }
  .c4-section-title h2 {
    font-size: 13px; text-transform: uppercase; letter-spacing: .06em;
    color: #6b6b6b; margin: 0; font-weight: 800;
    border-left: 3px solid #e77600; padding-left: 10px;
  }
  .c4-section { margin-bottom: 32px; }
  .c4-section:last-child { margin-bottom: 0; }

  .c4-badge {
    font-size: 12px; font-weight: 700; padding: 5px 14px; border-radius: 20px;
    display: inline-block; border: 1px solid currentColor; letter-spacing: .02em;
  }

  .c4-kpis {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px;
  }
  .c4-kpi {
    background: #fafafa; border: 1px solid #ededed; border-radius: 14px;
    padding: 16px; transition: box-shadow .2s ease;
  }
  .c4-kpi:hover { box-shadow: 0 4px 14px rgba(0,0,0,.06); }
  .c4-kpi .label {
    margin: 0 0 8px; font-size: 10.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .04em; color: #8a8a8a;
  }
  .c4-kpi .value { margin: 0; font-size: 26px; font-weight: 800; color: #1f1f1f; }
  .c4-kpi.accent {
    background: linear-gradient(145deg, #e77600 0%, #f29e04 100%);
    border-color: transparent;
  }
  .c4-kpi.accent .label { color: rgba(255,255,255,.85); }
  .c4-kpi.accent .value { color: #ffffff; }

  .c4-progress-track {
    background: #ececec; border-radius: 8px; height: 8px; overflow: hidden; margin-bottom: 22px;
  }
  .c4-progress-fill {
    display: block; height: 100%; border-radius: 8px;
    background: linear-gradient(90deg, #e77600, #f29e04);
  }

  .c4-panel {
    background: #fafafa; border: 1px solid #ededed; border-radius: 14px; padding: 8px 18px;
  }
  .c4-panel-label {
    font-size: 11.5px; color: #8a8a8a; margin: 0 0 10px; font-weight: 800;
    text-transform: uppercase; letter-spacing: .03em;
  }

  .c4-rank-row {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 4px; border-bottom: 1px solid #eaeaea;
  }
  .c4-rank-row:last-child { border-bottom: none; }
  .c4-rank-pos {
    width: 22px; flex: 0 0 22px; font-size: 12px; font-weight: 800; color: #b3b3b3; text-align: center;
  }
  .c4-rank-row.top .c4-rank-pos { color: #e77600; }
  .c4-rank-name { flex: 0 0 28%; font-size: 13px; color: #1f1f1f; font-weight: 600; }
  .c4-rank-row.top .c4-rank-name { font-weight: 800; }
  .c4-rank-bar-track {
    flex: 1; background: #ececec; border-radius: 6px; height: 8px; overflow: hidden;
  }
  .c4-rank-bar-fill {
    display: block; height: 100%; border-radius: 6px;
    background: linear-gradient(90deg, #e77600, #f29e04);
  }
  .c4-rank-qty { flex: 0 0 32px; text-align: right; font-size: 13px; font-weight: 800; color: #1f1f1f; }

  .c4-empty { color: #a3a3a3; font-size: 13px; margin: 6px 4px; font-style: italic; }

  .c4-footer {
    background: #1c1c1f; border-radius: 0 0 18px 18px; padding: 20px 32px; text-align: center;
  }
  .c4-footer p { margin: 0; font-size: 11px; color: #9c9c9c; }
  .c4-footer p strong { color: #f29e04; }
  .c4-footer .tagline { margin-top: 5px; font-size: 10px; color: #5c5c60; }

  @media (max-width: 480px) {
    .c4-kpis { grid-template-columns: repeat(2, 1fr); }
    .c4-rank-name { flex-basis: 38%; }
  }
</style>
"""


def render_ranking_html(d, label_total, color=None):
    if not d:
        return f'<p class="c4-empty">Nenhum {label_total} no período.</p>'
    ordenado = sorted(d.items(), key=lambda x: x[1], reverse=True)
    maximo = ordenado[0][1] if ordenado else 1
    linhas = ""
    for i, (nome, qtd) in enumerate(ordenado):
        pct = round(100 * qtd / maximo) if maximo else 0
        top = " top" if i == 0 else ""
        linhas += f"""
        <div class="c4-rank-row{top}">
          <span class="c4-rank-pos">{i + 1}º</span>
          <span class="c4-rank-name">{nome}</span>
          <span class="c4-rank-bar-track"><span class="c4-rank-bar-fill" style="width:{pct}%;"></span></span>
          <span class="c4-rank-qty">{qtd}</span>
        </div>"""
    return linhas


def render_health_badge(taxa_resposta):
    """Badge visual indicando a saúde geral do atendimento."""
    if taxa_resposta >= 90:
        cor, bg, label = "#1f7a3d", "#eafaf0", "Excelente"
    elif taxa_resposta >= 70:
        cor, bg, label = "#b8650a", "#fff4e8", "Atenção"
    else:
        cor, bg, label = "#c0392b", "#fdeeec", "Crítico"
    return f'<span class="c4-badge" style="color:{cor};background:{bg};">{label}</span>'


def render_html(report):
    taxa_resposta = 0
    base = report["total_emails"] - report.get("aguardando_atendente", 0)
    if base > 0:
        taxa_resposta = round(100 * report["respondidos"] / base)

    html = f"""
    {_STYLE}
    <div class="c4-report">

      <div class="c4-header">
        <img src="{COM4_LOGO_URL}" alt="COM4 Data Center">
        <div class="c4-header-meta">
          <p class="eyebrow">Relatório {report['periodo_label']}</p>
          <h1>Atendimento por E-mail</h1>
          <p>{report['data_inicio'].strftime('%d/%m/%Y')} a {report['data_fim'].strftime('%d/%m/%Y')}</p>
        </div>
      </div>

      <div class="c4-body">

        <div class="c4-section">
          <div class="c4-section-title">
            <h2>Visão geral do período</h2>
            {render_health_badge(taxa_resposta)}
          </div>

          <div class="c4-kpis">
            <div class="c4-kpi">
              <p class="label">Recebidos</p>
              <p class="value">{report['total_emails']}</p>
            </div>
            <div class="c4-kpi">
              <p class="label">Respondidos</p>
              <p class="value">{report['respondidos']}</p>
            </div>
            <div class="c4-kpi">
              <p class="label">Pendentes</p>
              <p class="value">{report['pendentes']}</p>
            </div>
            <div class="c4-kpi">
              <p class="label">Aguardando retorno</p>
              <p class="value">{report.get('aguardando_atendente', 0)}</p>
            </div>
            <div class="c4-kpi accent">
              <p class="label">Taxa de resposta</p>
              <p class="value">{taxa_resposta}%</p>
            </div>
          </div>

          <div class="c4-progress-track">
            <div class="c4-progress-fill" style="width:{taxa_resposta}%;"></div>
          </div>

          <p class="c4-panel-label">Ranking de atendimentos</p>
          <div class="c4-panel">
            {render_ranking_html(report['por_atendente'], 'atendimento')}
          </div>
        </div>

      </div>

      <div class="c4-footer">
        <p>Relatório gerado automaticamente pelo <strong>Hermes</strong> · COM4 Data Center</p>
        <p class="tagline">Conectado com o que importa: você.</p>
      </div>
    </div>
    """
    return html
