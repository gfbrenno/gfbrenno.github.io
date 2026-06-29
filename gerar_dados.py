"""
gerar_dados.py
==============
Gera um dashboard_final.html completo com os dados embutidos.
Basta abrir o HTML no navegador — sem servidor, sem JSON separado.

Uso:
    python gerar_dados.py

Requisitos: Python 3.6+  (sem dependências externas)

ESTRUTURA SUPORTADA:
  Claro: base/[ano]/[nome_livre]/         ← atividades de 2025
         base/[nome_livre]/               ← atividades de 2026 (sem subpasta de ano)

  Gilat: base/[ano]/[DD-MM-YYYY]/         ← atividades de 2025
         base/[DD-MM-YYYY]/               ← atividades de 2026 (sem subpasta de ano)

  Vivo:  base/[ano]/[pasta_dia]/[*.zip]   ← atividades de 2025
         base/[pasta_dia]/[*.zip]         ← atividades de 2026 (sem subpasta de ano)
"""

import os
import re
import json
import zipfile
from datetime import datetime

# ── Configuração ──────────────────────────────────────────────────────────────
PASTAS = {
    "Claro": r"C:\Users\brenno.fonseca\Documents\Encora\Atividades JM",
    "Gilat": r"C:\Users\brenno.fonseca\Documents\Encora\Gilat Peru",
    "Vivo":  r"C:\Users\brenno.fonseca\Documents\Encora\VIVO",
}

OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

ANO_MIN = 2020
ANO_MAX = 2030
ANO_RAIZ = "2026"   # ano assumido para itens soltos na raiz

# ── Helpers de data ───────────────────────────────────────────────────────────

def valida_data(ano, mes, dia):
    try:
        ano, mes, dia = int(ano), int(mes), int(dia)
        if not (ANO_MIN <= ano <= ANO_MAX): return None
        if not (1 <= mes <= 12):            return None
        if not (1 <= dia <= 31):            return None
        datetime(ano, mes, dia)
        return f"{ano:04d}-{mes:02d}-{dia:02d}"
    except (ValueError, TypeError):
        return None

def date_from_name(name):
    """Extrai data apenas de nomes com separadores explícitos (- ou /)."""
    # DD-MM-YYYY
    m = re.search(r'(?<!\d)(\d{2})[-/](\d{2})[-/](\d{4})(?!\d)', name)
    if m:
        iso = valida_data(m.group(3), m.group(2), m.group(1))
        if iso: return iso
    # YYYY-MM-DD
    m = re.search(r'(?<!\d)(\d{4})[-/](\d{2})[-/](\d{2})(?!\d)', name)
    if m:
        iso = valida_data(m.group(1), m.group(2), m.group(3))
        if iso: return iso
    return None

def date_from_zip(path):
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            infos = zf.infolist()
            if infos:
                dt = infos[0].date_time
                iso = valida_data(dt[0], dt[1], dt[2])
                if iso: return iso
    except Exception:
        pass
    return None

def date_from_fs(path):
    stat = os.stat(path)
    ts = stat.st_ctime if os.name == "nt" else stat.st_mtime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

def date_from_dir(path):
    """
    Percorre recursivamente `path` e retorna a data do arquivo com
    st_mtime mais recente. Fallback: st_mtime da própria pasta.

    Usa st_mtime (última modificação) em vez de st_ctime (criação), porque
    o Windows redefine st_ctime ao copiar arquivos para um novo computador,
    enquanto st_mtime preserva a data original do conteúdo.
    """
    IGNORADOS = {'.ds_store', 'thumbs.db', 'desktop.ini'}
    latest_ts = None

    try:
        for raiz, _, arquivos in os.walk(path):
            for nome in arquivos:
                if nome.lower() in IGNORADOS:
                    continue
                try:
                    ts = os.stat(os.path.join(raiz, nome)).st_mtime
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts
                except OSError:
                    pass
    except OSError:
        pass

    if latest_ts is None:
        # Pasta vazia ou inacessível → usa mtime da própria pasta
        latest_ts = os.stat(path).st_mtime

    return datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d")

def is_ano_folder(name):
    """Verifica se o nome é uma pasta de ano (ex: '2025', '2026')."""
    return name.isdigit() and len(name) == 4 and ANO_MIN <= int(name) <= ANO_MAX

# ── Extração de roteador ──────────────────────────────────────────────────────

# Palavras-sufixo conhecidas (sem underscore): aparecem após _ e não fazem parte
# do código do roteador. A comparação é case-insensitive.
_PALAVRAS_SUFIXO = {
    'antes', 'durante', 'depois', 'apos', 'pos', 'pre',
    'postupgrade', 'preupgrade',
    'full', 'backup', 'bkp', 'final', 'old', 'new',
    'result', 'log', 'config', 'before', 'after',
    'conferir', 'verificar', 'testar', 'teste', 'ping',
    'epipe', 'correcao', 'corrigir', 'ajuste', 'ajustar',
}

def extrair_roteador(nome_arquivo):
    """
    Extrai o nome do roteador a partir do nome de um arquivo .txt.

    Passo 1 — divide pelo '_' e aceita segmentos enquanto não forem texto livre
              nem palavras-sufixo conhecidas.
    Passo 2 — no resultado do passo 1, remove sufixos por hífen também:
              MSPKS01-RMP01-ANTES   → MSPKS01-RMP01
              MSSTQ01-RMP01-DURANTE → MSSTQ01-RMP01
              MSTCU01-RMP01-DEPOIS  → MSTCU01-RMP01
    """
    nome = os.path.splitext(nome_arquivo)[0].strip()

    # Passo 1: cortar pelo '_'
    partes = nome.split('_')
    aceitos = []
    for parte in partes:
        try:
            parte.encode('ascii')
        except UnicodeEncodeError:
            break
        if ' ' in parte:
            break
        if parte.lower() in _PALAVRAS_SUFIXO:
            break
        aceitos.append(parte)
    resultado = '_'.join(aceitos) if aceitos else nome

    # Passo 2: cortar sufixos por hífen no final do resultado
    # Ex: MSPKS01-RMP01-ANTES → dividir por '-', remover sufixos do final
    segmentos = resultado.split('-')
    while segmentos and segmentos[-1].lower() in _PALAVRAS_SUFIXO:
        segmentos.pop()
    resultado = '-'.join(segmentos) if segmentos else resultado

    return resultado

