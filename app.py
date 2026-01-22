import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

app = dash.Dash(__name__)
server = app.server 
app.title = "XM Dashboard Pro"

# --- DISEÑO ---
app.layout = html.Div(style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f4f7f9', 'minHeight': '100vh', 'padding': '20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        
        html.Div(style={'textAlign': 'center', 'marginBottom': '30px'}, children=[
            html.H1("Monitor Energético Nacional (XM)", style={'color': '#1a2b49', 'margin': '0'}),
            html.P("Consulta de variables horarias del SIN", style={'color': '#6b7280'})
        ]),

        html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '12px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.05)', 'marginBottom': '20px'}, children=[
            html.Label("Seleccione una Variable del Catálogo:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '10px'}),
            dcc.Dropdown(
                id='metric-dropdown',
                placeholder="Cargando catálogo de XM...",
                searchable=True,
                clearable=False
            ),
            html.Div(id='status-badge', style={'marginTop': '15px', 'fontSize': '13px', 'fontWeight': 'bold'})
        ]),

        html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '12px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.05)'}, children=[
            dcc.Loading(
                type="dot",
                children=dcc.Graph(id='main-graph', config={'displayModeBar': False})
            )
        ]),

        dcc.Interval(id='auto-refresh', interval=5*60*1000, n_intervals=0)
    ])
])

# --- FUNCIONES DE DATOS ---

def get_catalog():
    """Obtiene el catálogo de XM y mapea nombres correctamente"""
    try:
        url = "https://servapibi.xm.com.co/lists"
        payload = {"MetricId": "ListadoMetricas"}
        res = requests.post(url, json=payload, timeout=15)
        
        if res.status_code != 200:
            return []
            
        items = res.json().get('Items', [])
        options = []
        
        for i in items:
            # Buscamos el ID y el Nombre en las posibles llaves que usa XM
            m_id = i.get('MetricId') or i.get('CodMetrica')
            m_name = i.get('MetricName') or i.get('NombreMetrica')
            
            if m_id:
                label = f"{m_name} [{m_id}]" if m_name else f"Variable {m_id}"
                options.append({'label': label, 'value': m_id})
        
        return sorted(options, key=lambda x: x['label'])
    except Exception as e:
        print(f"Error en catálogo: {e}")
        return []

def get_data(metric_id):
    """Consulta datos horarios para la métrica seleccionada"""
    if not metric_id:
        return None
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
            return None
            
        items = res.json().get('Items', [])
        if not items:
            return None

        data_list = []
        for item in items:
            fecha_base = item.get('Date')
            for h in range(1, 25):
                col_hora = f'Hour{str(h).zfill(2)}'
                valor = item.get(col_hora)
                if valor is not None:
                    timestamp = pd.to_datetime(fecha_base) + pd.to_timedelta(h-1, unit='h')
                    data_list.append({'x': timestamp, 'y': valor})
        
        return pd.DataFrame(data_list).sort_values('x')
    except Exception as e:
        print(f"Error en datos: {e}")
        return None

# --- CALLBACKS ---

@app.callback(
    [Output('metric-dropdown', 'options'), Output('metric-dropdown', 'value')],
    Input('auto-refresh', 'n_intervals')
)
def update_dropdown_list(n):
    opts = get_catalog()
    # Intentamos poner Demanda Real (DemaReal) por defecto si existe
    default_val = 'DemaReal' if any(o['value'] == 'DemaReal' for o in opts) else (opts[0]['value'] if opts else None)
    return opts, default_val

@app.callback(
    [Output('main-graph', 'figure'), Output('status-badge', 'children'), Output('status-badge', 'style')],
    [Input('metric-dropdown', 'value'), Input('auto-refresh', 'n_intervals')]
)
def update_main_plot(selected_metric, n):
    if not selected_metric:
        return go.Figure(), "Seleccione una variable", {'color': 'gray'}

    df = get_data(selected_metric)
    
    if df is None or df.empty:
        return go.Figure(), f"⚠️ La métrica '{selected_metric}' no tiene datos horarios disponibles para hoy.", {'color': '#d32f2f'}

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['x'], y=df['y'],
        mode='lines',
        line=dict(color='#2563eb', width=3),
        fill='tozeroy',
        fillcolor='rgba(37, 99, 235, 0.1)',
        name=selected_metric
    ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Fecha y Hora", showgrid=True),
        yaxis=dict(title="Valor", showgrid=True),
        hovermode="x unified"
    )

    status_text = f"● Conectado a XM: {selected_metric} ({datetime.datetime.now().strftime('%H:%M:%S')})"
    return fig, status_text, {'color': '#2e7d32'}

if __name__ == '__main__':
    app.run_server(debug=False)
