import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

# Configuración de la App
app = dash.Dash(__name__)
server = app.server 
app.title = "Demanda XM en Tiempo Real"

# --- DISEÑO DEL DASHBOARD ---
app.layout = html.Div(style={'fontFamily': 'Segoe UI, sans-serif', 'padding': '30px', 'backgroundColor': '#f4f7f6'}, children=[
    html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 4px 10px rgba(0,0,0,0.1)'}, children=[
        html.H1("Demanda de Energía Colombia (SIN)", style={'textAlign': 'center', 'color': '#1a2a6c', 'margin': '0'}),
        html.P(id='live-update-text', style={'textAlign': 'center', 'color': '#555', 'fontSize': '14px'}),
        
        dcc.Graph(id='live-graph-demanda', config={'displayModeBar': False}),
        
        dcc.Interval(
            id='interval-component',
            interval=5*60*1000, # 5 minutos
            n_intervals=0
        )
    ])
])

# --- FUNCIÓN PARA OBTENER DATOS DIRECTO DE LA API DE XM ---
def fetch_xm_data():
    try:
        hoy = datetime.datetime.now().date()
        ayer = hoy - datetime.timedelta(days=1)
        
        # Endpoint oficial de XM para datos horarios
        url = "https://servapibi.xm.com.co/hourly"
        
        # Cuerpo de la petición (exactamente lo que pide XM)
        payload = {
            "MetricId": "DemandaReal",
            "StartDate": str(ayer),
            "EndDate": str(hoy),
            "Entity": "Sistema"
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        items = data.get('Items', [])
        
        if not items:
            return None

        # Procesar los datos de formato "ancho" a "largo"
        all_records = []
        for item in items:
            fecha_str = item['Date']
            # XM devuelve Hour01, Hour02... Hour24
            for h in range(1, 25):
                hour_key = f'Hour{str(h).zfill(2)}'
                valor = item.get(hour_key)
                if valor is not None:
                    # Crear el timestamp exacto
                    ts = pd.to_datetime(fecha_str) + pd.to_timedelta(h-1, unit='h')
                    all_records.append({'Timestamp': ts, 'Demanda': valor})
        
        df = pd.DataFrame(all_records).sort_values('Timestamp')
        return df
    except Exception as e:
        print(f"Error: {e}")
        return None

# --- CALLBACK PARA ACTUALIZACIÓN ---
@app.callback(
    [Output('live-graph-demanda', 'figure'),
     Output('live-update-text', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_graph_live(n):
    df = fetch_xm_data()
    
    if df is None or df.empty:
        return go.Figure(), "Esperando datos de XM..."

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Timestamp'], y=df['Demanda'],
        mode='lines',
        line=dict(color='#007bff', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 123, 255, 0.1)',
        name='Demanda (MW)'
    ))

    fig.update_layout(
        xaxis=dict(gridcolor='#eee', title="Hora"),
        yaxis=dict(gridcolor='#eee', title="MW"),
        plot_bgcolor='white',
        margin=dict(l=0, r=0, t=20, b=0),
        hovermode="x unified"
    )

    now = datetime.datetime.now().strftime("%I:%M %p")
    return fig, f"Última lectura: {now} (Actualización automática cada 5 min)"

if __name__ == '__main__':
    app.run_server(debug=False)
