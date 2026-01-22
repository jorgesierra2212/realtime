import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests
import json

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div(style={'fontFamily': 'Arial', 'padding': '20px'}, children=[
    html.H2("Monitor de Demanda XM - Diagnóstico", style={'textAlign': 'center'}),
    html.Div(id='debug-status', style={'color': 'red', 'textAlign': 'center', 'marginBottom': '20px'}),
    dcc.Graph(id='live-graph-demanda'),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0) # Reintentar cada minuto
])

def fetch_xm_data(metric="DemandaReal"):
    try:
        # XM a veces no tiene datos de "hoy" hasta muy tarde. 
        # Consultamos los últimos 3 días para asegurar que traiga algo.
        end_date = datetime.datetime.now().date()
        start_date = end_date - datetime.timedelta(days=3)
        
        url = "https://servapibi.xm.com.co/hourly"
        payload = {
            "MetricId": metric,
            "StartDate": str(start_date),
            "EndDate": str(end_date),
            "Entity": "Sistema"
        }
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0' # Engañar al servidor para que no crea que es un bot simple
        }

        print(f"--- Intentando MetricId: {metric} ---")
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        # LOGS PARA RENDER (Ver en la consola de Render)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error de XM: {response.text}")
            return None, f"Error API XM: Código {response.status_code}"

        data = response.json()
        items = data.get('Items', [])

        if not items:
            print(f"Aviso: La métrica {metric} respondió 200 pero no trajo datos (lista vacía).")
            return None, f"Variable {metric} sin datos en este rango de fechas."

        recs = []
        for item in items:
            d = item['Date']
            for h in range(1, 25):
                val = item.get(f'Hour{str(h).zfill(2)}')
                if val is not None:
                    ts = pd.to_datetime(d) + pd.to_timedelta(h-1, unit='h')
                    recs.append({'Timestamp': ts, 'MW': val})
        
        df = pd.DataFrame(recs).sort_values('Timestamp')
        print(f"Éxito: {len(df)} registros recuperados.")
        return df, "OK"

    except Exception as e:
        print(f"Error crítico en la petición: {str(e)}")
        return None, str(e)

@app.callback(
    [Output('live-graph-demanda', 'figure'),
     Output('debug-status', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    # Intento 1: Demanda Real
    df, msg = fetch_xm_data("DemandaReal")
    
    # Intento 2 (Fallback): Generación Real (si la demanda falla)
    if df is None:
        print("Reintentando con métrica alternativa: GeneracionReal")
        df, msg = fetch_xm_data("GeneracionReal")
    
    if df is None:
        return go.Figure(), f"FALLO TOTAL: {msg}. Revisa los Logs de Render."

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['MW'], name='Valor Real'))
    fig.update_layout(title=f"Datos recuperados ({datetime.datetime.now().strftime('%H:%M')})", plot_bgcolor='white')
    
    return fig, f"Conectado. Mostrando datos de: {msg if msg != 'OK' else 'Demanda Real'}"

if __name__ == '__main__':
    app.run_server(debug=False)
