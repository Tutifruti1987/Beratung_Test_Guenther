import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import pandas as pd # Neu für die Tabellen-Anzeige

# --- KONFIGURATION ---
st.set_page_config(page_title="R+V Profi-Berater", page_icon="🦁", layout="wide")

# --- FUNKTION: R+V LOGO ---
def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None 

logo_img = get_logo()

# --- DESIGN (CSS) ---
st.markdown("""
<style>
    .stChatMessage p { font-size: 1.15rem !important; }
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; border: 1px solid #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.7rem !important; color: #003366; }
</style>
""", unsafe_allow_html=True)

# --- MATHEMATIK-FUNKTIONEN ---
def berechne_werte(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, []
    
    # Netto-Schätzung
    faktoren = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto = brutto * (1 - (faktoren.get(steuerklasse, 0.40) - (kinder * 0.01)))
    netto_hh = netto + (kinder * 250)
    
    # Lücken
    jahre = 67 - alter
    wunsch_rente = netto_hh * 0.85 * ((1.02)**jahre)
    rente_luecke = max(0, wunsch_rente - (brutto * 0.48))
    bu_luecke = max(0, netto_hh - (brutto * 0.34))
    
    # Förderung
    foerder = []
    if steuerklasse != 6: foerder.append("bAV")
    if kinder > 0: foerder.append("Riester (Zulagen)")
    if brutto > 5000: foerder.append("Basisrente (Steuervorteil)")
    
    return netto_hh, rente_luecke, bu_luecke, foerder

# --- SIDEBAR ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=60)
    st.header("📋 Kundendaten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    steuerklasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Kinder", 0, 8, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Brutto (Monat) *", 0, 20000, 0)
    if st.button("Chat zurücksetzen"):
        st.session_state.messages = []
        st.rerun()

# --- BERECHNUNG AKTUALISIEREN ---
n_hh, r_luecke, b_luecke, f_liste = berechne_werte(brutto, steuerklasse, kinder, alter)

# --- HEADER & DASHBOARD ---
c1, c2 = st.columns([1, 5])
with c1: 
    if logo_img: st.image(logo_img, width=100)
with c2: 
    st.title("Versicherungs-Checkup")
    st.caption(f"Aktuelle Konfiguration: {status}, StKl. {steuerklasse}, {kinder} Kind(er)")

if brutto == 0:
    st.info("👈 Bitte gib links dein Brutto-Einkommen ein, um die Analyse zu starten.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
col2.metric("Rentenlücke", f"{r_luecke:.0f} €", delta="- Bedarf" if brutto>0 else None, delta_color="inverse")
col3.metric("BU-Lücke", f"{b_luecke:.0f} €", delta="- Risiko" if brutto>0 else None, delta_color="inverse")
col4.metric("Förderwege", f"{len(f_liste)}")

st.divider()

# --- CHAT LOGIK ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Der Prompt wird HIER bei jedem Durchlauf neu generiert mit den AKTUELLEN Werten
aktuelle_daten_hinweis = f"""
AKTUELLE DATEN AUS DEN EINGABEFELDERN:
- Brutto: {brutto} € (Falls 0, bitte den User höflich auffordern, es links einzutragen)
- Netto: {n_hh:.0f} €
- Rentenlücke: {r_luecke:.0f} €
- BU-Lücke: {b_luecke:.0f} €
- Kinder: {kinder}
- Steuerklasse: {steuerklasse}
"""

system_instruction = f"""
Du bist Günther, ein R+V Berater.
Regeln:
1. Antworte kurz und kundenorientiert ("Du").
2. Wenn der User "Ja" zur Analyse sagt oder nach Zahlen fragt, erstelle eine Markdown-Tabelle.
3. Berücksichtige IMMER die Werte aus 'AKTUELLE DATEN AUS DEN EINGABEFELDERN'.
4. Falls Brutto = 0 ist, erkläre, dass du ohne diese Angabe keine Lücken berechnen kannst.
{aktuelle_daten_hinweis}
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "### 👋 Hallo!\nIch bin Günther. Soll ich deine aktuellen Daten analysieren und in die Beratung einsteigen?"})

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Deine Nachricht..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        # Nutzung des stabilen Flash-Modells
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # Verlauf zusammenbauen
        history = [{"role": "user", "parts": [system_instruction]}]
        for m in st.session_state.messages:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
            
        with st.spinner("Günther rechnet..."):
            response = model.generate_content(history)
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
    except Exception as e:
        st.error(f"Fehler: {e}")
