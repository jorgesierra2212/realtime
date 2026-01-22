import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
from playwright.sync_api import sync_playwright
import re
import os

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div(style={'backgroundColor': '#020617', 'minHeight': '100vh', 'color': 'white', 'fontFamily': 'sans-serif', 'padding': '20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        html.H2("⚡ DEMANDA SIN COLOMBIA (5 MIN) - XM", style={'color': '#38bdf8', 'textAlign': 'center'}),
        html.P(id='status-log', style={'textAlign': 'center', 'fontSize': '12px', 'color': '#94a3b8'}),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False}, style={'height': '500px'})),
        
        html.Div(style={'display': 'flex', 'justifyContent': 'center', 'marginTop': '20px'}, children=[
            html.Div(style={'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '10px', 'textAlign': 'center', 'minWidth': '300px'}, children=[
                html.P("ÚLTIMA DEMANDA REAL", style={'color': '#94a3b8', 'margin': '0'}),
                html.H1(id='val-real', style={'color': '#f8fafc', 'margin': '10px 0'})
            ])
        ]),
        
        dcc.Interval(id='refresh', interval=180*1000, n_intervals=0) # Refresco cada 3 min
    ])
])

def get_data_via_browser():
    url = "https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx"
    
    try:
        with sync_playwright() as p:
            # Lanzamos navegador con argumentos para evitar bloqueos
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            
            print(f"Abriendo Sinergox...")
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Esperamos a que la gráfica se dibuje (Highcharts)
            page.wait_for_selector(".highcharts-series-group", timeout=30000)
            
            # EXTRACCIÓN MAESTRA: Obtenemos los datos directamente del objeto Highcharts en memoria
            script = """
            () => {
                let chart = Highcharts.charts.find(c => c && c.series.length > 0);
                let seriesReal = chart.series.find(s => s.name.toLowerCase().includes('real'));
                return seriesReal.data.map(p => ({ x: p.x, y: p.y }));
            }
            """
            raw_points = page.evaluate(script)
            browser.close()
            
            if not raw_points:
                return None, "Gráfica encontrada pero sin puntos"

            df = pd.DataFrame(raw_points)
            # XM entrega el tiempo en milisegundos UTC. Convertimos a Colombia (UTC-5)
            df['fecha'] = pd.to_datetime(df['x'], unit='ms') - pd.Timedelta(hours=5)
            df = df.rename(columns={'y': 'valor'})
            
            return df.sort_values('fecha'), "OK"

    except Exception as e:
        return None, f"Error de captura: {str(e)}"

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), Output('status-log', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df, status = get_data_via_browser()
    
    if df is None or df.empty:
        return go.Figure(), "---", f"Status: {status}"

    v_actual = df['valor'].iloc[-1]

    fig = go.Figure(go.Scatter(
        x=df['fecha'], y=df['valor'],
        mode='lines',
        line=dict(color='#38bdf8', width=3),
        fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'
    ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=10, b=30),
        xaxis=dict(showgrid=True, gridcolor='#1e293b', tickformat='%H:%M'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', title="MW")
    )

    log = f"Captura exitosa: {datetime.datetime.now().strftime('%H:%M:%S')}"
    return fig, f"{v_actual:,.0f} MW", log

if __name__ == '__main__':
    # Render usa la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    app.run_server(host='0.0.0.0', port=port, debug=False)
