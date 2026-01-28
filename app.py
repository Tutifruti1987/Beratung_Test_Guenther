import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time

# --- INITIALISIERUNG NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = "beratung"

# --- SETUP & LOGO ---
st.set_page_config(page_title="R+V Simulations-Plattform", page_icon="🦁", layout="wide")

def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None 

logo_img = get_logo()

# --- MATHEMATIK-FUNKTIONEN ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, 0
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto_basis = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto_basis + (kinder * 250)
    jahre_bis_rente = 67 - alter
    ziel_rente = netto_hh * 0.85 * (1.02 ** jahre_bis_rente)
    r_luecke = max(0, ziel_rente - (brutto * 0.48))
    b_luecke = max(0, netto_hh - (brutto * 0.34))
    return netto_hh, r_luecke, b_luecke, 3

def berechne_investment(start, rate, jahre, rendite=0.05, inflation=0.02):
    # Realverzinsung berechnen
    real_zins = (1 + rendite) / (1 + inflation) - 1
    monats_zins = (1 + real_zins)**(1/12) - 1
    monate = jahre * 12
    # Endwertformel Sparplan
    endwert = start * (1 + real_zins)**jahre + rate * ((1 + monats_zins)**monate - 1) / monats_zins
    return endwert

# --- NAVIGATION: SEITE 1 (BERATUNG) ---
if st.session_state.page == "beratung":
    with st.sidebar:
        if logo_img: st.image(logo_img, width=80)
        st.header("📋 Basis-Daten")
        status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
        st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
        kinder = st.number_input("Kinder", 0, 10, 0)
        alter = st.number_input("Alter", 18, 67, 35)
        brutto = st.number_input("Brutto (mtl.) €", 0, 25000, 0)
        if st.button("Reset Chat"):
            st.session_state.messages = []
            st.rerun()

    n_hh, r_luecke, b_luecke, f_anzahl = berechne_analyse(brutto, st_klasse, kinder, alter)

    c1, c2 = st.columns([1, 4])
    with c1: 
        if logo_img: st.image(logo_img, width=120)
    with c2: 
        st.title("Vorsorge-Check & Investment")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    col4.metric("Förderwege", f"{f_anzahl}")

    st.divider()

    # Chat-System
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    
    system_prompt = f"Du bist Günther, ein R+V Berater. Sei warmherzig, professionell und direkt. Brutto: {brutto}€, Netto: {n_hh}€, BU-Lücke: {b_luecke}€. Priorisiere BU vor Rente."
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. 👋 Sollen wir mal schauen, wie wir deine Lücken schließen?"})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Frag Günther..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([system_prompt] + [m["content"] for m in st.session_state.messages[-5:]])
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except: st.error("KI kurz überlastet...")

    # DER NEUE PROMINENTE BUTTON
    st.markdown("---")
    st.info("### 💡 Clevere Geldanlage mit Safe&Smart")
    st.write("Kombiniere Sicherheit mit Renditechancen. Flexibel ansparen ab 25 €.")
    if st.button("Jetzt informieren und direkt abschließen ➔", type="primary", use_container_width=True):
        st.session_state.page = "produkt_info"
        st.rerun()

# --- NAVIGATION: SEITE 2 (PRODUKT-SIMULATION) ---
elif st.session_state.page == "produkt_info":
    st.title("📈 R+V Safe&Smart Simulation")
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.markdown("""
        **Das Beste aus zwei Welten:** Ansparen mit der R+V Ansparkombi bedeutet Flexibilität. Ein Teil fließt in das Sicherungsvermögen, 
        der andere in renditestarke Investmentfonds.
        """)
        st.subheader("Simulations-Rechner (Inflationsbereinigt)")
        s_kapital = st.select_slider("Startkapital (€)", options=[0, 1000, 5000, 10000, 25000, 50000], value=5000)
        s_rate = st.slider("Monatliche Sparrate (€)", 25, 1000, 100)
        s_jahre = st.slider("Anlagedauer (Jahre)", 5, 40, 25)
        
        ergebnis = berechne_investment(s_kapital, s_rate, s_jahre)
        st.metric("Voraussichtliche Kaufkraft im Zieljahr", f"{ergebnis:,.0f} €", help="Berechnet mit 5% Rendite und 2% Inflation")
        
        # Speichern der Werte für die Zusammenfassung
        st.session_state.investment_data = {"start": s_kapital, "rate": s_rate, "jahre": s_jahre, "summe": ergebnis}

    with col_r:
        st.info("**Vorteile:**\n- Täglich verfügbar\n- Ab 25 € mtl.\n- Keine Abschlusskosten bei Zuzahlungen\n- R+V Garantie-Komponente")
        if logo_img: st.image(logo_img)

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("« Zurück zur Beratung"):
        st.session_state.page = "beratung"
        st.rerun()
    if c2.button("Weiter zum Angemessenheits-Check »"):
        st.session_state.page = "idd_check"
        st.rerun()

# --- NAVIGATION: SEITE 3 (IDD CHECK) ---
elif st.session_state.page == "idd_check":
    st.title("🛡️ Angemessenheitsprüfung (Simulation)")
    st.write("Für einen Abschluss müssen wir gesetzliche Anforderungen (IDD) prüfen.")
    
    with st.form("idd_form"):
        st.radio("Welche Erfahrung hast du mit Wertpapieren?", ["Keine", "Basiswissen", "Experte"])
        st.select_slider("Wie stehst du zu Kursschwankungen?", options=["Sicherheit zuerst", "Ausgewogen", "Renditeorientiert"])
        st.checkbox("Ich wünsche die Berücksichtigung von Nachhaltigkeitsaspekten (ESG).")
        st.caption("Dies ist eine Simulation. Es werden keine Daten gespeichert.")
        
        submitted = st.form_submit_state = st.form_submit_button("Eingaben bestätigen & Weiter")
        if submitted:
            st.session_state.page = "zusammenfassung"
            st.rerun()
    
    if st.button("« Zurück"):
        st.session_state.page = "produkt_info"
        st.rerun()

# --- NAVIGATION: SEITE 4 (ZUSAMMENFASSUNG) ---
elif st.session_state.page == "zusammenfassung":
    st.title("🏁 Zusammenfassung Ihres Sparwunsches")
    data = st.session_state.investment_data
    
    st.balloons()
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        ### Gewählte Konfiguration
        - **Produkt:** R+V Safe&Smart
        - **Startkapital:** {data['start']} €
        - **Monatliche Rate:** {data['rate']} €
        - **Laufzeit:** {data['jahre']} Jahre
        """)
    
    with col_b:
        st.markdown(f"""
        ### Ergebnis-Vorschau
        - **Kaufkraft-Endwert:** ~ {data['summe']:,.0f} €
        - **Status:** Simulation erfolgreich
        """)

    st.success("Dies war eine Simulation des Abschlussprozesses. Im echten Betrieb würde hier nun die finale Antragsübermittlung erfolgen.")
    
    if st.button("« Zurück zum Start (Beratung)"):
        st.session_state.page = "beratung"
        st.rerun()
