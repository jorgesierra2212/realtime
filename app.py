import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import datetime
import requests

app = dash.Dash(__name__)
server = app.server 
app.title = "XM | Demanda Tiempo Real"

# --- DISEÑO TIPO MONITOR DE OPERACIÓN ---
app.layout = html.Div(style={
    'fontFamily': '"Segoe UI", Roboto, sans-serif', 
    'backgroundColor': '#0b0f19', 
    'minHeight': '100vh', 
    'padding': '30px', 
    'color': '#f8fafc'
}, children=[
    html.Div(style={'maxWidth': '1200px', 'margin': '0 auto'}, children=[
        
        # Header
        html.Div(style={
            'display': 'flex', 'justifyContent': 'space-between', 
            'alignItems': 'center', 'borderBottom': '1px solid #1e293b', 
            'paddingBottom': '20px', 'marginBottom': '30px'
        }, children=[
            html.Div([
                html.H1("SISTEMA INTERCONECTADO NACIONAL", style={'margin': '0', 'fontSize': '20px', 'letterSpacing': '1px', 'color': '#38bdf8'}),
                html.H2("Demanda de Energía en Tiempo Real (5 min)", style={'margin': '5px 0 0 0', 'fontSize': '14px', 'fontWeight': '400', 'color': '#94a3b8'})
            ]),
            html.Div(id='live-clock', style={'textAlign': 'right', 'fontFamily': 'monospace', 'fontSize': '18px', 'color': '#38bdf8'})
        ]),

        # Tarjetas de datos rápidos
        html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(250px, 1fr))', 'gap': '20px', 'marginBottom': '30px'}, children=[
            html.Div(style={'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '12px', 'border': '1px solid #1e293b'}, children=[
                html.P("DEMANDA ACTUAL", style={'margin': '0', 'fontSize': '12px', 'color': '#94a3b8', 'fontWeight': 'bold'}),
                html.H3(id='val-real', style={'margin': '10px 0 0 0', 'fontSize': '32px', 'color': '#f8fafc'})
            ]),
            html.Div(style={'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '12px', 'border': '1px solid #1e293b'}, children=[
                html.P("PROGRAMADA", style={'margin': '0', 'fontSize': '12px', 'color': '#94a3b8', 'fontWeight': 'bold'}),
                html.H3(id='val-prog', style={'margin': '10px 0 0 0', 'fontSize': '32px', 'color': '#64748b'})
            ]),
            html.Div(style={'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '12px', 'border': '1px solid #1e293b'}, children=[
                html.P("DESVIACIÓN", style={'margin': '0', 'fontSize': '12px', 'color': '#94a3b8', 'fontWeight': 'bold'}),
                html.H3(id='val-desv', style={'margin': '10px 0 0 0', 'fontSize': '32px'})
            ])
        ]),

        # Gráfica
        html.Div(style={'backgroundColor': '#111827', 'padding': '20px', 'borderRadius': '16px', 'border': '1px solid #1e293b'}, children=[
            dcc.Loading(
                color="#38bdf8",
                children=dcc.Graph(id='rt-graph', config={'displayModeBar': False}, style={'height': '550px'})
            )
        ]),

        # Refresco cada 1 minuto (XM actualiza cada 5, pero así aseguramos capturar el cambio rápido)
        dcc.Interval(id='refresh-interval', interval=60*1000, n_intervals=0)
    ])
])

# --- OBTENCIÓN DE DATOS TIEMPO REAL ---

def fetch_sinergox_rt():
    try:
        url = "https://sinergox.xm.com.co/_vti_bin/XM.Sinergox.Servicios/Demanda.svc/GetDemandaRT"
        # Sinergox requiere un User-Agent de navegador para no bloquear
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, headers=headers, timeout=15)
        raw_data = response.json()
        
        # El JSON de Sinergox tiene una estructura: GetDemandaRTResult -> DemandaReal, DemandaProgramada, etc.
        result = raw_data.get('GetDemandaRTResult', {})
        
        # Procesar Demanda Real
        real = pd.DataFrame(result.get('DemandaReal', []))
        prog = pd.DataFrame(result.get('DemandaProgramada', []))
        
        # Sinergox envía tiempo en formato "/Date(1737424800000)/"
        def clean_date(d):
            return pd.to_datetime(int(d.split('(')[1].split(')')[0]), unit='ms') - pd.Timedelta(hours=5)

        real['fecha'] = real['Fecha'].apply(clean_date)
        prog['fecha'] = prog['Fecha'].apply(clean_date)
        
        return real, prog
    except Exception as e:
        print(f"Error Sinergox: {e}")
        return None, None

# --- CALLBACKS ---

@app.callback(
    [Output('rt-graph', 'figure'),
     Output('val-real', 'children'),
     Output('val-prog', 'children'),
     Output('val-desv', 'children'),
     Output('val-desv', 'style'),
     Output('live-clock', 'children')],
    [Input('refresh-interval', 'n_intervals')]
)
def update_dashboard(n):
    df_real, df_prog = fetch_sinergox_rt()
    now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
    
    if df_real is None or df_real.empty:
        return go.Figure(), "---", "---", "0%", {'color': 'white'}, now_str

    # Valores actuales
    v_real = df_real['Valor'].iloc[-1]
    v_prog = df_prog[df_prog['fecha'] == df_real['fecha'].iloc[-1]]['Valor'].iloc[0] if not df_prog.empty else v_real
    
    desv = ((v_real - v_prog) / v_prog) * 100
    desv_color = '#ef4444' if abs(desv) > 5 else '#22c55e'

    # Crear Figura
    fig = go.Figure()

    # Serie Programada (Línea punteada gris)
    fig.add_trace(go.Scatter(
        x=df_prog['fecha'], y=df_prog['Valor'],
        name='Programada', line=dict(color='#475569', width=2, dash='dot'),
        hoverinfo='skip'
    ))

    # Serie Real (Línea sólida azul con brillo)
    fig.add_trace(go.Scatter(
        x=df_real['fecha'], y=df_real['Valor'],
        name='Real', fill='tozeroy',
        fillcolor='rgba(56, 189, 248, 0.05)',
        line=dict(color='#38bdf8', width=4),
        marker=dict(size=6, color='#f8fafc')
    ))

    fig.update_layout(
        template='plotly_dark',
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='#1e293b', tickformat='%H:%M'),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', title="MW"),
        hovermode="x unified"
    )

    return (
        fig, 
        f"{v_real:,.0f} MW", 
        f"{v_prog:,.0f} MW", 
        f"{desv:+.2f}%", 
        {'margin': '10px 0 0 0', 'fontSize': '32px', 'color': desv_color},
        now_str
    )

if __name__ == '__main__':
    app.run_server(debug=False)
