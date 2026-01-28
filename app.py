import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd

# --- INITIALISIERUNG ---
if 'page' not in st.session_state:
    st.session_state.page = "beratung"
if 'messages' not in st.session_state:
    st.session_state.messages = []

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
    # Rentenlücke: Ziel 85% vom Netto, 2% Inflation bis 67
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

# --- SIDEBAR ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=80)
    st.header("📋 Kundendaten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    # VORBEFÜLLT MIT 2500€
    brutto = st.number_input("Bruttogehalt (mtl.) €", 0, 25000, 2500, step=100)
    st.divider()
    if st.button("Gespräch zurücksetzen"):
        st.session_state.messages = []
        st.session_state.page = "beratung"
        st.rerun()

# --- BERECHNUNGEN ---
n_hh, r_luecke, b_luecke, f_anz = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- NAVIGATIONSLOGIK ---

if st.session_state.page == "beratung":
    # Header
    c_logo, c_title = st.columns([1, 5])
    with c_logo: 
        if logo_img: st.image(logo_img, width=100)
    with c_title:
        st.title("R+V Vorsorge-Cockpit")

    # Kacheln
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    col4.metric("Förderwege", f"{f_anz}")

    # BEWERTUNG (Wieder eingefügt)
    st.write("### 🔍 Erste Einschätzung")
    if brutto > 0:
        if b_luecke > 1000:
            st.error(f"⚠️ Deine BU-Lücke ist mit {b_luecke:.0f}€ sehr kritisch. Dein Existenzschutz sollte Priorität haben.")
        else:
            st.success("✅ Deine BU-Lücke ist moderat, aber eine Absicherung bleibt wichtig.")
        
        if r_luecke > 1500:
            st.warning(f"📈 Deine Rentenlücke von {r_luecke:.0f}€ erfordert frühzeitiges Handeln.")
    else:
        st.info("Bitte gib links dein Einkommen ein für eine Bewertung.")

    st.divider()

    # HAUPT-LAYOUT: TEILUNG IN DER MITTE
    layout_links, layout_rechts = st.columns(2)

    with layout_links:
        st.subheader("💬 Beratung mit Günther")
        # Chat System
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        system_prompt = f"Du bist Günther, ein R+V Experte. Berate warmherzig und professionell. Daten: Brutto {brutto}€, Rentenlücke {r_luecke:.0f}€, BU-Lücke {b_luecke:.0f}€."
        
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. 👋 Ich habe deine Daten analysiert. Sollen wir über die Details sprechen?"})

        # Chat-Container mit fester Höhe für bessere Optik
        chat_container = st.container(height=400)
        with chat_container:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])

        if prompt := st.chat_input("Frage an Günther..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            try:
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content([system_prompt] + [m["content"] for m in st.session_state.messages[-5:]])
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except: st.error("KI-Service kurzzeitig nicht erreichbar.")

    with layout_rechts:
        st.subheader("🚀 Unsere neue Abschlussstrecke")
        st.markdown("""
        **Geldanlage neu gedacht.** Mit unserem Produkt **Safe&Smart** kombinierst du Sicherheit und Rendite. 
        Hier kannst du dein individuelles Ansparszenario simulieren und den Prozess bis zum Abschluss durchspielen.
        
        - ✅ Inflationsbereinigte Prognose
        - ✅ Flexibler Sparplan
        - ✅ IDD-konforme Simulation
        """)
        st.write("")
        if st.button("Jetzt informieren und direkt abschließen ➔", type="primary", use_container_width=True):
            st.session_state.page = "produkt_info"
            st.rerun()
        
        # Ein kleines Vorschaubild oder Icon
        st.image("https://www.ruv.de/static-files/ruvde/images/privatkunden/geldanlage/safe-smart/safe-smart-visual-teaser.jpg", use_container_width=True)

# --- SEITE 2: PRODUKT-INFO ---
elif st.session_state.page == "produkt_info":
    st.title("📈 R+V Safe&Smart Simulation")
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("Anlage-Parameter")
        start = st.number_input("Startkapital (€)", 0, 50000, 5000)
        rate = st.slider("Monatliche Sparrate (€)", 25, 1000, 100)
        max_jahre = 67 - alter
        jahre = st.slider("Laufzeit (Jahre)", 1, max_jahre, max_jahre)
        
        verlauf = berechne_investment_verlauf(start, rate, jahre)
        st.metric("Dein Ziel-Kapital (Kaufkraft)", f"{verlauf[-1]:,.0f} €")
        st.session_state.final_data = {"rate": rate, "start": start, "jahre": jahre, "summe": verlauf[-1]}

    with col_r:
        st.subheader("Wachstumsprognose")
        st.line_chart(pd.DataFrame(verlauf, columns=["Kapitalentwicklung"]))

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("« Zurück"): st.session_state.page = "beratung"; st.rerun()
    if c2.button("Weiter zum Abschluss »"): st.session_state.page = "idd_check"; st.rerun()

# --- SEITE 3: IDD ---
elif st.session_state.page == "idd_check":
    st.title("🛡️ Gesetzliche Prüfung")
    with st.form("idd"):
        st.radio("Fonds-Erfahrung?", ["Keine", "Basis", "Erfahren"])
        st.checkbox("Nachhaltigkeit (ESG) berücksichtigen")
        if st.form_submit_button("Bestätigen"):
            st.session_state.page = "zusammenfassung"
            st.rerun()
    if st.button("Abbrechen"): st.session_state.page = "produkt_info"; st.rerun()

# --- SEITE 4: ZUSAMMENFASSUNG ---
elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Abschluss-Zusammenfassung")
    st.balloons()
    fd = st.session_state.final_data
    st.success(f"Sparplan über {fd['rate']}€ erfolgreich simuliert!")
    
    st.markdown("""
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #003366;">
        <h4 style="color: #003366;">📄 Deine Dokumente</h4>
        <p>📁 Beratungsprotokoll | 📁 Bedingungen | 📁 Vorvertragliche Infos</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Zurück zum Start"): st.session_state.page = "beratung"; st.rerun()
