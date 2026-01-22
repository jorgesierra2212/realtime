import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
from playwright.sync_api import sync_playwright
import re

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div(style={'backgroundColor': '#020617', 'minHeight': '100vh', 'color': 'white', 'padding': '20px'}, children=[
    html.Div(style={'maxWidth': '1100px', 'margin': '0 auto'}, children=[
        html.H2("⚡ MONITOR SINERGORX - EXTRACCIÓN POR NAVEGADOR", style={'color': '#38bdf8', 'textAlign': 'center'}),
        html.P(id='status-log', style={'textAlign': 'center', 'fontSize': '12px', 'color': '#94a3b8'}),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False})),
        
        html.Div(style={'display': 'flex', 'justifyContent': 'space-around', 'marginTop': '20px', 'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '10px'}, children=[
            html.Div([html.P("DEMANDA ACTUAL", style={'color': '#94a3b8', 'margin': '0'}), html.H2(id='val-real')]),
            html.Div([html.P("MÉTODO", style={'color': '#94a3b8', 'margin': '0'}), html.H3("Browser Emulation", style={'color': '#38bdf8'})])
        ]),
        
        dcc.Interval(id='refresh', interval=180*1000, n_intervals=0) # Cada 3 min
    ])
])

def get_data_via_browser():
    """Simula un humano abriendo el navegador y extrayendo los datos de la gráfica"""
    url = "https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx"
    
    try:
        with sync_playwright() as p:
            # 1. Lanzamos el navegador
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 2. Navegamos (esto obtiene las cookies de sesión automáticamente)
            print(f"Navegando a {url}...")
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # 3. Esperamos a que la gráfica exista en el DOM
            page.wait_for_selector(".highcharts-container", timeout=30000)
            
            # 4. TRUCO MAESTRO: Ejecutamos JS para obtener los datos que Highcharts tiene en memoria
            # Esto es equivalente a "pasar el cursor" y leer todos los puntos
            script = """
            () => {
                if (typeof Highcharts !== 'undefined' && Highcharts.charts.length > 0) {
                    let chart = Highcharts.charts.find(c => c && c.series.length > 0);
                    let series = chart.series.find(s => s.name.includes('Real'));
                    return series.options.data.map(p => ({fecha: p.Fecha, valor: p.Valor}));
                }
                return null;
            }
            """
            data = page.evaluate(script)
            browser.close()
            
            if not data:
                return None, "Gráfica cargada pero vacía"

            df = pd.DataFrame(data)
            
            # Limpiar fechas de formato /Date(ms)/
            def parse_date(d):
                ms = int(re.search(r'\d+', d).group())
                return pd.to_datetime(ms, unit='ms') - pd.Timedelta(hours=5)

            df['fecha'] = df['fecha'].apply(parse_date)
            return df.sort_values('fecha'), "OK"

    except Exception as e:
        return None, f"Fallo de Navegador: {str(e)}"

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), Output('status-log', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df, status = get_data_via_browser()
    
    if df is None or df.empty:
        return go.Figure(), "---", f"Status: {status}"

    v_r = df['valor'].iloc[-1]

    fig = go.Figure(go.Scatter(
        x=df['fecha'], y=df['valor'],
        name='Demanda Real', line=dict(color='#38bdf8', width=3),
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

    log = f"Extracción exitosa vía Browser a las {datetime.datetime.now().strftime('%H:%M:%S')}"
    return fig, f"{v_r:,.0f} MW", log

if __name__ == '__main__':
    app.run_server(debug=False)
