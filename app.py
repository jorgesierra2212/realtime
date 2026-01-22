import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests
import json

app = dash.Dash(__name__)
server = app.server 
app.title = "XM | Monitor Tiempo Real"

# --- DISEÑO ---
app.layout = html.Div(style={'backgroundColor': '#0b0f19', 'minHeight': '100vh', 'color': 'white', 'padding': '20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        html.H2("DEMANDA SIN COLOMBIA - TIEMPO REAL (5 MIN)", style={'color': '#38bdf8', 'textAlign': 'center', 'margin': '0'}),
        html.P(id='debug-info', style={'textAlign': 'center', 'fontSize': '12px', 'color': '#94a3b8', 'marginBottom': '20px'}),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False})),
        
        html.Div(style={'display': 'flex', 'justifyContent': 'space-around', 'marginTop': '20px', 'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '10px'}, children=[
            html.Div([html.P("REAL", style={'color': '#94a3b8', 'margin': '0'}), html.H2(id='val-real', style={'color': '#f8fafc'})]),
            html.Div([html.P("PROGRAMADA", style={'color': '#94a3b8', 'margin': '0'}), html.H2(id='val-prog', style={'color': '#64748b'})])
        ]),
        
        dcc.Interval(id='refresh', interval=120*1000, n_intervals=0)
    ])
])

def fetch_data():
    # Rutas posibles para el servicio de tiempo real de XM
    urls = [
        "https://sinergox.xm.com.co/_vti_bin/XM.Sinergox.Servicios/Demanda.svc/GetDemandaRT",
        "https://sinergox.xm.com.co/dmnd/Servicios/Demanda.svc/GetDemandaRT"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=utf-8',
        'X-Requested-With': 'XMLHttpRequest'
    }

    last_status = ""
    for url in urls:
        try:
            # Enviamos POST con cuerpo {} como requiere el servicio .svc
            response = requests.post(url, headers=headers, data="{}", timeout=15)
            
            if response.status_code == 200:
                raw = response.json()
                res = raw.get('GetDemandaRTResult', {})
                
                def parse_date(d):
                    # Extraer milisegundos de /Date(123456789)/
                    ms = int(d.split('(')[1].split(')')[0])
                    return pd.to_datetime(ms, unit='ms') - pd.Timedelta(hours=5)

                df_real = pd.DataFrame(res.get('DemandaReal', []))
                df_prog = pd.DataFrame(res.get('DemandaProgramada', []))

                if not df_real.empty:
                    df_real['fecha'] = df_real['Fecha'].apply(parse_date)
                    df_prog['fecha'] = df_prog['Fecha'].apply(parse_date) if not df_prog.empty else None
                    return df_real, df_prog, "OK"
            
            last_status = f"Status {response.status_code} en {url.split('/')[-3]}"
        except Exception as e:
            last_status = f"Error: {str(e)}"
            
    return None, None, last_status

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), 
     Output('val-prog', 'children'), Output('debug-info', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df_r, df_p, status = fetch_data()
    
    if df_r is None or df_r.empty:
        return go.Figure(), "---", "---", f"Intento de conexión: {status}"

    # Últimos valores
    v_r = df_r['Valor'].iloc[-1]
    # Buscar el valor programado para la misma hora que el real
    v_p = df_p['Valor'].iloc[-1] if not df_p.empty else 0

    fig = go.Figure()
    
    # Capa Programada
    if not df_p.empty:
        fig.add_trace(go.Scatter(
            x=df_p['fecha'], y=df_p['Valor'], 
            name='Programada', line=dict(color='#475569', dash='dot', width=1)
        ))
    
    # Capa Real
    fig.add_trace(go.Scatter(
        x=df_r['fecha'], y=df_r['Valor'], 
        name='Demanda Real', line=dict(color='#38bdf8', width=3),
        fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'
    ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=0, t=10, b=0),
        xaxis=dict(showgrid=True, gridcolor='#1e293b', tickformat='%H:%M'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', title="MW"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig, f"{v_r:,.0f} MW", f"{v_p:,.0f} MW", f"Servicio Activo | Refresco: {datetime.datetime.now().strftime('%H:%M:%S')}"

if __name__ == '__main__':
    app.run_server(debug=False)
