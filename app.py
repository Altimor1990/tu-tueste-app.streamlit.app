import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Alpha Tueste App", layout="wide")
st.title("☕ Dashboard de Tueste: Alpha V2")

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('coffee_roasting_alpha_v2.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tuestes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_lote TEXT, variedad_grano TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS puntos_curva (id INTEGER PRIMARY KEY AUTOINCREMENT, tueste_id INTEGER, tiempo_seg REAL, piro_1_grano REAL, piro_2_ambiente REAL, piro_3_escape REAL, oxigeno_1_in REAL, oxigeno_2_out REAL, ror_grano REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS catas (id INTEGER PRIMARY KEY AUTOINCREMENT, tueste_id INTEGER, puntaje_total REAL, acidez REAL, cuerpo REAL, dulzor REAL, notas_catas TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- MENÚ LATERAL ---
st.sidebar.header("Opciones del Alpha")
menu = st.sidebar.radio("Navegación", ["1. Dashboard Histórico", "2. Cargar Archivo CSV", "3. Simulación de Tueste", "4. Monitor en Tiempo Real"])

# --- 1. DASHBOARD HISTÓRICO ---
if menu == "1. Dashboard Histórico":
    st.header("Análisis de Lotes Anteriores")
    conn = sqlite3.connect('coffee_roasting_alpha_v2.db')
    tuestes_df = pd.read_sql_query("SELECT * FROM tuestes", conn)
    
    if tuestes_df.empty:
        st.info("No hay datos todavía. Ve a 'Simulación' o 'Cargar Archivo' en el menú lateral.")
    else:
        lote_seleccionado = st.selectbox("Selecciona un Lote a analizar:", tuestes_df['nombre_lote'])
        t_id = tuestes_df[tuestes_df['nombre_lote'] == lote_seleccionado]['id'].values[0]
        
        puntos_df = pd.read_sql_query(f"SELECT * FROM puntos_curva WHERE tueste_id = {t_id}", conn)
        catas_df = pd.read_sql_query(f"SELECT * FROM catas WHERE tueste_id = {t_id}", conn)
        
        minutos = puntos_df['tiempo_seg'] / 60
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=('Temperaturas (3 Pirómetros) y RoR', 'Dinámica de Oxígeno', 'Perfil de Cata'), row_heights=[0.5, 0.25, 0.25], specs=[[{"secondary_y": True}], [{}], [{}]])
        
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['piro_1_grano'], name="Grano (BT)", line=dict(color='#8B4513', width=3)), row=1, col=1)
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['piro_2_ambiente'], name="Ambiente (ET)", line=dict(color='#FFA500', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['piro_3_escape'], name="Escape", line=dict(color='#A9A9A9')), row=1, col=1)
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['ror_grano'], name="RoR", line=dict(color='#DC143C')), row=1, col=1, secondary_y=True)
        
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['oxigeno_1_in'], name="O2 In", line=dict(color='#00BFFF')), row=2, col=1)
        fig.add_trace(go.Scatter(x=minutos, y=puntos_df['oxigeno_2_out'], name="O2 Out", line=dict(color='#4682B4', dash='dash')), row=2, col=1)
        
        if not catas_df.empty:
            c = catas_df.iloc[0]
            fig.add_trace(go.Bar(x=['Acidez', 'Cuerpo', 'Dulzor', 'Puntaje/10'], y=[c['acidez'], c['cuerpo'], c['dulzor'], c['puntaje_total']/10], name="Cata"), row=3, col=1)
            
        fig.update_layout(height=800, template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    conn.close()

# --- 2. CARGAR CSV ---
elif menu == "2. Cargar Archivo CSV":
    st.header("Cargar Exportación de Artisan/Cropster")
    uploaded_file = st.file_uploader("Sube tu archivo CSV (Debe contener Time, BT, ET, Exhaust, O2_in, O2_out)", type="csv")
    
    if uploaded_file is not None:
        nombre_lote = st.text_input("Nombre del lote:")
        if st.button("Guardar en Base de Datos") and nombre_lote:
            df = pd.read_csv(uploaded_file)
            df['RoR'] = np.gradient(df['BT'], df['Time']) * 60
            
            conn = sqlite3.connect('coffee_roasting_alpha_v2.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tuestes (nombre_lote, variedad_grano) VALUES (?, ?)", (nombre_lote, "Subido por CSV"))
            id_tueste = cursor.lastrowid
            
            for _, row in df.iterrows():
                cursor.execute('''INSERT INTO puntos_curva (tueste_id, tiempo_seg, piro_1_grano, piro_2_ambiente, piro_3_escape, oxigeno_1_in, oxigeno_2_out, ror_grano) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (id_tueste, float(row['Time']), float(row['BT']), float(row['ET']), float(row['Exhaust']), float(row['O2_in']), float(row['O2_out']), float(row['RoR'])))
            
            cursor.execute("INSERT INTO catas (tueste_id, puntaje_total, acidez, cuerpo, dulzor, notas_catas) VALUES (?, 0, 0, 0, 0, '')", (id_tueste,))
            conn.commit()
            conn.close()
            st.success(f"Lote '{nombre_lote}' guardado exitosamente. Ve al Dashboard para verlo.")

# --- 3. SIMULACIÓN ---
elif menu == "3. Simulación de Tueste":
    st.header("Generar Datos de Prueba (Simulador)")
    nombre_sim = st.text_input("Nombre de la simulación:")
    tipo = st.selectbox("Tipo de Tueste", ["normal", "rapido", "horneado"])
    
    if st.button("Generar Lote Simulado") and nombre_sim:
        conn = sqlite3.connect('coffee_roasting_alpha_v2.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tuestes (nombre_lote, variedad_grano) VALUES (?, ?)", (nombre_sim, "Virtual"))
        id_tueste = cursor.lastrowid
        
        tiempos = np.arange(0, 600, 5)
        mod_temp = 1.2 if tipo == "rapido" else 0.7 if tipo == "horneado" else 1.0
        
        piro_1 = 150 + (75 * mod_temp) * (1 - np.exp(-tiempos / 200)) 
        piro_2 = 250 - (20 / mod_temp) * np.exp(-tiempos / 100) 
        piro_3 = 200 + 10 * np.sin(tiempos / 50) - (20 * mod_temp) * np.exp(-tiempos / 150)
        oxigeno_1 = np.full_like(tiempos, 20.9)
        oxigeno_2 = 20.9 - (4.5 * mod_temp) * (1 - np.exp(-tiempos / 250))
        ror = np.gradient(piro_1, tiempos) * 60 
        
        for t, p1, p2, p3, o1, o2, r in zip(tiempos, piro_1, piro_2, piro_3, oxigeno_1, oxigeno_2, ror):
            cursor.execute('''INSERT INTO puntos_curva (tueste_id, tiempo_seg, piro_1_grano, piro_2_ambiente, piro_3_escape, oxigeno_1_in, oxigeno_2_out, ror_grano) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (id_tueste, float(t), float(p1), float(p2), float(p3), float(o1), float(o2), float(r)))
        
        cursor.execute("INSERT INTO catas (tueste_id, puntaje_total, acidez, cuerpo, dulzor, notas_catas) VALUES (?, 85, 8, 8, 8, 'Simulado')", (id_tueste,))
        conn.commit()
        conn.close()
        st.success(f"Simulación '{nombre_sim}' creada. Ve al Dashboard para verla.")

# --- 4. TIEMPO REAL (Simulado) ---
elif menu == "4. Monitor en Tiempo Real":
    st.header("Monitor de Hardware (En Vivo)")
    if st.button("Iniciar Tueste de Prueba"):
        espacio_grafico = st.empty() # Espacio dinámico para actualizar el gráfico
        tiempos, piro1, piro2, o2 = [], [], [], []
        t_grano, t_amb, ox = 150.0, 250.0, 20.9
        
        # Bucle de actualización web
        for t in range(0, 60, 2):
            tiempos.append(t)
            t_grano += np.random.uniform(0.5, 2.0)
            t_amb -= np.random.uniform(0.1, 0.5)
            ox -= np.random.uniform(0.05, 0.2)
            
            piro1.append(t_grano)
            piro2.append(t_amb)
            o2.append(ox)
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Scatter(x=tiempos, y=piro1, name='Grano (BT)', line=dict(color='#8B4513', width=3)), row=1, col=1)
            fig.add_trace(go.Scatter(x=tiempos, y=piro2, name='Ambiente (ET)', line=dict(color='#FFA500', dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=tiempos, y=o2, name='O2 Out (%)', line=dict(color='#4682B4')), row=2, col=1)
            fig.update_layout(title=f"🔴 TUESTE EN VIVO - Segundos: {t}", height=600, template="plotly_dark")
            fig.update_yaxes(range=[100, 300], row=1, col=1)
            
            # Actualiza el gráfico en la web
            espacio_grafico.plotly_chart(fig, use_container_width=True)
            time.sleep(0.5) # Velocidad acelerada para demostración
        st.success("Tueste finalizado.")