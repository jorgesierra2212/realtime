import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests
import json

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div(style={'backgroundColor': '#0b0f19', 'minHeight': '100vh', 'color': 'white', 'padding': '20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        html.H2("DEMANDA SIN COLOMBIA - TIEMPO REAL (5 MIN)", style={'color': '#38bdf8', 'textAlign': 'center'}),
        html.P(id='debug-info', style={'textAlign': 'center', 'fontSize': '12px', 'color': '#94a3b8'}),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False})),
        
        html.Div(style={'display': 'flex', 'justifyContent': 'space-around', 'marginTop': '20px'}, children=[
            html.Div([html.P("REAL", style={'color': '#94a3b8'}), html.H3(id='val-real')]),
            html.Div([html.P("PROGRAMADA", style={'color': '#94a3b8'}), html.H3(id='val-prog')])
        ]),
        
        dcc.Interval(id='refresh', interval=120*1000, n_intervals=0) # Cada 2 min
    ])
])

def fetch_data():
    # URL técnica detectada en la consola de Sinergox
    url = "https://sinergox.xm.com.co/dmnd/_vti_bin/XM.Sinergox.Servicios/Demanda.svc/GetDemandaRT"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=utf-8',
        'Referer': 'https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        # Importante: XM requiere POST con cuerpo vacío {}
        response = requests.post(url, headers=headers, data="{}", timeout=20)
        
        if response.status_code != 200:
            return None, None, f"Error XM: {response.status_code}"

        # Validar si recibimos JSON o HTML (error de firewall)
        if "<html>" in response.text.lower():
            return None, None, "Bloqueo Geográfico: XM bloqueó la IP del servidor."

        raw = response.json()
        res = raw.get('GetDemandaRTResult', {})
        
        # Limpieza de fechas de formato WCF /Date(ms)/
        def parse_date(d):
            ms = int(d.split('(')[1].split(')')[0])
            # Ajuste UTC-5 (Colombia)
            return pd.to_datetime(ms, unit='ms') - pd.Timedelta(hours=5)

        df_real = pd.DataFrame(res.get('DemandaReal', []))
        df_prog = pd.DataFrame(res.get('DemandaProgramada', []))

        if not df_real.empty:
            df_real['fecha'] = df_real['Fecha'].apply(parse_date)
        if not df_prog.empty:
            df_prog['fecha'] = df_prog['Fecha'].apply(parse_date)

        return df_real, df_prog, "OK"

    except Exception as e:
        return None, None, f"Error conexión: {str(e)}"

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), 
     Output('val-prog', 'children'), Output('debug-info', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df_r, df_p, status = fetch_data()
    
    if df_r is None or df_r.empty:
        return go.Figure(), "---", "---", f"Status: {status}"

    v_r = df_r['Valor'].iloc[-1]
    v_p = df_p['Valor'].iloc[-1] if not df_p.empty else 0

    fig = go.Figure()
    # Programada
    if not df_p.empty:
        fig.add_trace(go.Scatter(x=df_p['fecha'], y=df_p['Valor'], name='Programada', 
                                 line=dict(color='#475569', dash='dot')))
    # Real
    fig.add_trace(go.Scatter(x=df_r['fecha'], y=df_r['Valor'], name='Real', 
                             line=dict(color='#38bdf8', width=3), fill='tozeroy',
                             fillcolor='rgba(56, 189, 248, 0.1)'))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=True, gridcolor='#1e293b'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', title="MW")
    )

    return fig, f"{v_r:,.0f} MW", f"{v_p:,.0f} MW", f"Última actualización: {datetime.datetime.now().strftime('%H:%M:%S')}"

if __name__ == '__main__':
    app.run_server(debug=False)
