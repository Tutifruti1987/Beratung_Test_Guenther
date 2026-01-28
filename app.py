import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd

# --- 1. SETUP & STATE ---
if 'page' not in st.session_state:
    st.session_state.page = "beratung"
if 'messages' not in st.session_state:
    st.session_state.messages = []

st.set_page_config(page_title="R+V Vorsorge-Cockpit", page_icon="🦁", layout="wide")

# --- 2. FUNKTIONEN (Logo & Mathe) ---
@st.cache_data
def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        response = requests.get(url, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None

logo_img = get_logo()

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
    # Einfache Zinseszins-Rechnung für die Grafik
    real_zins = (1.05 / 1.02) - 1 # 5% Rendite bereinigt um 2% Inflation
    monats_zins = (1 + real_zins)**(1/12) - 1
    werte = []
    stand = start
    for m in range(jahre * 12 + 1):
        werte.append(stand)
        stand = (stand + rate) * (1 + monats_zins)
    return werte

# --- 3. SIDEBAR (EINGABEN) ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=80)
    st.header("📋 Deine Daten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Bruttogehalt (mtl.) €", 0, 25000, 2500, step=100)
    st.divider()
    if st.button("Reset & Neustart"):
        st.session_state.clear()
        st.rerun()

# Werte berechnen
n_hh, r_luecke, b_luecke, f_anz = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- 4. HAUPTSEITE: BERATUNG (SPLIT SCREEN) ---
if st.session_state.page == "beratung":
    st.title("R+V Vorsorge-Cockpit")
    
    # Kacheln
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
    c2.metric("Rentenlücke", f"{r_luecke:.0f} €")
    c3.metric("BU-Lücke", f"{b_luecke:.0f} €")
    c4.metric("Förderwege", f"{f_anz}")

    # Ampel-Bewertung
    ce1, ce2 = st.columns(2)
    with ce1:
        if b_luecke > 800: st.error(f"🚨 Achtung: Hohe BU-Lücke ({b_luecke:.0f} €). Existenzbedrohend!")
        else: st.success("✅ BU-Schutz ist solide.")
    with ce2:
        if r_luecke > 1000: st.warning(f"📉 Rentenlücke ({r_luecke:.0f} €) ist spürbar.")
        else: st.success("✅ Rentenvorsorge passt.")
        
    st.divider()

    # LAYOUT: LINKS CHAT | RECHTS PRODUKT
    col_chat, col_prod = st.columns(2)

    # --- LINKER BEREICH: GÜNTHER ---
    with col_chat:
        st.subheader("💬 Chat mit Günther")
        
        # Chat History anzeigen
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. 👋 Ich sehe deine Zahlen. Sollen wir mal drüber schauen?"})
        
        chat_container = st.container(height=400)
        with chat_container:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])

        # Chat Eingabe & Logik
        if prompt := st.chat_input("Schreib Günther..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)

            if "GOOGLE_API_KEY" in st.secrets:
                try:
                    # 1. Konfiguration
                    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                    model = genai.GenerativeModel('gemini-2.0-flash') # Das Modell, das bei dir funktionierte!
                    
                    # 2. Gedächtnis bauen (WICHTIG für Logik!)
                    # System-Prompt mit aktuellen Daten
                    system_instruction = f"""
                    Du bist Günther, ein R+V Berater. Erfahrener Profi, norddeutsch-warmherzig, Du-Form.
                    Fakten zum Kunden:
                    - Brutto: {brutto} €
                    - Netto: {n_hh:.0f} €
                    - Rentenlücke: {r_luecke:.0f} € (Erkläre: Lücke im Alter)
                    - BU-Lücke: {b_luecke:.0f} € (Erkläre: Existenzrisiko heute. WICHTIGER als Rente!)
                    Antworte kurz, knackig und hilfreich. Keine Romane.
                    """
                    
                    # Verlauf zusammenbauen: System + letzte 4 Nachrichten (spart Tokens, behält aber Kontext)
                    history_for_api = [system_instruction]
                    for m in st.session_state.messages[-4:]:
                        history_for_api.append(f"{'Kunde' if m['role']=='user' else 'Günther'}: {m['content']}")
                    
                    # 3. API Abruf mit Retry-Schleife (gegen Fehler 429)
                    with st.spinner("Günther tippt..."):
                        response_text = ""
                        for attempt in range(3): # 3 Versuche
                            try:
                                response = model.generate_content(history_for_api)
                                response_text = response.text
                                break # Erfolg -> Raus aus der Schleife
                            except Exception as e:
                                if "429" in str(e):
                                    time.sleep(2) # Kurz warten
                                    continue
                                else:
                                    raise e # Anderer Fehler
                        
                        if response_text:
                            st.session_state.messages.append({"role": "assistant", "content": response_text})
                            st.rerun()
                        else:
                            st.error("Google ist gerade zu beschäftigt. Versuch es gleich nochmal.")
                            
                except Exception as e:
                    st.error(f"Ein technischer Fehler: {e}")
            else:
                st.warning("API Key fehlt in den Secrets!")

    # --- RECHTER BEREICH: SAFE & SMART ---
    with col_prod:
        st.subheader("🚀 Deine Lösung: Safe&Smart")
        st.markdown("""
        **Die R+V Ansparkombi.**
        Kombiniere die Sicherheit des R+V Sicherungsvermögens mit den Renditechancen der weltweiten Märkte.
        
        * ✅ Flexibel einzahlen & entnehmen
        * ✅ Inflationsschutz durch Sachwerte
        * ✅ IDD-konformer Prozess
        """)
        
        st.image("https://www.ruv.de/static-files/ruvde/images/privatkunden/geldanlage/safe-smart/safe-smart-visual-teaser.jpg", use_container_width=True)
        
        st.write("") # Abstand
        if st.button("Jetzt Safe&Smart simulieren ➔", type="primary", use_container_width=True):
            st.session_state.page = "produkt_info"
            st.rerun()

# --- 5. PRODUKT-RECHNER ---
elif st.session_state.page == "produkt_info":
    st.title("📈 Safe&Smart Rechner")
    c_l, c_r = st.columns(2)
    
    with c_l:
        st.subheader("Deine Sparziele")
        start = st.number_input("Startkapital (€)", 0, 100000, 5000)
        rate = st.slider("Monatliche Rate (€)", 25, 1000, 100)
        laufzeit = st.slider("Laufzeit (Jahre)", 5, 40, 20)
        
        verlauf = berechne_investment_verlauf(start, rate, laufzeit)
        endkapital = verlauf[-1]
        
        st.session_state.final_data = {"start": start, "rate": rate, "jahre": laufzeit, "summe": endkapital}
        st.metric("Voraussichtliches Kapital (Kaufkraft)", f"{endkapital:,.0f} €")

    with c_r:
        st.subheader("Entwicklung")
        st.line_chart(pd.DataFrame(verlauf, columns=["Wert"]))
    
    c1, c2 = st.columns(2)
    if c1.button("« Zurück"): st.session_state.page = "beratung"; st.rerun()
    if c2.button("Weiter zur Prüfung »", type="primary"): st.session_state.page = "idd"; st.rerun()

# --- 6. IDD PRÜFUNG ---
elif st.session_state.page == "idd":
    st.title("🛡️ Angemessenheitsprüfung")
    with st.form("idd_form"):
        st.selectbox("Kenntnisse", ["Keine", "Basis", "Erfahren"])
        rk = st.select_slider("Risikoklasse (SRI)", options=[1, 2, 3, 4, 5], value=3)
        st.checkbox("Nachhaltigkeitspräferenzen (ESG) berücksichtigen")
        
        if st.form_submit_button("Ergebnis bestätigen"):
            st.session_state.rk = rk
            st.session_state.page = "abschluss"
            st.rerun()

# --- 7. ABSCHLUSS & DOKUMENTE ---
elif st.session_state.page == "abschluss":
    st.title("🏁 Dein Simulations-Ergebnis")
    st.balloons()
    
    data = st.session_state.final_data
    
    # Goldene Ergebnis-Box
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #003366 0%, #0055aa 100%); padding: 30px; border-radius: 15px; text-align: center; color: white; border: 4px solid #ffcc00; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
        <h2 style="color: #ffcc00; margin: 0;">DEIN ZIEL-VERMÖGEN</h2>
        <h1 style="font-size: 4.5rem; margin: 10px 0;">{data['summe']:,.0f} €*</h1>
        <p style="opacity: 0.8;">*prognostizierte Kaufkraft nach {data['jahre']} Jahren</p>
    </div>
    """, unsafe_allow_html=True)

    c_info, c_docs = st.columns(2)
    with c_info:
        st.info(f"**Prüfergebnis:**\nDas Produkt passt zu deiner Risikoklasse **{st.session_state.rk}**. Die Sparrate von {data['rate']}€ ist tragbar.")
    
    with c_docs:
        # Dokumenten-Box (wieder da!)
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd;">
            <strong>📄 Bereitgestellte Dokumente:</strong><br>
            <span style="font-size: 1.2rem;">📝</span> Beratungsprotokoll (PDF)<br>
            <span style="font-size: 1.2rem;">📜</span> Produktinformationsblatt<br>
            <span style="font-size: 1.2rem;">⚖️</span> Verbraucherinformationen
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Der große Abschluss-Button
    if st.button("🚀 JETZT KOSTENPFLICHTIG ABSCHLIESSEN (SIMULATION)", type="primary", use_container_width=True):
        st.success("🎉 Antrag wurde erfolgreich simuliert! Vielen Dank.")
        st.balloons()
        
    if st.button("Neustart"):
        st.session_state.clear()
        st.rerun()
        
