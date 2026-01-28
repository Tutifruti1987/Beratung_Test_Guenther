import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd

# --- INITIALISIERUNG NAVIGATION & DATEN ---
if 'page' not in st.session_state:
    st.session_state.page = "beratung"
if 'messages' not in st.session_state:
    st.session_state.messages = []

# --- SETUP ---
st.set_page_config(page_title="R+V Berater-Plattform", page_icon="🦁", layout="wide")

def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        response = requests.get(url, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None

logo_img = get_logo()

# --- MATHE-LOGIK ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, 0
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto + (kinder * 250)
    ziel_rente = netto_hh * 0.85 * (1.02 ** (67-alter))
    r_luecke = max(0, ziel_rente - (brutto * 0.48))
    b_luecke = max(0, netto_hh - (brutto * 0.34))
    return netto_hh, r_luecke, b_luecke, 3

def berechne_investment_verlauf(start, rate, jahre, rendite=0.05, inflation=0.02):
    real_zins = (1 + rendite) / (1 + inflation) - 1
    monats_zins = (1 + real_zins)**(1/12) - 1
    werte = []
    stand = start
    for m in range(jahre * 12 + 1):
        werte.append(stand)
        stand = (stand + rate) * (1 + monats_zins)
    return werte

# --- SIDEBAR (Immer sichtbar für Basisdaten) ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=80)
    st.header("📋 Kundendaten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Bruttogehalt (mtl.) €", 0, 25000, 0, step=100)
    st.divider()
    if st.button("Gespräch zurücksetzen"):
        st.session_state.messages = []
        st.session_state.page = "beratung"
        st.rerun()

# --- BERECHNUNGEN ---
n_hh, r_luecke, b_luecke, f_anz = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- NAVIGATIONSLOGIK ---

# SEITE 1: BERATUNG
if st.session_state.page == "beratung":
    c1, c2 = st.columns([1, 4])
    with c1: 
        if logo_img: st.image(logo_img, width=120)
    with c2: 
        st.title("Persönliche Vorsorgeanalyse")
        st.subheader("Berater: Günther")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    col4.metric("Förderwege", f"{f_anz}")

    st.divider()

    # Chat
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    
    system_prompt = f"Du bist Günther, ein R+V Berater. Professionell, direkt, warmherzig. Brutto: {brutto}€, Netto: {n_hh}€, Lücken: Rente {r_luecke}€, BU {b_luecke}€."
    
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "assistant", "content": "Guten Tag! Ich bin Günther. Sollen wir direkt in deine Analyse einsteigen?"})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Frage an Günther..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content([system_prompt] + [m["content"] for m in st.session_state.messages[-5:]])
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except: st.error("Fehler bei der KI-Anfrage.")

    st.info("### 📈 Clevere Geldanlage mit Safe&Smart")
    if st.button("Jetzt informieren und direkt abschließen ➔", type="primary", use_container_width=True):
        st.session_state.page = "produkt_info"
        st.rerun()

# SEITE 2: SAFE & SMART RECHNER
elif st.session_state.page == "produkt_info":
    st.title("R+V Safe&Smart - Deine Investment-Simulation")
    
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("Anlage-Parameter")
        start = st.number_input("Startkapital (€)", 0, 50000, 5000)
        rate = st.slider("Monatliche Sparrate (€)", 25, 1000, 100)
        
        # Laufzeit-Logik
        max_jahre = 67 - alter
        dauer_wahl = st.radio("Laufzeit:", [f"Bis zur Rente (Alter 67, also {max_jahre} Jahre)", "Individuell"])
        jahre = max_jahre if "Rente" in dauer_wahl else st.slider("Jahre", 1, max_jahre, 15)
        
        verlauf = berechne_investment_verlauf(start, rate, jahre)
        st.metric("Dein Ziel-Kapital (Kaufkraft)", f"{verlauf[-1]:,.0f} €")

    with col_r:
        st.subheader("Voraussichtliches Wachstum")
        st.line_chart(pd.DataFrame(verlauf, columns=["Kapitalentwicklung"]))
        st.caption("Basis: 5% p.a. Renditechance, 2% p.a. Inflation.")

    c1, c2 = st.columns(2)
    if c1.button("« Zurück zur Beratung"): st.session_state.page = "beratung"; st.rerun()
    if c2.button("Weiter zum Abschluss »"): 
        st.session_state.final_data = {"rate": rate, "start": start, "jahre": jahre, "summe": verlauf[-1]}
        st.session_state.page = "idd_check"
        st.rerun()

# SEITE 3: IDD
elif st.session_state.page == "idd_check":
    st.title("Gesetzliche Prüfung (IDD)")
    st.write("Diese Angaben sind für eine rechtssichere Simulation notwendig.")
    with st.form("idd"):
        st.radio("Erfahrung mit Fonds?", ["Keine", "Basis", "Erfahren"])
        st.checkbox("Ich wünsche ESG-Nachhaltigkeitskriterien.")
        if st.form_submit_button("Prüfung abschließen"):
            st.session_state.page = "zusammenfassung"
            st.rerun()
    if st.button("« Abbrechen"): st.session_state.page = "produkt_info"; st.rerun()

# SEITE 4: ZUSAMMENFASSUNG & DOKUMENTE
elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Ihr Simulations-Ergebnis")
    st.balloons()
    fd = st.session_state.final_data
    
    st.write(f"Sie haben sich für einen Sparplan über **{fd['rate']} €** mtl. entschieden.")
    
    # DOKUMENTEN BOX
    st.markdown(f"""
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #003366;">
        <h4 style="color: #003366;">📄 Bereitgestellte Dokumente</h4>
        <div style="display: flex; gap: 15px; flex-wrap: wrap;">
            <div style="border: 1px solid #ddd; padding: 10px; background: white;">📁 Beratungsprotokoll</div>
            <div style="border: 1px solid #ddd; padding: 10px; background: white;">📁 Produktbedingungen</div>
            <div style="border: 1px solid #ddd; padding: 10px; background: white;">📁 Vorvertragliche Informationen</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("« Zurück zum Start"): st.session_state.page = "beratung"; st.rerun()
