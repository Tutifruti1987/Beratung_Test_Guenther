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

st.set_page_config(page_title="R+V Beratungs-Plattform", page_icon="🦁", layout="wide")

def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        response = requests.get(url, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None

logo_img = get_logo()

# --- RECHEN-LOGIK ---
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
    if st.button("Simulation zurücksetzen"):
        st.session_state.clear()
        st.rerun()

n_hh, r_luecke, b_luecke, f_anz = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- NAVIGATION ---

# SEITE 1: BERATUNGS-DASHBOARD
if st.session_state.page == "beratung":
    st.title("R+V Vorsorge-Cockpit")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    col4.metric("Förderwege", f"{f_anz}")

    st.write("### 🔍 Deine Sofort-Analyse")
    c_eval1, c_eval2 = st.columns(2)
    with c_eval1:
        if b_luecke > 800:
            st.error(f"🚨 **Kritisch:** Deine BU-Lücke von {b_luecke:.0f}€ gefährdet deinen Lebensstandard sofort bei Krankheit.")
    with c_eval2:
        if r_luecke > 1000:
            st.warning(f"📉 **Handlungsbedarf:** Deine Rentenlücke von {r_luecke:.0f}€ wird im Alter spürbar.")

    st.divider()
    l_col, r_col = st.columns(2)

    with l_col:
        st.subheader("💬 Chat mit Günther")
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        system_p = f"Du bist Günther, R+V Berater. Sachlich, warmherzig. Brutto {brutto}, BU-Lücke {b_luecke}."
        if not st.session_state.messages: st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. Schauen wir uns deine Lücken mal gemeinsam an?"})
        
        container = st.container(height=350)
        with container:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if prompt := st.chat_input("Frage stellen..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            try:
                model = genai.GenerativeModel('gemini-2.0-flash')
                res = model.generate_content([system_p] + [m["content"] for m in st.session_state.messages[-3:]])
                st.session_state.messages.append({"role": "assistant", "content": res.text})
                st.rerun()
            except: st.error("KI-Fehler")

    with r_col:
        st.subheader("🚀 Unsere neue Abschlussstrecke")
        st.markdown("""
        **Safe&Smart: Die Ansparkombi.**
        Kombiniere die Sicherheit der R+V mit den Renditechancen der Märkte. 
        In wenigen Schritten zur individuellen Geldanlage.
        """)
        if st.button("Jetzt Safe&Smart simulieren ➔", type="primary", use_container_width=True):
            st.session_state.page = "produkt_info"
            st.rerun()
        st.image("https://www.ruv.de/static-files/ruvde/images/privatkunden/geldanlage/safe-smart/safe-smart-visual-teaser.jpg")

# SEITE 2: PRODUKT & RECHNER
elif st.session_state.page == "produkt_info":
    st.title("📈 Safe&Smart Investment-Rechner")
    cl, cr = st.columns(2)
    with cl:
        st.subheader("Einstellungen")
        start = st.number_input("Startkapital (€)", 0, 50000, 5000)
        rate = st.slider("Monatliche Rate (€)", 25, 1000, 100)
        jahre = st.slider("Anlagedauer (Jahre)", 1, 67-alter, 67-alter)
        verlauf = berechne_investment_verlauf(start, rate, jahre)
        st.session_state.investment_data = {"rate": rate, "start": start, "jahre": jahre, "summe": verlauf[-1]}
    with cr:
        st.subheader("Kapitalentwicklung")
        st.line_chart(pd.DataFrame(verlauf, columns=["Kapital"]))
        st.metric("Voraussichtliche Kaufkraft", f"{verlauf[-1]:,.0f} €")
    
    if st.button("Weiter zum Angemessenheits-Check »", type="primary"):
        st.session_state.page = "idd_check"
        st.rerun()

# SEITE 3: IDD DETAIL
elif st.session_state.page == "idd_check":
    st.title("🛡️ Angemessenheitsprüfung & IDD")
    with st.form("idd_form_detail"):
        st.subheader("Anlageprofil")
        h_horizont = st.selectbox("Anlagehorizont", ["Kurzfristig (< 5 Jahre)", "Mittelfristig (5-10 Jahre)", "Langfristig (> 10 Jahre)"])
        r_klasse = st.select_slider("Risikoklasse (SRI)", options=[1, 2, 3, 4, 5], value=3, help="1 = Sicher, 5 = Hochriskant")
        
        st.subheader("Nachhaltigkeitspräferenzen (ESG)")
        esg_env = st.checkbox("Ökologische Ziele (Umweltschutz, Klima)")
        esg_soc = st.checkbox("Soziale Ziele (Menschenrechte, Arbeitsschutz)")
        esg_gov = st.checkbox("Gute Unternehmensführung (Anti-Korruption)")
        
        if st.form_submit_button("Profil bestätigen"):
            st.session_state.idd_results = {"rk": r_klasse, "esg": esg_env or esg_soc or esg_gov}
            st.session_state.page = "zusammenfassung"
            st.rerun()

# SEITE 4: FINALE
elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Dein Spar-Erfolg")
    st.balloons()
    data = st.session_state.investment_data
    idd = st.session_state.idd_results
    
    # EMOTIONALE HERVORHEBUNG
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #003366 0%, #0055aa 100%); padding: 40px; border-radius: 20px; text-align: center; color: white; border: 3px solid #ffcc00;">
        <h2 style="color: #ffcc00; margin-bottom: 0;">HERZLICHEN GLÜCKWUNSCH!</h2>
        <p style="font-size: 1.2rem;">Durch deine Entscheidung sparst du ein Vermögen von voraussichtlich</p>
        <h1 style="font-size: 5rem; margin: 10px 0;">{data['summe']:,.0f} €*</h1>
        <p style="font-size: 1rem; opacity: 0.8;">*Kaufkraftbereinigt im Zieljahr. Eine starke Leistung für deine Zukunft!</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    c_res1, c_res2 = st.columns(2)
    with c_res1:
        st.info(f"### 📋 Empfehlung\nBasierend auf Risikoklasse **{idd['rk']}** ist Safe&Smart für dich **angemessen**. Deine Nachhaltigkeitswünsche werden im R+V Portfolio berücksichtigt.")
    with c_res2:
        st.markdown("""
        ### 📄 Deine Dokumente
        - 📄 **Individuelles Beratungsprotokoll**
        - 📄 **Produktinformationsblatt (BIB)**
        - 📄 **Allgemeine Bedingungen (AVB)**
        """)

    if st.button("« Zurück zum Start"):
        st.session_state.page = "beratung"
        st.rerun()
