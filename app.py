import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests
import re
from bs4 import BeautifulSoup
import json

app = dash.Dash(__name__)
server = app.server 

# --- INTERFAZ DE SALA DE CONTROL ---
app.layout = html.Div(style={'backgroundColor': '#020617', 'minHeight': '100vh', 'color': 'white', 'fontFamily': 'monospace'}, children=[
    html.Div(style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '20px'}, children=[
        html.Div(style={'borderLeft': '4px solid #38bdf8', 'paddingLeft': '15px', 'marginBottom': '30px'}, children=[
            html.H1("MONITOR DE DEMANDA - SIN COLOMBIA", style={'margin': '0', 'fontSize': '22px', 'letterSpacing': '2px'}),
            html.P("EXTRACCIÓN DE ALTA RESOLUCIÓN (Sinergox RT)", style={'color': '#38bdf8', 'margin': '5px 0 0 0'})
        ]),
        
        dcc.Loading(children=dcc.Graph(id='rt-graph', config={'displayModeBar': False})),
        
        html.Div(style={'display': 'flex', 'gap': '20px', 'marginTop': '20px'}, children=[
            html.Div(style={'flex': '1', 'backgroundColor': '#0f172a', 'padding': '20px', 'borderRadius': '8px'}, children=[
                html.P("ÚLTIMA LECTURA REAL", style={'color': '#94a3b8', 'fontSize': '12px'}),
                html.H2(id='val-real', style={'color': '#f8fafc', 'margin': '0'})
            ]),
            html.Div(style={'flex': '1', 'backgroundColor': '#0f172a', 'padding': '20px', 'borderRadius': '8px'}, children=[
                html.P("STATUS DEL SCRAPER", style={'color': '#94a3b8', 'fontSize': '12px'}),
                html.H2(id='status-scrap', style={'fontSize': '18px', 'margin': '0'})
            ])
        ]),
        
        dcc.Interval(id='refresh', interval=5*60*1000, n_intervals=0)
    ])
])

# --- SCRAPER INTELIGENTE ---

def scrape_sinergox():
    url = "https://sinergox.xm.com.co/dmnd/Paginas/Informes/Demanda_Tiempo_Real.aspx"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return None, f"Error Acceso: {response.status_code}"

        # Usamos BeautifulSoup para buscar los scripts
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        data_json = None
        # Buscamos el script que contiene los datos de la gráfica
        for script in scripts:
            if script.string and 'dataReal' in script.string:
                # Usamos Regex para extraer el contenido de la variable dataReal
                # Buscamos algo como: var dataReal = [...];
                match = re.search(r'var dataReal\s*=\s*(\[.*?\]);', script.string, re.DOTALL)
                if match:
                    data_json = match.group(1)
                    break
        
        if not data_json:
            return None, "No se encontró la variable dataReal en el HTML"

        # Limpiar y parsear el JSON extraído
        # Los JSON de XM suelen tener fechas en formato /Date(...)/
        raw_list = json.loads(data_json)
        
        records = []
        for item in raw_list:
            # Extraer milisegundos de "/Date(1737482400000)/"
            ms_str = re.search(r'\((\d+)\)', item['Fecha']).group(1)
            ts = pd.to_datetime(int(ms_str), unit='ms') - pd.Timedelta(hours=5)
            records.append({'fecha': ts, 'valor': item['Valor']})
            
        return pd.DataFrame(records).sort_values('fecha'), "CONECTADO"

    except Exception as e:
        return None, f"Fallo: {str(e)}"

# --- CALLBACKS ---

@app.callback(
    [Output('rt-graph', 'figure'), Output('val-real', 'children'), Output('status-scrap', 'children'), Output('status-scrap', 'style')],
    [Input('refresh', 'n_intervals')]
)
def update_dashboard(n):
    df, status = scrape_sinergox()
    
    if df is None or df.empty:
        return go.Figure(), "---", status, {'color': '#ef4444'}

    v_actual = df['valor'].iloc[-1]
    
    # Crear gráfica estilizada
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['fecha'], y=df['valor'],
        mode='lines',
        line=dict(color='#38bdf8', width=3),
        fill='tozeroy',
        fillcolor='rgba(56, 189, 248, 0.05)',
        hovertemplate='%{y:.1f} MW<br>%{x|%H:%M}<extra></extra>'
    ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=0, t=10, b=30),
        xaxis=dict(showgrid=True, gridcolor='#1e293b', tickformat='%H:%M'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', zeroline=False),
    )

    return fig, f"{v_actual:,.0f} MW", f"● {status}", {'color': '#22c55e'}

if __name__ == '__main__':
    app.run_server(debug=False)
