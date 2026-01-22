import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

app = dash.Dash(__name__)
server = app.server 

app.layout = html.Div([
    html.H2("Dashboard Demanda XM (Auto-Descubrimiento)", style={'textAlign': 'center'}),
    html.Div(id='status-bar', style={'textAlign': 'center', 'padding': '10px', 'color': 'blue'}),
    dcc.Graph(id='main-graph'),
    dcc.Interval(id='refresh', interval=5*60*1000, n_intervals=0)
])

def discover_metrics():
    """Consulta el catálogo oficial de XM para ver los nombres reales de las métricas"""
    try:
        url = "https://servapibi.xm.com.co/lists"
        payload = {"MetricId": "ListadoMetricas"}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            metrics = res.json().get('Items', [])
            # Buscamos cualquier métrica que hable de Demanda
            demanda_metrics = [m['MetricId'] for m in metrics if 'Demanda' in str(m.get('MetricName', ''))]
            print(f"🔎 CATÁLOGO XM ENCONTRADO: {demanda_metrics}")
            return demanda_metrics
        return []
    except:
        return []

def get_xm_data():
    # Paso 1: Intentar con los nombres técnicos cortos más probables
    # Según el estándar XM BI: 'DemaReal' es Demanda Real, 'DemanComer' es Comercial
    target_metrics = ["DemaReal", "DemanComer", "Dema"] 
    
    # Paso 2: Intentar descubrir si hay otros nombres en el catálogo
    catalog = discover_metrics()
    for m in catalog:
        if m not in target_metrics: target_metrics.append(m)

    end_date = datetime.datetime.now().date()
    start_date = end_date - datetime.timedelta(days=2)
    
    for metric in target_metrics:
        try:
            url = "https://servapibi.xm.com.co/hourly"
            payload = {
                "MetricId": metric,
                "StartDate": str(start_date),
                "EndDate": str(end_date),
                "Entity": "Sistema"
            }
            print(f"🚀 Probando MetricId: {metric}...")
            r = requests.post(url, json=payload, timeout=15)
            
            if r.status_code == 200:
                items = r.json().get('Items', [])
                if items:
                    print(f"✅ ÉXITO con: {metric}")
                    data = []
                    for item in items:
                        fecha = item['Date']
                        for h in range(1, 25):
                            v = item.get(f'Hour{str(h).zfill(2)}')
                            if v is not None:
                                ts = pd.to_datetime(fecha) + pd.to_timedelta(h-1, unit='h')
                                data.append({'TS': ts, 'Val': v})
                    return pd.DataFrame(data).sort_values('TS'), metric
            else:
                print(f"❌ {metric} falló con status {r.status_code}")
        except Exception as e:
            print(f"⚠ Error en {metric}: {e}")
            
    return None, None

@app.callback(
    [Output('main-graph', 'figure'), Output('status-bar', 'children')],
    [Input('refresh', 'n_intervals')]
)
def update(n):
    df, metric_name = get_xm_data()
    
    if df is None:
        return go.Figure(), "❌ No se encontró la métrica en el catálogo de XM. Revisa logs."

    fig = go.Figure(go.Scatter(x=df['TS'], y=df['Val'], fill='tozeroy', line=dict(color='#00CC96')))
    fig.update_layout(title=f"Demanda detectada vía: {metric_name}", plot_bgcolor='white')
    
    return fig, f"Actualizado: {datetime.datetime.now().strftime('%H:%M')} | Métrica: {metric_name}"

if __name__ == '__main__':
    app.run_server(debug=False)
