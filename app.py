import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

# 1. Inicializar la App y el Servidor inmediatamente
app = dash.Dash(__name__)
server = app.server 
app.title = "Demanda XM Colombia"

# 2. Definir el Layout PRIMERO (para que nunca sea None)
app.layout = html.Div(style={'fontFamily': 'Arial, sans-serif', 'padding': '20px', 'backgroundColor': '#f8f9fa'}, children=[
    html.Div(style={'maxWidth': '1000px', 'margin': '0 auto', 'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}, children=[
        html.H2("Demanda de Energía en Tiempo Real (SIN)", style={'textAlign': 'center', 'color': '#2c3e50'}),
        html.P(id='live-update-text', style={'textAlign': 'center', 'color': '#7f8c8d'}, children="Cargando datos desde XM..."),
        
        dcc.Graph(
            id='live-graph-demanda', 
            config={'displayModeBar': False},
            figure=go.Figure() # Figura vacía inicial
        ),
        
        dcc.Interval(
            id='interval-component',
            interval=5*60*1000, # 5 minutos
            n_intervals=0
        )
    ])
])

# 3. Función robusta para traer datos (Sin librerías externas)
def fetch_xm_data():
    try:
        hoy = datetime.datetime.now().date()
        ayer = hoy - datetime.timedelta(days=1)
        url = "https://servapibi.xm.com.co/hourly"
        
        payload = {
            "MetricId": "DemandaReal",
            "StartDate": str(ayer),
            "EndDate": str(hoy),
            "Entity": "Sistema"
        }
        
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200: return None
        
        items = response.json().get('Items', [])
        if not items: return None

        recs = []
        for item in items:
            d = item['Date']
            for h in range(1, 25):
                val = item.get(f'Hour{str(h).zfill(2)}')
                if val is not None:
                    ts = pd.to_datetime(d) + pd.to_timedelta(h-1, unit='h')
                    recs.append({'Timestamp': ts, 'MW': val})
        
        return pd.DataFrame(recs).sort_values('Timestamp')
    except Exception as e:
        print(f"Error API: {e}")
        return None

# 4. Callback para actualizar la gráfica
@app.callback(
    [Output('live-graph-demanda', 'figure'),
     Output('live-update-text', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    df = fetch_xm_data()
    
    if df is None or df.empty:
        return go.Figure(), "Error de conexión con XM. Reintentando..."

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Timestamp'], y=df['MW'],
        mode='lines+markers',
        line=dict(color='#007bff', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 123, 255, 0.1)',
        name='Demanda Real'
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(showgrid=True, gridcolor='#eee'),
        yaxis=dict(title="Megavatios (MW)", showgrid=True, gridcolor='#eee'),
        plot_bgcolor='white',
        hovermode="x unified"
    )

    status = f"Última actualización: {datetime.datetime.now().strftime('%H:%M:%S')}"
    return fig, status

if __name__ == '__main__':
    app.run_server(debug=False)