# Padrão mínimo de hostname: deve conter pelo menos um hífen, todos os segmentos
# separados por hífen devem ser curtos (≤10 chars) e sem espaços.
# Isso descarta nomes descritivos como "Configurar BGP para ativação do roteador X".
_RE_HOSTNAME = re.compile(r'^[A-Za-z0-9]+(-[A-Za-z0-9]{1,10})+$')

def _parece_roteador(nome):
    """Retorna True se o nome tem estrutura de hostname (ex: GOPWL03-RMP01, i-br-sp-spo-hl3-01)."""
    return bool(_RE_HOSTNAME.match(nome))

def roteadores_da_pasta(path):
    """
    Varre `path` (zip ou pasta) procurando arquivos .txt e retorna o
    conjunto de nomes de roteadores únicos encontrados.
    """
    roteadores = set()

    def _processar(nome):
        if nome.lower().endswith('.txt'):
            r = extrair_roteador(nome)
            if r and _parece_roteador(r):
                roteadores.add(r)

    if path.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                for info in zf.infolist():
                    _processar(os.path.basename(info.filename))
        except Exception:
            pass
    else:
        try:
            for raiz, _, arquivos in os.walk(path):
                for nome in arquivos:
                    _processar(nome)
        except OSError:
            pass

    return roteadores


# ── Claro ─────────────────────────────────────────────────────────────────────

def ler_claro(base):
    """
    Lê atividades da Claro:
    - base/[ano]/[nome_livre]/   → atividades com subpasta de ano
    - base/[nome_livre]/         → atividades na raiz (2026)

    Data: extraída do nome se possível; caso contrário, usa date_from_dir()
    que busca o st_mtime mais recente entre todos os arquivos da pasta,
    evitando o problema de st_ctime redefinido ao trocar de notebook.
    """
    atividades = []
    if not os.path.isdir(base):
        print(f"[AVISO] Pasta Claro não encontrada: {base}")
        return atividades

    for item in sorted(os.listdir(base)):
        item_path = os.path.join(base, item)
        if not os.path.isdir(item_path):
            continue

        if is_ano_folder(item):
            # Subpasta de ano → iterar atividades dentro
            ano = item
            for sub in sorted(os.listdir(item_path)):
                sub_path = os.path.join(item_path, sub)
                if os.path.isdir(sub_path):
                    atividades.append({
                        "cliente": "Claro",
                        "atividade": sub,
                        "data": date_from_name(sub) or date_from_dir(sub_path),  # ← corrigido
                        "ano": ano,
                        "caminho": sub_path,
                        "roteadores": sorted(roteadores_da_pasta(sub_path)),
                    })
        else:
            # Item solto na raiz → atividade de 2026
            atividades.append({
                "cliente": "Claro",
                "atividade": item,
                "data": date_from_name(item) or date_from_dir(item_path),  # ← corrigido
                "ano": ANO_RAIZ,
                "caminho": item_path,
                "roteadores": sorted(roteadores_da_pasta(item_path)),
            })

    return atividades

# ── Helper compartilhado: Gilat e Vivo ───────────────────────────────────────

def processar_pasta_dia(cliente, dia, dia_path, ano):
    """
    Processa uma pasta de dia que contém arquivos .zip como atividades.
    Cada .zip é uma atividade; o nome do zip (sem extensão) é o nome da atividade.
    A data é extraída do nome da pasta pai (DD-MM-YYYY); fallback: metadado do zip
    e, por último, data de modificação do arquivo.
    Se não houver zips, registra a pasta de dia como atividade única.
    """
    resultado = []
    data_pasta = date_from_name(dia) or date_from_fs(dia_path)
    zips = sorted([f for f in os.listdir(dia_path) if f.lower().endswith(".zip")])

    if zips:
        for z in zips:
            z_path = os.path.join(dia_path, z)
            nome = os.path.splitext(z)[0]
            data = data_pasta or date_from_zip(z_path) or date_from_fs(z_path)
            resultado.append({
                "cliente": cliente,
                "atividade": nome,
                "data": data,
                "ano": ano,
                "caminho": z_path,
                "roteadores": sorted(roteadores_da_pasta(z_path)),
            })
    else:
        # Pasta sem zips → a própria pasta de dia é a atividade
        resultado.append({
            "cliente": cliente,
            "atividade": dia,
            "data": data_pasta or date_from_fs(dia_path),
            "ano": ano,
            "caminho": dia_path,
            "roteadores": sorted(roteadores_da_pasta(dia_path)),
        })
    return resultado

# ── Gilat ─────────────────────────────────────────────────────────────────────

def ler_gilat(base):
    """
    Lê atividades da Gilat:
    - base/[ano]/[DD-MM-YYYY]/[*.zip]   → atividades com subpasta de ano
    - base/[DD-MM-YYYY]/[*.zip]         → atividades na raiz (2026)

    Cada .zip dentro da pasta de dia é uma atividade distinta.
    """
    atividades = []
    if not os.path.isdir(base):
        print(f"[AVISO] Pasta Gilat não encontrada: {base}")
        return atividades

    for item in sorted(os.listdir(base)):
        item_path = os.path.join(base, item)
        if not os.path.isdir(item_path):
            continue

        if is_ano_folder(item):
            # Subpasta de ano → iterar pastas de dia dentro
            ano = item
            for dia in sorted(os.listdir(item_path)):
                dia_path = os.path.join(item_path, dia)
                if os.path.isdir(dia_path):
                    atividades += processar_pasta_dia("Gilat", dia, dia_path, ano)
        else:
            # Pasta de dia solta na raiz → 2026
            atividades += processar_pasta_dia("Gilat", item, item_path, ANO_RAIZ)

    return atividades

