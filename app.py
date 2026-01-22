import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests
import re
import json

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div(style={'backgroundColor': '#020617', 'minHeight': '100vh', 'color': 'white', 'fontFamily': 'sans-serif'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '20px'}, children=[
        html.H2("⚡ MONITOR NACIONAL DE ENERGÍA", style={'color': '#38bdf8', 'letterSpacing': '2px'}),
        html.Div(id='status-log', style={'fontSize': '12px', 'color': '#94a3b8', 'marginBottom': '20px'}),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False})),
        
        html.Div(style={'display': 'flex', 'gap': '20px', 'marginTop': '20px'}, children=[
            html.Div(style={'flex': '1', 'backgroundColor': '#0f172a', 'padding': '20px', 'borderRadius': '10px'}, children=[
                html.P("DEMANDA ACTUAL (MW)", style={'fontSize': '12px', 'color': '#94a3b8'}),
                html.H1(id='val-real', style={'margin': '0', 'color': '#f8fafc'})
            ]),
            html.Div(style={'flex': '1', 'backgroundColor': '#0f172a', 'padding': '20px', 'borderRadius': '10px'}, children=[
                html.P("FUENTE DE DATOS", style={'fontSize': '12px', 'color': '#94a3b8'}),
                html.H3(id='val-fuente', style={'margin': '0', 'color': '#38bdf8'})
            ])
        ]),
        dcc.Interval(id='refresh', interval=120*1000, n_intervals=0)
    ])
])

# --- EL MOTOR DE EXTRACCIÓN ROBUSTO ---

def get_realtime_data():
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=utf-8',
        'Referer': 'https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx'
    }

    try:
        # PASO 1: Obtener cookies de sesión entrando a la página principal
        print("Intentando obtener sesión de Sinergox...")
        landing = session.get("https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx", timeout=15)
        
        # PASO 2: Intentar el servicio WCF con la sesión activa
        service_url = "https://sinergox.xm.com.co/dmnd/_vti_bin/XM.Sinergox.Servicios/Demanda.svc/GetDemandaRT"
        response = session.post(service_url, headers=headers, data="{}", timeout=15)
        
        if response.status_code == 200 and "GetDemandaRTResult" in response.text:
            data = response.json()['GetDemandaRTResult']
            df = pd.DataFrame(data['DemandaReal'])
            
            def parse_date(d):
                ms = int(re.search(r'\d+', d).group())
                return pd.to_datetime(ms, unit='ms') - pd.Timedelta(hours=5)

            df['fecha'] = df['Fecha'].apply(parse_date)
            return df, "Sinergox (5 min)"

    except Exception as e:
        print(f"Sinergox falló: {e}")

    # PASO 3: FALLBACK INTELIGENTE (API de Resumen Diario - Granularidad Alta)
    # Si Sinergox bloquea, esta es la fuente que usa la App Móvil de XM
    try:
        print("Cambiando a Fuente de Resumen XM...")
        res_url = "https://servapibi.xm.com.co/hourly"
        payload = {
            "MetricId": "DemaReal",
            "StartDate": str(datetime.datetime.now().date()),
            "EndDate": str(datetime.datetime.now().date()),
            "Entity": "Sistema"
        }
        res = requests.post(res_url, json=payload, timeout=10)
        if res.status_code == 200:
            items = res.json().get('Items', [])
            records = []
            for item in items:
                f = item['Date']
                for h in range(1, 25):
                    v = item.get(f'Hour{str(h).zfill(2)}')
                    if v is not None:
                        ts = pd.to_datetime(f) + pd.to_timedelta(h-1, unit='h')
                        records.append({'fecha': ts, 'Valor': v})
            return pd.DataFrame(records), "XM API (Horaria)"
    except:
        pass

    return None, "Error de Conexión"

# --- CALLBACKS ---

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), Output('val-fuente', 'children'), Output('status-log', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df, fuente = get_realtime_data()
    
    if df is None or df.empty:
        return go.Figure(), "---", fuente, f"Último intento: {datetime.datetime.now().strftime('%H:%M:%S')} - Fallido"

    v_actual = df['Valor'].iloc[-1]
    
    fig = go.Figure(go.Scatter(
        x=df['fecha'], y=df['Valor'],
        mode='lines+markers' if len(df) < 50 else 'lines',
        line=dict(color='#38bdf8', width=3),
        fill='tozeroy',
        fillcolor='rgba(56, 189, 248, 0.05)',
        name='MW'
    ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=True, gridcolor='#1e293b'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b')
    )

    log = f"Conexión exitosa a las {datetime.datetime.now().strftime('%H:%M:%S')}"
    return fig, f"{v_actual:,.0f}", fuente, log

if __name__ == '__main__':
    app.run_server(debug=False)
