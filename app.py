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

st.set_page_config(page_title="R+V Vorsorge-Cockpit", page_icon="🦁", layout="wide")

# --- LOGO (gecached) ---
@st.cache_data
def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        response = requests.get(url, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None

logo_img = get_logo()

# --- MATHE ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, 0
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto + (kinder * 250)
    ziel_rente = netto_hh * 0.85 * (1.02 ** (67-alter))
    r_luecke = max(0, ziel_rente - (brutto * 0.48))
    b_luecke = max(0, netto_hh - (brutto * 0.34))
    return netto_hh, r_luecke, b_luecke, 3

def berechne_investment_verlauf(start, rate, jahre):
    real_zins = (1.05 / 1.02) - 1
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
    brutto = st.number_input("Bruttogehalt (mtl.) €", 0, 25000, 2500, step=100)
    st.divider()
    if st.button("Simulation Neustarten"):
        st.session_state.clear()
        st.rerun()

n_hh, r_luecke, b_luecke, f_anz = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- NAVIGATION ---

if st.session_state.page == "beratung":
    st.title("R+V Vorsorge-Cockpit")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    col4.metric("Förderwege", f"{f_anz}")

    st.write("### 🔍 Deine Sofort-Analyse")
    ce1, ce2 = st.columns(2)
    with ce1:
        if b_luecke > 800: st.error(f"🚨 BU-Lücke ({b_luecke:.0f}€) ist kritisch!")
        else: st.success("✅ BU-Schutz stabil.")
    with ce2:
        if r_luecke > 1000: st.warning(f"📉 Rentenlücke ({r_luecke:.0f}€) beachten.")
        else: st.success("✅ Rentenplanung im Plan.")

    st.divider()
    l_col, r_col = st.columns(2)

    with l_col:
        st.subheader("💬 Chat mit Günther")
        if not st.session_state.messages: 
            st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. 👋 Sollen wir über deine Zahlen sprechen?"})
        
        container = st.container(height=350)
        with container:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if prompt := st.chat_input("Deine Frage..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            if "GOOGLE_API_KEY" in st.secrets:
                try:
                    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    sys_p = f"Du bist R+V Berater Günther. Brutto {brutto}€, Netto {n_hh:.0f}€. Antworte kurz und präzise."
                    
                    with st.spinner("Günther überlegt..."):
                        # Automatischer Retry-Mechanismus
                        for i in range(3):
                            try:
                                res = model.generate_content([sys_p, prompt])
                                st.session_state.messages.append({"role": "assistant", "content": res.text})
                                break
                            except Exception as e:
                                if "429" in str(e) and i < 2:
                                    time.sleep(4)
                                    continue
                                else: raise e
                    st.rerun()
                except Exception as e:
                    st.error("Google ist gerade überlastet. Bitte warte 10 Sekunden, bevor du die nächste Frage stellst.")
            else:
                st.error("API Key fehlt!")

    with r_col:
        st.subheader("🚀 Unsere neue Abschlussstrecke")
        st.markdown("**Safe&Smart: Die Ansparkombi.**\nKombiniere Sicherheit mit Renditechancen.")
        if st.button("Jetzt Safe&Smart simulieren ➔", type="primary", use_container_width=True):
            st.session_state.page = "produkt_info"
            st.rerun()
        st.image("https://www.ruv.de/static-files/ruvde/images/privatkunden/geldanlage/safe-smart/safe-smart-visual-teaser.jpg")

# --- DIE ANDEREN SEITEN (PRODUKT, IDD, FINALE) ---
elif st.session_state.page == "produkt_info":
    st.title("📈 Safe&Smart Investment-Rechner")
    cl, cr = st.columns(2)
    with cl:
        start = st.number_input("Startkapital (€)", 0, 50000, 5000)
        rate = st.slider("Monatliche Rate (€)", 25, 1000, 100)
        jahre = st.slider("Anlagedauer (Jahre)", 1, 67-alter, 67-alter)
        verlauf = berechne_investment_verlauf(start, rate, jahre)
        st.session_state.inv_data = {"rate": rate, "summe": verlauf[-1], "jahre": jahre, "start": start}
        st.metric("Voraussichtliches Kapital", f"{verlauf[-1]:,.0f} €")
    with cr:
        st.subheader("Wachstumsverlauf")
        st.line_chart(pd.DataFrame(verlauf, columns=["Kapital"]))

    if st.button("Weiter zum Abschluss »", type="primary", use_container_width=True):
        st.session_state.page = "idd_check"
        st.rerun()

elif st.session_state.page == "idd_check":
    st.title("🛡️ Angemessenheitsprüfung")
    with st.form("idd"):
        st.radio("Anlageerfahrung", ["Einsteiger", "Fortgeschritten", "Profi"])
        st.select_slider("Risikoprofil", options=[1, 2, 3, 4, 5], value=3)
        st.checkbox("ESG berücksichtigen")
        if st.form_submit_button("Bestätigen"):
            st.session_state.page = "zusammenfassung"
            st.rerun()

elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Dein Simulations-Erfolg")
    st.balloons()
    data = st.session_state.inv_data
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #003366 0%, #0055aa 100%); padding: 40px; border-radius: 20px; text-align: center; color: white; border: 3px solid #ffcc00; margin-bottom: 25px;">
        <h2 style="color: #ffcc00; margin-bottom: 0;">HERZLICHEN GLÜCKWUNSCH!</h2>
        <h1 style="font-size: 5rem; margin: 10px 0;">{data['summe']:,.0f} €*</h1>
        <p>Kaufkraftbereinigt in {data['jahre']} Jahren.</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 JETZT SIMULIERT ABSCHLIESSEN", type="primary", use_container_width=True):
        st.success("🎉 Antrag erfolgreich simuliert!")
    if st.button("Zurück zum Start", use_container_width=True):
        st.session_state.page = "beratung"
        st.rerun()
