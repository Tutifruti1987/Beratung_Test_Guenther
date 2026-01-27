import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time

# --- KONFIGURATION ---
st.set_page_config(page_title="R+V Profi-Berater", page_icon="🦁", layout="wide")

# --- FUNKTION: R+V LOGO LADEN ---
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

# --- DESIGN (CSS) ---
st.markdown("""
<style>
    .stChatMessage p { font-size: 1.2rem !important; line-height: 1.6 !important; }
    .stChatMessage { border: 1px solid #e0e0e0; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    .stAlert { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- MATHEMATIK ---
def berechne_netto_genauer(brutto, steuerklasse, kinder):
    if brutto == 0: return 0, 0
    faktoren = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    abzug_quote = faktoren.get(steuerklasse, 0.40) - (kinder * 0.01)
    if abzug_quote < 0.2: abzug_quote = 0.2
    netto = brutto * (1 - abzug_quote)
    return netto, netto + (kinder * 250)

def ermittle_foerderung(brutto, steuerklasse, kinder, status):
    potenziale = []
    if brutto == 0: return []
    if steuerklasse != 6: potenziale.append("bAV (Direktversicherung) - Sozialabgaben sparen")
    if kinder > 0: potenziale.append(f"Riester-Rente - {kinder}x Kinderzulage sichern")
    elif brutto < 2500: potenziale.append("Riester-Rente - Förderquote prüfen")
    if brutto > 5200 or steuerklasse in [1, 3]: potenziale.append("Basisrente (Rürup) - Steuerlast senken")
    return potenziale

def berechne_alle_luecken(brutto, netto_hh, alter, rentenalter, inflation):
    if brutto == 0: return 0, 0
    jahre = rentenalter - alter
    gesetzl_rente = brutto * 0.48 
    kaufkraft = (1 + (inflation/100)) ** jahre
    wunsch_rente = netto_hh * 0.85 * kaufkraft
    rente_luecke = max(0, wunsch_rente - gesetzl_rente)
    # BU
    em_rente = brutto * 0.34
    bu_luecke = max(0, netto_hh - em_rente)
    return rente_luecke, bu_luecke

# --- SIDEBAR ---
with st.sidebar:
    if logo_img:
        st.image(logo_img, width=60)
    else:
        st.header("🦁 R+V") 
        
    st.header("Kundenprofil")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    steuerklasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Kinder", 0, 8, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    
    # Startwert 0
    brutto = st.number_input("Brutto (Monat) *", min_value=0, max_value=20000, value=0, help="Bitte hier dein Bruttogehalt eingeben.")
    
    st.divider()
    if st.button("Neustart"):
        st.session_state.messages = []
        st.rerun()

# --- HAUPTBEREICH ---
c1, c2 = st.columns([1, 6])
with c1:
    if logo_img:
        st.image(logo_img, width=100)
    else:
        st.title("🦁")
with c2:
    st.title("Profi-Bedarfsanalyse")
    st.caption(f"Status: {status} | Steuerklasse {steuerklasse} | {kinder} Kinder")

# LOGIK: WENN BRUTTO 0
if brutto == 0:
    st.warning("⚠️ Bitte gib zuerst dein Brutto-Einkommen in der Seitenleiste (links) ein.")
    netto_hh = 0
    rente_luecke = 0
    bu_luecke = 0
    foerder_liste = []
    foerder_str = ""
else:
    netto, netto_hh = berechne_netto_genauer(brutto, steuerklasse, kinder)
    rente_luecke, bu_luecke = berechne_alle_luecken(brutto, netto_hh, alter, 67, 2.0)
    foerder_liste = ermittle_foerderung(brutto, steuerklasse, kinder, status)
    foerder_str = "\n- ".join(foerder_liste)

# KACHELN
col1, col2, col3, col4 = st.columns(4)
col1.metric("Dein Netto (mtl.)", f"{netto_hh:.0f} €")
col2.metric("Rentenlücke", f"{rente_luecke:.0f} €", delta="- Bedarf" if brutto > 0 else None, delta_color="inverse")
col3.metric("BU-Lücke", f"{bu_luecke:.0f} €", delta="- Risiko" if brutto > 0 else None, delta_color="inverse")
col4.metric("Förder-Chancen", f"{len(foerder_liste)}", delta="Möglich" if brutto > 0 else None, delta_color="normal")

st.divider()

# --- KI GÜNTHER ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

system_prompt = f"""
Du bist Günther, R+V Experte.
Kunde: {alter}J, {status}, {kinder} Kinder. Brutto {brutto}.
Lücken (nur relevant wenn Brutto > 0):
- Rentenlücke: {rente_luecke:.0f} €
- BU-LÜCKE: {bu_luecke:.0f} €

Regeln:
1. Wenn Brutto=0, bitte höflich um Eingabe.
2. Wenn Brutto da ist: Analysiere erst nach "Go" des Kunden.
3. Sei empathisch, nutze das "Du".
4. Empfiehl R+V Produkte.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    intro_text = f"### 👋 Hallo!\nIch bin Günther, dein persönlicher R+V Berater.\n\nSoll ich deine Daten analysieren und wir steigen gemeinsam in die Versicherungsberatung ein?"
    st.session_state.messages.append({"role": "assistant", "content": intro_text})

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Antworte Günther (z.B. 'Ja, gerne')..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # Wir schicken nur die letzten Nachrichten, um Tokens zu sparen
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages[-5:]: # Nur die letzten 5 Nachrichten
            r = "user" if m["role"] == "user" else "model"
            history.append({"role": r, "parts": [m["content"]]})
            
        with st.spinner("Günther überlegt kurz..."):
            # Ein kleiner technischer Trick: Wir warten 1 Sekunde vor dem Senden
            time.sleep(1) 
            response = model.generate_content(history)
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ Google sagt: 'Zu schnell!'. Bitte warte kurz 30-60 Sekunden und probiere es dann nochmal.")
        else:
            st.error(f"Fehler: {e}")
