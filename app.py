import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd
import numpy as np

# --- INITIALISIERUNG ---
if 'page' not in st.session_state:
    st.session_state.page = "beratung"
if 'alter' not in st.session_state:
    st.session_state.alter = 35

st.set_page_config(page_title="R+V Safe&Smart", page_icon="🦁", layout="wide")

# --- LOGO FUNKTION ---
def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        response = requests.get(url, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None

logo_img = get_logo()

# --- RECHEN-LOGIK ---
def berechne_verlauf(start, rate, jahre, rendite=0.05, inflation=0.02):
    real_zins = (1 + rendite) / (1 + inflation) - 1
    monats_zins = (1 + real_zins)**(1/12) - 1
    werte = []
    kontostand = start
    for monat in range(jahre * 12 + 1):
        werte.append(kontostand)
        kontostand = (kontostand + rate) * (1 + monats_zins)
    return werte

# --- SEITE 1: BERATUNG ---
if st.session_state.page == "beratung":
    with st.sidebar:
        if logo_img: st.image(logo_img, width=80)
        st.session_state.alter = st.number_input("Dein Alter", 18, 67, st.session_state.alter)
        brutto = st.number_input("Brutto mtl. €", 0, 20000, 4000)
    
    st.title("R+V Vorsorge-Check")
    st.info("### 📈 Clevere Geldanlage mit Safe&Smart")
    if st.button("Jetzt informieren und direkt abschließen ➔", type="primary"):
        st.session_state.page = "produkt_info"
        st.rerun()
    # (Hier würde dein Günther Chat weiterlaufen...)

# --- SEITE 2: PRODUKT-INFO & RECHNER ---
elif st.session_state.page == "produkt_info":
    st.title("Ansparkombi Safe&Smart")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Deine Planung")
        start = st.number_input("Startkapital (€)", 0, 100000, 5000)
        rate = st.slider("Monatliche Sparrate (€)", 25, 1000, 100)
        
        # Alter & Laufzeit Logik
        alter_heute = st.session_state.alter
        max_jahre = 67 - alter_heute
        
        wahl = st.radio("Anlagedauer wählen:", [f"Bis zur Rente (Alter 67, also {max_jahre} Jahre)", "Individuelle Dauer"])
        
        if wahl == "Individuelle Dauer":
            jahre = st.slider("Jahre", 1, max_jahre, min(10, max_jahre))
        else:
            jahre = max_jahre

        verlauf = berechne_verlauf(start, rate, jahre)
        endwert = verlauf[-1]
        
        st.metric("Dein voraussichtliches Kapital (heutige Kaufkraft)", f"{endwert:,.0f} €")

    with col2:
        st.subheader("Wertentwicklung")
        chart_data = pd.DataFrame({"Kapital (€)": verlauf})
        st.line_chart(chart_data)
        st.caption("Simulation mit 5% Rendite p.a. und 2% Inflation.")

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("« Zurück"): st.session_state.page = "beratung"; st.rerun()
    if c2.button("Weiter zum Check »"): 
        st.session_state.investment_data = {"start": start, "rate": rate, "jahre": jahre, "summe": endwert}
        st.session_state.page = "idd_check"
        st.rerun()

# --- SEITE 3: IDD ---
elif st.session_state.page == "idd_check":
    st.title("Angemessenheitsprüfung")
    with st.form("idd"):
        st.radio("Erfahrung mit Fonds?", ["Keine", "Basis", "Profi"])
        st.checkbox("Ich bestätige die Simulation der Nachhaltigkeitsaspekte (ESG)")
        if st.form_submit_button("Bestätigen & Weiter"):
            st.session_state.page = "zusammenfassung"
            st.rerun()

# --- SEITE 4: ZUSAMMENFASSUNG & DOKUMENTE ---
elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Dein Abschluss-Check")
    st.balloons()
    
    data = st.session_state.investment_data
    st.write(f"Du sparst **{data['rate']} €** monatlich über **{data['jahre']} Jahre**.")
    
    st.markdown("""
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px solid #003366;">
        <h4 style="color: #003366; margin-top: 0;">📄 Deine Vertragsunterlagen (Simulation)</h4>
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="background: white; padding: 10px; border-radius: 5px; border: 1px solid #ccc; cursor: pointer;">
                📄 <b>Beratungsprotokoll</b><br><small>PDF-Vorschau</small>
            </div>
            <div style="background: white; padding: 10px; border-radius: 5px; border: 1px solid #ccc; cursor: pointer;">
                📜 <b>Produktbedingungen</b><br><small>Allgemeine Infos</small>
            </div>
            <div style="background: white; padding: 10px; border-radius: 5px; border: 1px solid #ccc; cursor: pointer;">
                📑 <b>Vorvertragliche Infos</b><br><small>Basisdatenblatt</small>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if st.button("« Zurück zum Start"):
        st.session_state.page = "beratung"
        st.rerun()
