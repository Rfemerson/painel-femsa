"""Painel comercial FEMSA: autenticação, consulta e visualização somente leitura."""

import hashlib
import hmac
import math
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


COLUNAS = ['Data', 'Aplicativo', 'Tipo', 'Status', 'Supervisor', 'Vendedor', 'Matrícula', 'Validade']
CORES = ['#D71920', '#27272A', '#EF767A', '#74747C', '#A60F15']
CSS = """
<style>
.block-container {max-width: 1440px; padding-top: 2rem;}
h1,h2,h3 {color: #27272A;}
[data-testid="stMetric"] {border: 1px solid #E4E4E7; border-top: 4px solid #D71920;
 border-radius: 10px; padding: 16px; background: white;}
.femsa-brand {color: #D71920; font-weight: 900; letter-spacing: .16em; font-size: 22px;}
.table-scroll {overflow-x:auto; border:1px solid #E4E4E7; border-radius:10px;}
.table-scroll table {width:100%; border-collapse:collapse; font-size:14px;}
.table-scroll th {background:#27272A; color:white; text-align:left; white-space:nowrap;}
.table-scroll td,.table-scroll th {padding:12px; border-bottom:1px solid #E4E4E7;}
.table-scroll tr:nth-child(even) {background:#F4F4F5;}
@media(max-width:640px) {.block-container {padding:1rem;} h1 {font-size:1.8rem;}}
</style>
"""


def normalizar(value):
    text = '' if pd.isna(value) else str(value).strip()
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).upper()


def autenticar():
    try:
        password = st.secrets['DASHBOARD_PASSWORD']
    except (KeyError, FileNotFoundError):
        st.error('A senha do painel ainda não foi configurada. Contate o administrador.')
        st.stop()
    if not isinstance(password, str) or not password.strip():
        st.error('Configure uma senha válida para o painel.')
        st.stop()
    fingerprint = hashlib.sha256(password.encode()).hexdigest()
    if hmac.compare_digest(st.session_state.get('auth', ''), fingerprint):
        return
    st.title('Acesso ao painel comercial')
    st.caption('Informe a senha para visualizar os chamados da FEMSA.')
    with st.form('login', clear_on_submit=True):
        entered = st.text_input('Senha', type='password')
        submitted = st.form_submit_button('Entrar', type='primary')
    if submitted:
        if hmac.compare_digest(entered.encode(), password.encode()):
            st.session_state.auth = fingerprint
            st.rerun()
        st.error('Senha incorreta.')
    st.stop()


def preparar(records):
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError('Formato de registros inválido.')
    if not records:
        return pd.DataFrame({c: pd.Series(dtype='datetime64[ns]' if c == 'Data' else 'str') for c in COLUNAS})
    df = pd.DataFrame(records)
    aliases = {normalizar(c): c for c in COLUNAS}
    aliases.update({
        'CARIMBO DE DATA/HORA': 'Data',
        'DATA/HORA': 'Data',
        'DATA DE ABERTURA': 'Data',
        'TIPO DO CHAMADO': 'Tipo',
        'TIPO DE CHAMADO': 'Tipo',
    })
    df = df.rename(columns={c: aliases.get(normalizar(c), c) for c in df.columns})
    if df.columns.duplicated().any() or not set(COLUNAS).issubset(df.columns):
        raise ValueError('Confira os cabeçalhos obrigatórios na aba Base_Painel.')
    df = df.loc[df['Validade'].fillna('').astype(str).str.strip().str.upper().eq('VÁLIDO'), COLUNAS].copy()
    for col in COLUNAS[1:]:
        df[col] = df[col].fillna('').astype(str).str.strip()
    statuses = {'CONCLUIDO': 'CONCLUÍDO', 'CONCLUIDOS': 'CONCLUÍDO', 'PENDENTES': 'PENDENTE'}
    df['Status'] = df['Status'].map(lambda value: statuses.get(normalizar(value), normalizar(value)) or 'SEM STATUS')
    for col in ['Aplicativo', 'Tipo', 'Supervisor', 'Vendedor', 'Matrícula']:
        df[col] = df[col].replace('', 'Não informado')
    def parse_date(value):
        text = str(value).strip()
        return pd.to_datetime(text, errors='coerce', dayfirst=not (len(text) > 4 and text[4] == '-'))
    df['Data'] = df['Data'].map(parse_date)
    return df.sort_values('Data', ascending=False, na_position='last', kind='stable').reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False, max_entries=4)
def carregar(url, token):
    try:
        response = requests.post(url, json={'token': token}, timeout=(10, 45))
    except requests.RequestException as exc:
        raise RuntimeError('Não foi possível conectar ao Apps Script.') from exc

    if response.status_code != 200:
        raise RuntimeError(f'O Apps Script respondeu com HTTP {response.status_code}.')

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        final_host = urlparse(response.url).hostname or ''
        if 'accounts.google.com' in final_host or 'ServiceLogin' in response.text:
            raise RuntimeError(
                'O Apps Script exige login Google. Publique o app da Web com acesso para Qualquer pessoa.'
            ) from exc
        raise RuntimeError('O Apps Script não retornou JSON válido.') from exc

    if not isinstance(payload, dict) or payload.get('ok') is not True:
        detail = payload.get('error') if isinstance(payload, dict) else ''
        raise RuntimeError(f'A API recusou a consulta: {detail or "resposta inválida"}')

    return preparar(payload.get('records')), datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def grafico(fig):
    fig.update_layout(font_family='Arial', font_color='#27272A', margin=dict(l=10, r=10, t=25, b=15),
                      paper_bgcolor='white', plot_bgcolor='white', separators=',.')
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False, 'responsive': True, 'locale': 'pt-BR'})


