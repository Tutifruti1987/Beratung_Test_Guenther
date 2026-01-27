import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time

# --- SETUP & KONFIGURATION ---
st.set_page_config(page_title="R+V Berater Günther", page_icon="🦁", layout="wide")

# --- FUNKTION: R+V LOGO (Stabil via URL) ---
def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=2)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except:
        pass
    return None 

logo_img = get_logo()

# --- DESIGN (CSS für professionelles Look & Feel) ---
st.markdown("""
<style>
    .stChatMessage p { font-size: 1.15rem !important; line-height: 1.6 !important; }
    .stChatMessage { border-radius: 12px; padding: 15px; border: 1px solid #e0e6ed; box-shadow: 1px 1px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #003366; font-weight: bold; }
    .stAlert { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- MATHEMATIK-LOGIK (Vorsorge-Rechner) ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, 0
    
    # Netto-Schätzung
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto_basis = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto_basis + (kinder * 250) # Inkl. Kindergeld
    
    # Rentenlücke (Ziel: 85% vom Netto, 2% Inflation)
    jahre_bis_rente = 67 - alter
    ziel_rente = netto_hh * 0.85 * (1.02 ** jahre_bis_rente)
    r_luecke = max(0, ziel_rente - (brutto * 0.48)) # Annahme: 48% Rentenniveau vom Brutto
    
    # BU-Lücke (Absicherung des aktuellen Netto vs. Erwerbsminderungsrente)
    b_luecke = max(0, netto_hh - (brutto * 0.34)) # Annahme: 34% EM-Rente vom Brutto
    
    # Förderwege zählen
    f_anzahl = 0
    if steuerklasse != 6: f_anzahl += 1 # bAV
    if kinder > 0: f_anzahl += 1 # Riester
    if brutto > 5000: f_anzahl += 1 # Rürup
    
    return netto_hh, r_luecke, b_luecke, f_anzahl

# --- SIDEBAR (Dateneingabe) ---
with st.sidebar:
    if logo_img:
        st.image(logo_img, width=80)
    st.header("📋 Kundendaten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Bruttogehalt (mtl.) in € *", 0, 25000, 0, step=100)
    
    st.divider()
    if st.button("Beratung zurücksetzen"):
        st.session_state.messages = []
        st.rerun()

# --- BERECHNUNG DER WERTE ---
n_hh, r_luecke, b_luecke, f_anzahl = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- DASHBOARD HEADER ---
c1, c2 = st.columns([1, 4])
with c1: 
    if logo_img: st.image(logo_img, width=120)
with c2: 
    st.title("R+V Vorsorgeanalyse")
    st.subheader("Ihr Experte: Günther")

if brutto == 0:
    st.warning("👈 Bitte geben Sie links Ihr monatliches Bruttogehalt ein, um die Analyse zu starten.")

# Metriken (Kacheln)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
col2.metric("Rentenlücke", f"{r_luecke:.0f} €", delta="Bedarf" if brutto > 0 else None, delta_color="inverse")
col3.metric("BU-Lücke", f"{b_luecke:.0f} €", delta="Risiko" if brutto > 0 else None, delta_color="inverse")
col4.metric("Förderwege", f"{f_anzahl}")

st.divider()

# --- KI-CHAT SYSTEM ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Dynamischer System-Prompt
if brutto > 0:
    daten_kontext = f"""
    AKTUELLE DATEN:
    - Alter: {alter}, Kinder: {kinder}
    - Brutto: {brutto} € | Netto-Haushalt: {n_hh:.0f} €
    - Rentenlücke: {r_luecke:.0f} € | BU-Lücke: {b_luecke:.0f} €
    """
    handlungsanweisung = "Analysieren Sie die Lücken präzise und empfehlen Sie als erste Priorität die R+V BerufsunfähigkeitsPolice."
else:
    daten_kontext = "HINWEIS: Bruttoeinkommen steht auf 0 €."
    handlungsanweisung = "Erklären Sie freundlich, dass für eine korrekte Analyse die Angabe des monatlichen Bruttogehalts im linken Feld erforderlich ist."

system_prompt = f"""
Du bist Günther, ein erfahrener Vorsorge-Experte der R+V Versicherung.
STIL: Professionell, sachlich, kompetent und direkt. Keine flapsigen Sprüche.
KOMMUNIKATION: Du nutzt das "Du", bleibst aber seriös und höflich.

{daten_kontext}

AUFTRAG:
1. {handlungsanweisung}
2. Nutzen Sie für die Darstellung der Zahlen immer eine übersichtliche Tabelle.
3. Erklären Sie kurz, dass Existenzschutz (BU) Vorrang vor Altersvorsorge hat.
"""

# Chat-Historie Initialisierung
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Guten Tag! Ich bin Günther. Gerne unterstütze ich Sie bei Ihrer Vorsorgeplanung. Sollen wir direkt in die Analyse Ihrer aktuellen Daten einsteigen?"
    })

# Chat anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- CHAT Eingabe ---
if prompt := st.chat_input("Ihre Frage an Günther..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        # Wir nutzen jetzt das Modell, das in deiner Diagnose-Liste definitiv vorhanden war
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Verlauf mit System-Anweisung
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages[-6:]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
            
        with st.spinner("Analyse wird erstellt..."):
            for i in range(3):
                try:
                    # Der Standardaufruf (nutzt automatisch die stabilste API-Version)
                    response = model.generate_content(history)
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    break
                except Exception as e:
                    if "429" in str(e) and i < 2:
                        time.sleep(5)
                        continue
                    else:
                        raise e
                        
    except Exception as e:
        # Detaillierte Fehlermeldung für uns zur Diagnose
        st.error(f"Hinweis: {e}")
