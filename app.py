import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

app = dash.Dash(__name__)
server = app.server 
app.title = "XM API Explorer"

# --- INTERFAZ ---
app.layout = html.Div(style={'fontFamily': 'Segoe UI, sans-serif', 'padding': '20px', 'backgroundColor': '#f0f2f5'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto', 'backgroundColor': 'white', 'padding': '25px', 'borderRadius': '15px', 'boxShadow': '0 10px 25px rgba(0,0,0,0.1)'}, children=[
        
        html.H2("Explorador de Variables XM (Tiempo Real)", style={'textAlign': 'center', 'color': '#1e3a8a'}),
        
        html.Div([
            html.Label("Selecciona o busca una métrica del catálogo oficial:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '10px'}),
            dcc.Dropdown(
                id='metric-dropdown',
                placeholder="Cargando catálogo...",
                style={'marginBottom': '20px'}
            ),
        ]),

        html.Div(id='info-panel', style={'padding': '10px', 'borderRadius': '5px', 'backgroundColor': '#eef2ff', 'marginBottom': '20px', 'fontSize': '14px'}),

        dcc.Loading(
            type="circle",
            children=dcc.Graph(id='main-graph', config={'displayModeBar': False})
        ),
        
        dcc.Interval(id='auto-refresh', interval=5*60*1000, n_intervals=0)
    ])
])

# --- FUNCIONES DE DATOS ---

def get_xm_catalog():
    """Obtiene todas las métricas disponibles en XM"""
    try:
        url = "https://servapibi.xm.com.co/lists"
        payload = {"MetricId": "ListadoMetricas"}
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            items = res.json().get('Items', [])
            # Creamos opciones para el Dropdown: {label: Nombre Amigable, value: ID Técnico}
            options = [
                {'label': f"{i.get('MetricName', 'S/N')} ({i.get('MetricId')})", 'value': i.get('MetricId')}
                for i in items
            ]
            return sorted(options, key=lambda x: x['label'])
        return [{'label': 'Error cargando catálogo', 'value': 'error'}]
    except Exception as e:
        return [{'label': f'Error: {str(e)}', 'value': 'error'}]

def fetch_xm_data(metric_id):
    """Consulta los datos horarios para la métrica seleccionada"""
    if not metric_id or metric_id == 'error':
        return None, "Selecciona una métrica"
    
    try:
        end_date = datetime.datetime.now().date()
        start_date = end_date - datetime.timedelta(days=2)
        url = "https://servapibi.xm.com.co/hourly"
        
        payload = {
            "MetricId": metric_id,
            "StartDate": str(start_date),
            "EndDate": str(end_date),
            "Entity": "Sistema"
        }
        
        res = requests.post(url, json=payload, timeout=20)
        
        if res.status_code != 200:
            return None, f"Error {res.status_code}: {res.text}"
        
        items = res.json().get('Items', [])
        if not items:
            return None, "La métrica no devolvió datos para los últimos 2 días."

        recs = []
        for item in items:
            fecha = item['Date']
            for h in range(1, 25):
                val = item.get(f'Hour{str(h).zfill(2)}')
                if val is not None:
                    ts = pd.to_datetime(fecha) + pd.to_timedelta(h-1, unit='h')
                    recs.append({'Timestamp': ts, 'Valor': val})
        
        df = pd.DataFrame(recs).sort_values('Timestamp')
        return df, "Éxito"
    except Exception as e:
        return None, f"Error de conexión: {str(e)}"

# --- CALLBACKS ---

# 1. Cargar el catálogo al abrir la app
@app.callback(
    [Output('metric-dropdown', 'options'), Output('metric-dropdown', 'value')],
    Input('auto-refresh', 'n_intervals') # Se dispara al cargar
)
def fill_catalog(n):
    opts = get_xm_catalog()
    # Intentamos pre-seleccionar 'DemaReal' si existe, si no, nada.
    default_val = next((o['value'] for o in opts if o['value'] == 'DemaReal'), None)
    return opts, default_val

# 2. Actualizar gráfica según selección o tiempo
@app.callback(
    [Output('main-graph', 'figure'), Output('info-panel', 'children')],
    [Input('metric-dropdown', 'value'), Input('auto-refresh', 'n_intervals')]
)
def update_graph(selected_metric, n):
    if not selected_metric:
        return go.Figure(), "Selecciona una variable arriba para comenzar."
    
    df, status = fetch_xm_data(selected_metric)
    
    if df is None:
        return go.Figure(), f"⚠️ Estado: {status}"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Timestamp'], y=df['Valor'],
        mode='lines+markers',
        line=dict(color='#3b82f6', width=3),
        fill='tozeroy',
        fillcolor='rgba(59, 130, 246, 0.1)',
        name=selected_metric
    ))

    fig.update_layout(
        title=f"Visualizando: {selected_metric}",
        template='plotly_white',
        xaxis=dict(title="Fecha y Hora", gridcolor='#f0f0f0'),
        yaxis=dict(title="Valor", gridcolor='#f0f0f0'),
        margin=dict(l=0, r=0, t=50, b=0)
    )

    info = f"✅ Mostrando '{selected_metric}'. Datos actualizados: {datetime.datetime.now().strftime('%H:%M:%S')}"
    return fig, info

if __name__ == '__main__':
    app.run_server(debug=False)