def main():
    st.set_page_config(page_title='FEMSA | Chamados comerciais', page_icon='🔴', layout='wide')
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="femsa-brand">FEMSA</div>', unsafe_allow_html=True)
    autenticar()  # Nenhuma leitura de dados ou consulta ao cache ocorre antes deste ponto.
    with st.sidebar:
        st.header('Painel comercial')
        if st.button('Sair', width='stretch'):
            st.session_state.clear()
            st.rerun()
        refresh = st.button('Atualizar dados', type='primary', width='stretch')
    try:
        url, token = st.secrets['DATA_API_URL'], st.secrets['DATA_API_TOKEN']
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'script.google.com' or not parsed.path.endswith('/exec') or not token:
            raise ValueError('Configure a URL /exec do Apps Script e o token da API.')
        if refresh:
            carregar.clear()
        with st.spinner('Consultando chamados…'):
            df, updated = carregar(url, token)
    except (KeyError, FileNotFoundError):
        st.error('Configure DATA_API_URL e DATA_API_TOKEN nos secrets do Streamlit.')
        st.stop()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    except (ValueError, TypeError) as exc:
        st.error(f'Não foi possível interpretar os dados da base: {exc}')
        st.stop()
    st.title('Chamados comerciais')
    st.caption(f'Visão operacional • Somente registros válidos • Consulta em {updated} (horário do servidor)')
    with st.sidebar:
        st.header('Filtros')
        period = ()
        valid_dates = df['Data'].dropna()
        if not valid_dates.empty:
            period = st.date_input('Período', value=(), min_value=valid_dates.min().date(),
                                   max_value=valid_dates.max().date(), format='DD/MM/YYYY')
            st.caption('Sem seleção: todo o período, incluindo datas ausentes.')
        selections = {c: st.multiselect(c, sorted(df[c].unique())) for c in ['Aplicativo', 'Tipo', 'Status', 'Supervisor']}
        search = st.text_input('Buscar vendedor ou matrícula', placeholder='Nome ou matrícula')
    filtered = df.copy()
    if len(period) == 1:
        st.info('Selecione a data final para aplicar o período.')
    elif len(period) == 2:
        filtered = filtered.loc[filtered['Data'].dt.date.between(*period)]
    for column, selected in selections.items():
        if selected:
            filtered = filtered.loc[filtered[column].isin(selected)]
    if search.strip():
        query = normalizar(search)
        filtered = filtered.loc[filtered['Vendedor'].map(normalizar).str.contains(query, regex=False) |
                                filtered['Matrícula'].map(normalizar).str.contains(query, regex=False)]
    total = len(filtered)
    count = filtered['Status'].value_counts()
    completed = int(count.get('CONCLUÍDO', 0))
    metrics = [('Total', total), ('Concluídos', completed), ('Pendentes', int(count.get('PENDENTE', 0))),
               ('Em atendimento', int(count.get('EM ATENDIMENTO', 0))), ('Sem status', int(count.get('SEM STATUS', 0))),
               ('Taxa de conclusão', f'{completed / total * 100 if total else 0:.1f}%'.replace('.', ','))]
    for start in (0, 3):
        for col, (label, value) in zip(st.columns(3), metrics[start:start + 3]):
            col.metric(label, value)
    st.caption('Indicadores, gráficos e tabela refletem os filtros selecionados.')
    if filtered.empty:
        st.info('Nenhum chamado encontrado para os filtros selecionados.')
        return
    left, right = st.columns(2)
    with left:
        st.subheader('Distribuição por status')
        chart = filtered.groupby('Status').size().reset_index(name='Chamados')
        grafico(px.pie(chart, names='Status', values='Chamados', hole=.62, color_discrete_sequence=CORES))
    with right:
        st.subheader('Chamados por tipo')
        chart = filtered.groupby('Tipo').size().reset_index(name='Chamados').sort_values('Chamados')
        grafico(px.bar(chart, x='Chamados', y='Tipo', orientation='h', color_discrete_sequence=CORES))
    st.subheader('Evolução diária de aberturas')
    dated = filtered.dropna(subset=['Data'])
    if not dated.empty:
        daily = dated.set_index('Data').resample('D').size().rename('Chamados').reset_index()
        fig = px.line(daily, x='Data', y='Chamados', markers=True, color_discrete_sequence=CORES)
        fig.update_xaxes(tickformat='%d/%m/%Y')
        fig.update_yaxes(rangemode='tozero', dtick=1 if daily['Chamados'].max() < 10 else None)
        grafico(fig)
    missing = int(filtered['Data'].isna().sum())
    if missing:
        st.warning(f'{missing} chamado(s) sem data válida: exibidos no final da tabela e excluídos da evolução diária.')
    st.subheader('Detalhamento dos chamados')
    size = st.selectbox('Chamados por página', [10, 25, 50], index=1)
    pages = max(1, math.ceil(total / size))
    signature = repr((period, selections, search, size, total))
    if st.session_state.get('filter_signature') != signature:
        st.session_state.page = 1
        st.session_state.filter_signature = signature
    page = st.number_input('Página', min_value=1, max_value=pages, step=1, key='page')
    start = (page - 1) * size
    table = filtered.iloc[start:start + size].drop(columns='Validade').copy()
    table['Data'] = table['Data'].dt.strftime('%d/%m/%Y %H:%M').fillna('Sem data')
    # HTML escapado: nenhum editor, toolbar, link automático ou botão de exportação.
    st.markdown('<div class="table-scroll">' + table.to_html(index=False, escape=True, border=0) + '</div>', unsafe_allow_html=True)
    st.caption(f'Página {page} de {pages} • Exibindo {start + 1}–{min(start + size, total)} de {total} chamados • Mais recentes primeiro')


if __name__ == '__main__':
    main()
