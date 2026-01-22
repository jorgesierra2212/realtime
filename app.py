import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

app = dash.Dash(__name__)
server = app.server 
app.title = "XM Dashboard Pro"

# --- DISEÑO LIMPIO Y PROFESIONAL ---
app.layout = html.Div(style={'fontFamily': 'Helvetica, Arial, sans-serif', 'backgroundColor': '#f4f7f9', 'minHeight': '100vh', 'padding': '40px 20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        
        # Encabezado
        html.Div(style={'textAlign': 'left', 'marginBottom': '30px'}, children=[
            html.H1("Monitor Energético Nacional", style={'color': '#1a2b49', 'fontWeight': '800', 'margin': '0'}),
            html.P("Consulta de demanda y variables del SIN en tiempo real (Fuente: XM)", style={'color': '#6b7280', 'marginTop': '5px'})
        ]),

        # Panel de Control
        html.Div(style={'backgroundColor': 'white', 'padding': '25px', 'borderRadius': '15px', 'boxShadow': '0 4px 20px rgba(0,0,0,0.05)', 'marginBottom': '25px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px', 'alignItems': 'flex-end', 'flexWrap': 'wrap'}, children=[
                html.Div(style={'flex': '1', 'minWidth': '300px'}, children=[
                    html.Label("Variable del Catálogo XM", style={'fontWeight': 'bold', 'color': '#374151', 'fontSize': '14px', 'display': 'block', 'marginBottom': '8px'}),
                    dcc.Dropdown(
                        id='metric-dropdown',
                        placeholder="Buscando variables en XM...",
                        searchable=True,
                        clearable=False,
                        style={'borderRadius': '8px'}
                    ),
                ]),
                html.Div(style={'paddingBottom': '5px'}, children=[
                    html.Span(id='status-badge', style={'padding': '8px 15px', 'borderRadius': '20px', 'fontSize': '12px', 'fontWeight': 'bold'})
                ])
            ])
        ]),

        # Gráfico principal
        html.Div(style={'backgroundColor': 'white', 'padding': '25px', 'borderRadius': '15px', 'boxShadow': '0 4px 20px rgba(0,0,0,0.05)'}, children=[
            dcc.Loading(
                type="dot",
                color="#2563eb",
                children=dcc.Graph(id='main-graph', config={'displayModeBar': False}, style={'height': '500px'})
            )
        ]),

        dcc.Interval(id='auto-refresh', interval=5*60*1000, n_intervals=0)
    ])
])

# --- LÓGICA DE EXTRACCIÓN DE DATOS ---

def get_catalog():
    """Obtiene el catálogo intentando múltiples mapeos de llaves de XM"""
    try:
        url = "https://servapibi.xm.com.co/lists"
        payload = {"MetricId": "ListadoMetricas"}
        res = requests.post(url, json=payload, timeout=15)
        
        if res.status_code != 200: return []
        
        items = res.json().get('Items', [])
        options = []
        
        for i in items:
            # Mapeo robusto: XM usa diferentes nombres de columna según la versión
            m_id = i.get('MetricId') or i.get('metricId') or i.get('CodMetrica') or i.get('Id')
            m_name = i.get('MetricName') or i.get('metricName') or i.get('NombreMetrica') or i.get('Nombre')
            
            if m_id:
                label = f"{m_name}" if m_name else f"Variable {m_id}"
                options.append({'label': f"{label} [{m_id}]", 'value': m_id})
        
        return sorted(options, key=lambda x: x['label'])
    except:
        return []

def get_data(metric_id):
    if not metric_id: return None
    try:
        end_date = datetime.datetime.now().date()
        start_date = end_date - datetime.timedelta(days=2)
        
        # Endpoint horario
        url = "https://servapibi.xm.com.co/hourly"
        payload = {
            "MetricId": metric_id,
            "StartDate": str(start_date),
            "EndDate": str(end_date),
            "Entity": "Sistema"
        }
        
        res = requests.post(url, json=payload, timeout=20)
        items = res.json().get('Items', [])
        
        if not items: return None

        data = []
        for item in items:
            date_val = item.get('Date')
            for h in range(1, 25):
                # Las horas en la API XM vienen como Hour01, Hour02...
                val = item.get(f'Hour{str(h).zfill(2)}')
                if val is not None:
                    ts = pd.to_datetime(date_val) + pd.to_timedelta(h-1, unit='h')
                    data.append({'x': ts, 'y': val})