# ── Vivo ──────────────────────────────────────────────────────────────────────

def ler_vivo(base):
    """
    Lê atividades da Vivo:
    - base/[ano]/[pasta_dia]/[*.zip]   → atividades com subpasta de ano
    - base/[pasta_dia]/[*.zip]         → atividades na raiz (2026)

    Cada .zip dentro da pasta de dia é uma atividade distinta.
    """
    atividades = []
    if not os.path.isdir(base):
        print(f"[AVISO] Pasta Vivo não encontrada: {base}")
        return atividades

    for item in sorted(os.listdir(base)):
        item_path = os.path.join(base, item)
        if not os.path.isdir(item_path):
            continue

        if is_ano_folder(item):
            # Subpasta de ano → iterar pastas de dia dentro
            ano = item
            for dia in sorted(os.listdir(item_path)):
                dia_path = os.path.join(item_path, dia)
                if os.path.isdir(dia_path):
                    atividades += processar_pasta_dia("Vivo", dia, dia_path, ano)
        else:
            # Pasta de dia solta na raiz → 2026
            atividades += processar_pasta_dia("Vivo", item, item_path, ANO_RAIZ)

    return atividades

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dashboard de Atividades — Encora</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:#0f1117; --surface:#181c25; --border:#252a36; --text:#e4e8f0; --muted:#6b748a;
      --claro:#ef4444; --claro-dim:#ef444420;
      --gilat:#3b82f6; --gilat-dim:#3b82f620;
      --vivo:#a855f7;  --vivo-dim:#a855f720;
      --radius:10px;
    }
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    body { background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif; min-height:100vh; padding:0 0 60px; }
    header { background:var(--surface); border-bottom:1px solid var(--border); padding:28px 40px 24px; display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap; }
    .header-title .eyebrow { font-size:11px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); display:block; margin-bottom:4px; }
    .header-title h1 { font-size:26px; font-weight:700; letter-spacing:-.02em; }
    .header-meta { font-size:12px; color:var(--muted); font-family:'JetBrains Mono',monospace; text-align:right; }
    main { max-width:1280px; margin:0 auto; padding:36px 40px 0; }
    .kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:32px; }
    .kpi { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px 22px; display:flex; flex-direction:column; gap:6px; position:relative; overflow:hidden; }
    .kpi::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; }
    .kpi.total::before { background:linear-gradient(90deg,var(--claro),var(--vivo)); }
    .kpi.claro::before { background:var(--claro); }
    .kpi.gilat::before { background:var(--gilat); }
    .kpi.vivo::before  { background:var(--vivo); }
    .kpi-label { font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
    .kpi-value { font-size:38px; font-weight:700; letter-spacing:-.03em; line-height:1; }
    .kpi.total .kpi-value { color:var(--text); }
    .kpi.claro .kpi-value { color:var(--claro); }
    .kpi.gilat .kpi-value { color:var(--gilat); }
    .kpi.vivo  .kpi-value { color:var(--vivo); }
    .kpi-sub { font-size:12px; color:var(--muted); }
    .charts-grid { display:grid; grid-template-columns:340px 1fr; gap:20px; margin-bottom:32px; }
    .chart-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:24px; }
    .chart-card h2 { font-size:13px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin-bottom:20px; }
    .filters { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:18px 22px; display:flex; flex-wrap:wrap; gap:14px; align-items:center; margin-bottom:16px; }
    .filters label { font-size:12px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-right:4px; }
    .filters select, .filters input[type="text"] { background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--text); font-family:inherit; font-size:13px; padding:6px 10px; outline:none; transition:border-color .15s; }
    .filters select:focus, .filters input[type="text"]:focus { border-color:var(--claro); }
    .filter-group { display:flex; align-items:center; gap:6px; }
    .btn-clear { background:transparent; border:1px solid var(--border); border-radius:6px; color:var(--muted); cursor:pointer; font-size:12px; padding:6px 12px; transition:all .15s; font-family:inherit; }
    .btn-clear:hover { border-color:var(--text); color:var(--text); }
    .table-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
    .table-header { padding:18px 22px 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border); }
    .table-header h2 { font-size:13px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
    .table-count { font-size:12px; color:var(--muted); font-family:'JetBrains Mono',monospace; }
    .table-scroll { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; font-size:13.5px; }
    thead th { background:var(--bg); padding:12px 16px; text-align:left; font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); white-space:nowrap; cursor:pointer; user-select:none; transition:color .15s; }
    thead th:hover { color:var(--text); }
    thead th .sort-icon { margin-left:4px; opacity:.4; }
    thead th.active .sort-icon { opacity:1; }
    tbody tr { border-top:1px solid var(--border); transition:background .1s; }
    tbody tr:hover { background:rgba(255,255,255,.03); }
    tbody td { padding:13px 16px; vertical-align:middle; }
    .badge { display:inline-block; border-radius:20px; font-size:11px; font-weight:600; padding:3px 10px; letter-spacing:.04em; }
    .badge-claro { background:var(--claro-dim); color:var(--claro); }
    .badge-gilat { background:var(--gilat-dim); color:var(--gilat); }
    .badge-vivo  { background:var(--vivo-dim);  color:var(--vivo); }
    .date-mono { font-family:'JetBrains Mono',monospace; font-size:12.5px; color:var(--muted); }
    .atividade-name { max-width:460px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block; }
    #empty-state { text-align:center; padding:60px 20px; color:var(--muted); }
    #empty-state h3 { font-size:16px; font-weight:500; margin-bottom:8px; color:var(--text); }
    .pagination { display:flex; align-items:center; justify-content:flex-end; gap:8px; padding:14px 18px; border-top:1px solid var(--border); }
    .page-btn { background:transparent; border:1px solid var(--border); border-radius:6px; color:var(--muted); cursor:pointer; font-family:inherit; font-size:12px; padding:5px 11px; transition:all .15s; }
    .page-btn:hover:not(:disabled) { border-color:var(--text); color:var(--text); }
    .page-btn.active { background:var(--claro); border-color:var(--claro); color:#000; font-weight:600; }
    .page-btn:disabled { opacity:.3; cursor:default; }
    .heatmap-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:24px; margin-bottom:32px; }
    .heatmap-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; margin-bottom:20px; }
    .heatmap-header h2 { font-size:13px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
    .heatmap-controls { display:flex; align-items:center; gap:10px; }
    .heatmap-controls select { background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--text); font-family:inherit; font-size:12px; padding:4px 8px; outline:none; }
    .heatmap-controls select:focus { border-color:var(--claro); }
    .heatmap-wrap { overflow-x:auto; padding-bottom:4px; display:flex; justify-content:center; }
    .heatmap-grid { display:flex; gap:3px; align-items:flex-start; }
    .heatmap-labels-day { display:flex; flex-direction:column; gap:3px; margin-right:4px; padding-top:22px; }
    .heatmap-day-label { font-size:10px; color:var(--muted); font-family:'JetBrains Mono',monospace; height:12px; line-height:12px; }
    .heatmap-col { display:flex; flex-direction:column; gap:3px; }
    .heatmap-month-label { font-size:10px; color:var(--muted); font-family:'JetBrains Mono',monospace; height:16px; line-height:16px; margin-bottom:2px; white-space:nowrap; }
    .heatmap-cell { width:12px; height:12px; border-radius:2px; cursor:default; flex-shrink:0; }
    .heatmap-cell[data-count="0"] { background:#1e2433; }
    .heatmap-cell[data-level="1"] { background:#1d4022; }
    .heatmap-cell[data-level="2"] { background:#286230; }
    .heatmap-cell[data-level="3"] { background:#39a047; }
    .heatmap-cell[data-level="4"] { background:#4cc75a; }
    .heatmap-cell.future { background:#151820; cursor:default; }
    .heatmap-footer { display:flex; align-items:center; justify-content:space-between; margin-top:14px; flex-wrap:wrap; gap:8px; margin-left:auto; margin-right:auto; }
    .heatmap-legend { display:flex; align-items:center; gap:6px; }
    .heatmap-legend span { font-size:11px; color:var(--muted); }
    .heatmap-legend-cells { display:flex; gap:3px; }
    .heatmap-legend-cell { width:12px; height:12px; border-radius:2px; }
    .heatmap-stat { font-size:12px; color:var(--muted); font-family:'JetBrains Mono',monospace; }
    .hm-tooltip { position:fixed; background:#0a0d13; border:1px solid var(--border); border-radius:6px; padding:7px 11px; font-size:12px; color:var(--text); pointer-events:none; z-index:9999; white-space:nowrap; display:none; }
    .rt-tooltip { position:fixed; background:#0a0d13; border:1px solid var(--border); border-radius:8px; padding:10px 14px; font-size:12px; color:var(--text); pointer-events:none; z-index:9999; display:none; max-width:320px; }
    .rt-tooltip-title { font-size:11px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }
    .rt-tooltip-list { display:flex; flex-direction:column; gap:4px; }
    .rt-tooltip-item { font-family:'JetBrains Mono',monospace; font-size:11.5px; color:var(--text); white-space:nowrap; }
    .rcount { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:22px; border-radius:5px; font-size:11px; font-weight:600; font-family:'JetBrains Mono',monospace; cursor:default; }
    .rcount-zero { color:var(--muted); }
    .rcount-some { background:rgba(245,158,11,.12); color:#f59e0b; border:1px solid rgba(245,158,11,.25); }
    .hm-tooltip strong { color:var(--text); font-weight:600; }
    .hm-tooltip .hm-tt-muted { color:var(--muted); }
    .router-kpi { border-top:3px solid #f59e0b !important; }
    .router-kpi .kpi-value { color:#f59e0b !important; }
    @media(max-width:900px){ main{padding:24px 20px 0;} header{padding:20px;} .kpi-row{grid-template-columns:repeat(2,1fr);} .charts-grid{grid-template-columns:1fr;} }
  </style>
</head>
<body>
<header>
  <div class="header-title">
    <span class="eyebrow">Encora · Brenno Fonseca</span>
    <h1>Dashboard de Atividades</h1>
  </div>
  <div class="header-meta" id="meta-gerado"></div>
</header>
<main>
  <div class="kpi-row" style="grid-template-columns:repeat(5,1fr)">
    <div class="kpi total"><span class="kpi-label">Total</span><span class="kpi-value" id="kpi-total">0</span><span class="kpi-sub" id="kpi-period"></span></div>
    <div class="kpi claro"><span class="kpi-label">Claro</span><span class="kpi-value" id="kpi-claro">0</span><span class="kpi-sub">Brasil</span></div>
    <div class="kpi gilat"><span class="kpi-label">Gilat</span><span class="kpi-value" id="kpi-gilat">0</span><span class="kpi-sub">Peru</span></div>
    <div class="kpi vivo"><span class="kpi-label">Vivo</span><span class="kpi-value" id="kpi-vivo">0</span><span class="kpi-sub">Brasil</span></div>
    <div class="kpi router-kpi"><span class="kpi-label">Roteadores</span><span class="kpi-value" id="kpi-routers">0</span><span class="kpi-sub">únicos acessados</span></div>
  </div>
  <div class="charts-grid">
    <div class="chart-card"><h2>Distribuição por cliente</h2><div style="position:relative;height:240px"><canvas id="chartPie"></canvas></div></div>
    <div class="chart-card"><h2>Atividades por mês</h2><div style="position:relative;height:240px"><canvas id="chartBar"></canvas></div></div>
  </div>
  <div class="heatmap-card">
    <div class="heatmap-header">
      <h2>Contribuições por dia</h2>
      <div class="heatmap-controls">
        <select id="hm-cliente"><option value="">Todos os clientes</option><option value="Claro">Claro</option><option value="Gilat">Gilat</option><option value="Vivo">Vivo</option></select>
        <select id="hm-ano"></select>
      </div>
    </div>
    <div class="heatmap-wrap"><div class="heatmap-grid" id="heatmap-grid"></div></div>
    <div class="heatmap-footer">
      <span class="heatmap-stat" id="hm-stat"></span>
      <div class="heatmap-legend">
        <span>Menos</span>
        <div class="heatmap-legend-cells">
          <div class="heatmap-legend-cell" style="background:#1e2433"></div>
          <div class="heatmap-legend-cell" style="background:#1d4022"></div>
          <div class="heatmap-legend-cell" style="background:#286230"></div>
          <div class="heatmap-legend-cell" style="background:#39a047"></div>
          <div class="heatmap-legend-cell" style="background:#4cc75a"></div>
        </div>
        <span>Mais</span>
      </div>
    </div>
  </div>
  <div id="hm-tooltip" class="hm-tooltip"></div>
  <div id="rt-tooltip" class="rt-tooltip"><div class="rt-tooltip-title" id="rt-tt-title"></div><div class="rt-tooltip-list" id="rt-tt-list"></div></div>

  <div class="filters">
    <div class="filter-group"><label for="f-cliente">Cliente</label>
      <select id="f-cliente"><option value="">Todos</option><option value="Claro">Claro</option><option value="Gilat">Gilat</option><option value="Vivo">Vivo</option></select></div>
    <div class="filter-group"><label for="f-ano">Ano</label><select id="f-ano"><option value="">Todos</option></select></div>
    <div class="filter-group"><label for="f-mes">Mês</label>
      <select id="f-mes"><option value="">Todos</option><option value="01">Janeiro</option><option value="02">Fevereiro</option><option value="03">Março</option><option value="04">Abril</option><option value="05">Maio</option><option value="06">Junho</option><option value="07">Julho</option><option value="08">Agosto</option><option value="09">Setembro</option><option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option></select></div>
    <div class="filter-group"><label for="f-busca">Buscar</label><input type="text" id="f-busca" placeholder="nome da atividade…" style="min-width:200px"/></div>
    <div class="filter-group"><label for="f-roteador">Roteador</label><input type="text" id="f-roteador" placeholder="hostname…" style="min-width:180px"/></div>
    <button class="btn-clear" id="btn-clear">Limpar filtros</button>
  </div>
  <div class="table-card">
    <div class="table-header"><h2>Atividades</h2><span class="table-count" id="table-count"></span></div>
    <div class="table-scroll">
      <table>
        <thead><tr>
          <th data-col="data" class="active">Data <span class="sort-icon">↓</span></th>
          <th data-col="cliente">Cliente <span class="sort-icon">↕</span></th>
          <th data-col="atividade">Atividade <span class="sort-icon">↕</span></th>
          <th data-col="ano">Ano <span class="sort-icon">↕</span></th>
          <th style="text-align:center;cursor:default">Roteadores</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div id="empty-state" style="display:none"><h3>Nenhuma atividade encontrada</h3><p>Tente ajustar os filtros.</p></div>
    <div class="pagination" id="pagination" style="display:none"></div>
  </div>
</main>
<script>
const PAYLOAD = __PAYLOAD__;
const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
let ALL = PAYLOAD.atividades || [];
let filtered = [...ALL];
let sortCol = 'data', sortDir = -1, page = 1;
const PER_PAGE = 25;

function formatDate(iso) { const [y,m,d]=iso.split('-'); return d+'/'+m+'/'+y; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function updateKPIs() {
  document.getElementById('kpi-total').textContent = ALL.length;
  document.getElementById('kpi-claro').textContent = ALL.filter(a=>a.cliente==='Claro').length;
  document.getElementById('kpi-gilat').textContent = ALL.filter(a=>a.cliente==='Gilat').length;
  document.getElementById('kpi-vivo').textContent  = ALL.filter(a=>a.cliente==='Vivo').length;
  document.getElementById('meta-gerado').textContent = 'Gerado em ' + new Date(PAYLOAD.gerado_em).toLocaleString('pt-BR');
  const dates = ALL.map(a=>a.data).sort();
  if (dates.length) document.getElementById('kpi-period').textContent = formatDate(dates[0]) + ' → ' + formatDate(dates[dates.length-1]);
}

function populateAno() {
  const anos = [...new Set(ALL.map(a=>a.ano))].sort((a,b)=>b-a);
  const sel = document.getElementById('f-ano');
  anos.forEach(a => { const o=document.createElement('option'); o.value=a; o.textContent=a; sel.appendChild(o); });
}

function applyFilters() {
  const cliente   = document.getElementById('f-cliente').value;
  const ano       = document.getElementById('f-ano').value;
  const mes       = document.getElementById('f-mes').value;
  const busca     = document.getElementById('f-busca').value.toLowerCase().trim();
  const roteador  = document.getElementById('f-roteador').value.toLowerCase().trim();
  filtered = ALL.filter(a => {
    if (cliente  && a.cliente !== cliente) return false;
    if (ano      && a.ano !== ano)         return false;
    if (mes      && a.data.split('-')[1] !== mes) return false;
    if (busca    && !a.atividade.toLowerCase().includes(busca)) return false;
    if (roteador && !(a.roteadores || []).some(r => r.toLowerCase().includes(roteador))) return false;
    return true;
  });
  sortData(); page = 1; renderTable(); renderPagination();
}

['f-cliente','f-ano','f-mes'].forEach(id => document.getElementById(id).addEventListener('change', applyFilters));
document.getElementById('f-busca').addEventListener('input', applyFilters);
document.getElementById('f-roteador').addEventListener('input', applyFilters);
document.getElementById('btn-clear').addEventListener('click', () => {
  ['f-cliente','f-ano','f-mes'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-busca').value = '';
  document.getElementById('f-roteador').value = '';
  applyFilters();
});

function sortData() {
  filtered.sort((a,b) => { const va=a[sortCol]||'',vb=b[sortCol]||''; return va<vb?-sortDir:va>vb?sortDir:0; });
}
document.querySelectorAll('thead th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    const col=th.dataset.col;
    if (sortCol===col) sortDir*=-1; else { sortCol=col; sortDir=-1; }
    document.querySelectorAll('thead th').forEach(t=>t.classList.remove('active'));
    th.classList.add('active');
    th.querySelector('.sort-icon').textContent = sortDir===-1?'↓':'↑';
    sortData(); renderTable(); renderPagination();
  });
});

function renderTable() {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  document.getElementById('empty-state').style.display = filtered.length ? 'none' : 'block';
  document.getElementById('table-count').textContent = filtered.length + ' atividade' + (filtered.length!==1?'s':'');

  const rtTooltip = document.getElementById('rt-tooltip');
  const rtTitle   = document.getElementById('rt-tt-title');
  const rtList    = document.getElementById('rt-tt-list');

  filtered.slice((page-1)*PER_PAGE, page*PER_PAGE).forEach(a => {
    const tr  = document.createElement('tr');
    const cls = a.cliente.toLowerCase();
    const rots = a.roteadores || [];
    const n    = rots.length;

    // Células base
    const tdData = document.createElement('td');
    tdData.className = 'date-mono';
    tdData.textContent = formatDate(a.data);

    const tdCliente = document.createElement('td');
    tdCliente.innerHTML = `<span class="badge badge-${cls}">${esc(a.cliente)}</span>`;

    const tdAtiv = document.createElement('td');
    tdAtiv.innerHTML = `<span class="atividade-name" title="${esc(a.atividade)}">${esc(a.atividade)}</span>`;

    const tdAno = document.createElement('td');
    tdAno.className = 'date-mono';
    tdAno.textContent = a.ano;

    // Célula de roteadores
    const tdRot = document.createElement('td');
    tdRot.style.cssText = 'text-align:center;';
    const badge = document.createElement('span');
    badge.className = n > 0 ? 'rcount rcount-some' : 'rcount rcount-zero';
    badge.textContent = n > 0 ? n : '—';
    tdRot.appendChild(badge);

    if (n > 0) {
      function positionRtTooltip(e) {
        const tw = rtTooltip.offsetWidth  || 280;
        const th = rtTooltip.offsetHeight || 40;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const gap = 14;
        // Horizontal: vai para a esquerda se não cabe à direita
        const left = (e.clientX + gap + tw > vw)
          ? e.clientX - tw - gap
          : e.clientX + gap;
        // Vertical: vai para cima se não cabe abaixo
        const top = (e.clientY + th + gap > vh)
          ? e.clientY - th - gap
          : e.clientY + gap;
        rtTooltip.style.left = left + 'px';
        rtTooltip.style.top  = top  + 'px';
      }
      badge.addEventListener('mouseenter', e => {
        rtTitle.textContent = n + ' roteador' + (n > 1 ? 'es' : '');
        rtList.innerHTML = rots.map(r => `<div class="rt-tooltip-item">${esc(r)}</div>`).join('');
        rtTooltip.style.display = 'block';
        positionRtTooltip(e);
      });
      badge.addEventListener('mousemove', positionRtTooltip);
      badge.addEventListener('mouseleave', () => { rtTooltip.style.display = 'none'; });
    }

    tr.appendChild(tdData);
    tr.appendChild(tdCliente);
    tr.appendChild(tdAtiv);
    tr.appendChild(tdAno);
    tr.appendChild(tdRot);
    tbody.appendChild(tr);
  });
}

function renderPagination() {
  const pag = document.getElementById('pagination');
  const total = Math.ceil(filtered.length/PER_PAGE);
  pag.innerHTML = ''; pag.style.display = total<=1?'none':'flex';
  const mkBtn = (label, pg, active=false, disabled=false) => {
    const b=document.createElement('button'); b.className='page-btn'+(active?' active':'');
    b.textContent=label; b.disabled=disabled;
    if (!disabled) b.onclick=()=>{page=pg;renderTable();renderPagination();};
    return b;
  };
  pag.appendChild(mkBtn('←', page-1, false, page===1));
  const range = total<=7?Array.from({length:total},(_,i)=>i+1):page<=4?[1,2,3,4,5,'…',total]:page>=total-3?[1,'…',total-4,total-3,total-2,total-1,total]:[1,'…',page-1,page,page+1,'…',total];
  range.forEach(p => {
    if (p==='…') { const s=document.createElement('span'); s.textContent='…'; s.style.cssText='color:var(--muted);font-size:12px'; pag.appendChild(s); }
    else pag.appendChild(mkBtn(p, p, p===page));
  });
  pag.appendChild(mkBtn('→', page+1, false, page===total));
}

function buildCharts() {
  const claroN=ALL.filter(a=>a.cliente==='Claro').length;
  const gilatN=ALL.filter(a=>a.cliente==='Gilat').length;
  const vivoN =ALL.filter(a=>a.cliente==='Vivo').length;
  new Chart(document.getElementById('chartPie'), {
    type:'doughnut',
    data:{ labels:['Claro','Gilat','Vivo'], datasets:[{ data:[claroN,gilatN,vivoN], backgroundColor:['#ef4444','#3b82f6','#a855f7'], borderColor:'#181c25', borderWidth:3, hoverOffset:8 }] },
    options:{ responsive:true, maintainAspectRatio:false, cutout:'62%',
      plugins:{ legend:{ position:'bottom', labels:{ color:'#6b748a', font:{family:'Inter',size:12}, padding:16, boxWidth:12, boxHeight:12 } },
        tooltip:{ callbacks:{ label:ctx=>` ${ctx.label}: ${ctx.parsed} atividades` } } } }
  });
  const monthMap={};
  ALL.forEach(a => {
    const [y,m]=a.data.split('-'); const key=y+'-'+m;
    if (!monthMap[key]) monthMap[key]={Claro:0,Gilat:0,Vivo:0};
    monthMap[key][a.cliente]++;
  });
  const keys=Object.keys(monthMap).sort();
  const labels=keys.map(k=>{ const [y,m]=k.split('-'); return MESES[parseInt(m,10)-1]+' '+y.slice(2); });
  new Chart(document.getElementById('chartBar'), {
    type:'bar',
    data:{ labels, datasets:[
      { label:'Claro', data:keys.map(k=>monthMap[k].Claro), backgroundColor:'#ef4444', borderRadius:4 },
      { label:'Gilat', data:keys.map(k=>monthMap[k].Gilat), backgroundColor:'#3b82f6', borderRadius:4 },
      { label:'Vivo',  data:keys.map(k=>monthMap[k].Vivo),  backgroundColor:'#a855f7', borderRadius:4 },
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      scales:{
        x:{ stacked:true, ticks:{color:'#6b748a',font:{family:'Inter',size:11}}, grid:{color:'#252a36'} },
        y:{ stacked:true, ticks:{color:'#6b748a',font:{family:'Inter',size:11},stepSize:1}, grid:{color:'#252a36'} }
      },
      plugins:{ legend:{ position:'top', align:'end', labels:{color:'#6b748a',font:{family:'Inter',size:12},boxWidth:12,boxHeight:12} } }
    }
  });
}

// ── Heatmap ───────────────────────────────────────────────────────────────────
const DIAS_SEMANA = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
const MESES_FULL  = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

function hmPopulateAno() {
  const anos = [...new Set(ALL.map(a => a.ano))].sort((a,b) => b - a);
  const sel = document.getElementById('hm-ano');
  sel.innerHTML = '';
  anos.forEach(a => { const o = document.createElement('option'); o.value = a; o.textContent = a; sel.appendChild(o); });
  if (anos.length) sel.value = anos[0];
}

function buildHeatmap() {
  const ano     = parseInt(document.getElementById('hm-ano').value, 10);
  const cliente = document.getElementById('hm-cliente').value;
  if (!ano) return;

  const fonte = cliente ? ALL.filter(a => a.cliente === cliente) : ALL;

  // Montar mapa data → count
  const countMap = {};
  fonte.forEach(a => { if (parseInt(a.data.slice(0,4),10) === ano) countMap[a.data] = (countMap[a.data]||0) + 1; });
  const maxCount = Math.max(1, ...Object.values(countMap));

  function level(n) {
    if (!n) return 0;
    if (n <= maxCount * .25) return 1;
    if (n <= maxCount * .50) return 2;
    if (n <= maxCount * .75) return 3;
    return 4;
  }

  // Semana começa na segunda-feira (índice JS: 1)
  // Offset: quantos dias recuar a partir do 1-Jan para chegar à segunda anterior
  const jan1    = new Date(ano, 0, 1);
  const hoje    = new Date(); hoje.setHours(23,59,59,999);
  const dow1    = jan1.getDay(); // 0=Dom … 6=Sáb
  const offsetSeg = (dow1 === 0) ? 6 : dow1 - 1; // dias a recuar até a segunda
  const start   = new Date(jan1);
  start.setDate(jan1.getDate() - offsetSeg);

  // Fim: domingo da semana que contém 31-Dez
  const dec31  = new Date(ano, 11, 31);
  const dowFim = dec31.getDay();
  const end    = new Date(dec31);
  end.setDate(dec31.getDate() + ((dowFim === 0) ? 0 : 7 - dowFim)); // avança até domingo

  // Labels dos dias: Seg, Ter, Qua, Qui, Sex, Sáb, Dom
  const DIAS_SEG = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];

  const grid    = document.getElementById('heatmap-grid');
  const tooltip = document.getElementById('hm-tooltip');
  grid.innerHTML = '';

  // Coluna de labels (Seg, Qua, Sex — só ímpares para não poluir)
  const labelsCol = document.createElement('div');
  labelsCol.className = 'heatmap-labels-day';
  DIAS_SEG.forEach((d,i) => {
    const lbl = document.createElement('div');
    lbl.className = 'heatmap-day-label';
    lbl.textContent = (i % 2 === 0) ? d : '';
    labelsCol.appendChild(lbl);
  });
  grid.appendChild(labelsCol);

  const cur = new Date(start);
  let lastMonth = -1;

  while (cur <= end) {
    const col = document.createElement('div');
    col.className = 'heatmap-col';

    // Guarda as 7 datas desta semana para decidir se a coluna tem dados visíveis
    const semana = [];
    const tmpCur = new Date(cur);
    for (let d = 0; d < 7; d++) {
      semana.push(new Date(tmpCur));
      tmpCur.setDate(tmpCur.getDate() + 1);
    }

    // Label do mês: mostrar quando a segunda-feira da semana muda de mês
    const monthLbl = document.createElement('div');
    monthLbl.className = 'heatmap-month-label';
    const mesSeg = semana[0].getMonth(); // segunda-feira
    if (mesSeg !== lastMonth && semana[0].getFullYear() === ano) {
      monthLbl.textContent = MESES_FULL[mesSeg];
      lastMonth = mesSeg;
    } else {
      monthLbl.textContent = '';
    }
    col.appendChild(monthLbl);

    for (let d = 0; d < 7; d++) {
      const cell    = document.createElement('div');
      cell.className = 'heatmap-cell';
      const dia     = semana[d];
      const isoDate = dia.toISOString().slice(0,10);
      const inYear  = dia.getFullYear() === ano;
      const isFuture = dia > hoje;

      if (!inYear || isFuture) {
        cell.classList.add('future');
      } else {
        const cnt = countMap[isoDate] || 0;
        cell.dataset.count = cnt;
        if (cnt > 0) cell.dataset.level = level(cnt);

        const dateStr   = isoDate;
        const diaSemana = d; // 0=Seg … 6=Dom nesta grade
        cell.addEventListener('mouseenter', e => {
          const [y,m,dd] = dateStr.split('-');
          const semNome  = DIAS_SEG[diaSemana];
          const label    = cnt === 0 ? 'Nenhuma atividade' : `${cnt} atividade${cnt>1?'s':''}`;
          tooltip.innerHTML = `<strong>${label}</strong><br><span class="hm-tt-muted">${semNome}, ${dd}/${m}/${y}</span>`;
          tooltip.style.display = 'block';
        });
        cell.addEventListener('mousemove', e => {
          const tw = tooltip.offsetWidth || 160;
          const th = tooltip.offsetHeight || 40;
          const left = (e.clientX + 14 + tw > window.innerWidth)  ? e.clientX - tw - 14 : e.clientX + 14;
          const top  = (e.clientY - 36 < 0)                        ? e.clientY + 14      : e.clientY - 36;
          tooltip.style.left = left + 'px';
          tooltip.style.top  = top  + 'px';
        });
        cell.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
      }

      col.appendChild(cell);
      cur.setDate(cur.getDate() + 1);
    }
    grid.appendChild(col);
  }

  // Estatística resumida
  const total = Object.values(countMap).reduce((a,b)=>a+b, 0);
  const diasAtivos = Object.keys(countMap).length;
  document.getElementById('hm-stat').textContent = `${total} atividade${total!==1?'s':''}  ·  ${diasAtivos} dia${diasAtivos!==1?'s':''}  ·  ${ano}`;

  // Alinhar footer com as bordas do grid
  requestAnimationFrame(() => {
    const gridEl   = document.getElementById('heatmap-grid');
    const footerEl = document.querySelector('.heatmap-footer');
    if (gridEl && footerEl) {
      footerEl.style.width = gridEl.offsetWidth + 'px';
    }
  });
}

document.getElementById('hm-ano').addEventListener('change', buildHeatmap);
document.getElementById('hm-cliente').addEventListener('change', buildHeatmap);

// ── Roteadores ────────────────────────────────────────────────────────────────
const ALL_ROUTERS = PAYLOAD.roteadores || [];

function initRouters() {
  document.getElementById('kpi-routers').textContent = ALL_ROUTERS.length;
}

updateKPIs(); populateAno(); hmPopulateAno(); applyFilters(); buildCharts(); buildHeatmap(); initRouters();
</script>
</body>
</html>'''

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    todas = []
    todas += ler_claro(PASTAS["Claro"])
    todas += ler_gilat(PASTAS["Gilat"])
    todas += ler_vivo(PASTAS["Vivo"])
    todas.sort(key=lambda x: x["data"], reverse=True)

    # Coletar todos os roteadores únicos globais
    todos_roteadores = sorted({r for a in todas for r in a.get("roteadores", [])})

    payload = {
        "gerado_em": datetime.now().isoformat(),
        "total": len(todas),
        "atividades": todas,
        "roteadores": todos_roteadores,
    }

    html = HTML_TEMPLATE.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False))
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # Largura do terminal (fallback 100)
    try:
        import shutil
        W = shutil.get_terminal_size().columns
    except Exception:
        W = 100
    W = max(W, 60)

    SEP  = "─" * W
    SEP2 = "═" * W

    print(f"\n{SEP2}")
    print(f"  ✅  {len(todas)} atividades  ·  🔌 {len(todos_roteadores)} roteadores únicos")
    print(f"  📄  {OUTPUT_HTML}")
    print(SEP2)

    CORES = {"Claro": "\033[91m", "Gilat": "\033[94m", "Vivo": "\033[95m"}
    RESET = "\033[0m"

    for cliente in ("Claro", "Gilat", "Vivo"):
        cor   = CORES.get(cliente, "")
        itens = [a for a in todas if a["cliente"] == cliente]
        rots  = sorted({r for a in itens for r in a.get("roteadores", [])})
        por_ano = {}
        for a in itens:
            por_ano.setdefault(a["ano"], 0)
            por_ano[a["ano"]] += 1
        resumo = "  |  ".join(f"{ano}: {n}" for ano, n in sorted(por_ano.items()))

        print(f"\n{cor}{'━' * W}{RESET}")
        print(f"{cor}  {cliente.upper():8}{RESET}  {len(itens)} atividades  ·  {len(rots)} roteadores  ({resumo})")
        print(f"{cor}{'━' * W}{RESET}")

        if rots:
            # Imprimir em colunas — calcular largura máxima dos hostnames
            col_w = max(len(r) for r in rots) + 2
            cols  = max(1, (W - 4) // col_w)
            for i, r in enumerate(rots):
                fim = "\n" if (i + 1) % cols == 0 or i == len(rots) - 1 else ""
                print(f"  {r:<{col_w}}", end=fim)
        else:
            print("  (nenhum roteador identificado)")

    print(f"\n{SEP}\n")

if __name__ == "__main__":
    main()
