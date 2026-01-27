import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="R+V Berater Günther", page_icon="🦁", layout="wide")

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
    .stChatMessage p { font-size: 1.2rem !important; line-height: 1.6 !important; }
    .stChatMessage { border-radius: 15px; padding: 20px; margin-bottom: 15px; border: 1px solid #e0e6ed; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    div[data-testid="stMetricValue"] { font-size: 2rem !important; color: #003366; font-weight: bold; }
    .stAlert { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- MATHEMATIK-KERN ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, []
    
    # Netto-Schätzung nach deutschen Standards
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto_basis = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto_basis + (kinder * 250)
    
    # DIN 77230 Orientierung: Absicherungsbedarf
    jahre_bis_rente = 67 - alter
    wunsch_niveau = 0.85 # 85% vom Netto
    inflation = 1.02 # 2%
    ziel_rente = netto_hh * wunsch_niveau * (inflation ** jahre_bis_rente)
    
    r_luecke = max(0, ziel_rente - (brutto * 0.48))
    b_luecke = max(0, netto_hh - (brutto * 0.34)) # Erwerbsminderungs-Lücke
    
    foerder = []
    if steuerklasse != 6: foerder.append("Betriebliche Altersvorsorge (bAV)")
    if kinder > 0: foerder.append("Riester-Förderung (Zulagen)")
    if brutto > 5000: foerder.append("Basisrente (Rürup) für Steuervorteile")
    
    return netto_hh, r_luecke, b_luecke, foerder

# --- SIDEBAR ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=80)
    st.header("📋 Dateneingabe")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Bruttogehalt (mtl.) in € *", 0, 25000, 0, step=100)
    
    st.divider()
    if st.button("Beratung neu starten"):
        st.session_state.messages = []
        st.rerun()

# --- ANALYSE-WERTE ---
n_hh, r_luecke, b_luecke, f_wege = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- HEADER & COCKPIT ---
c1, c2 = st.columns([1, 4])
with c1: 
    if logo_img: st.image(logo_img, width=120)
with c2: 
    st.title("Persönliche R+V Vorsorgeanalyse")
    st.subheader(f"Berater: Günther")

if brutto == 0:
    st.warning("👈 Willkommen! Bitte gib links dein Bruttogehalt ein, damit ich deine Vorsorgesituation analysieren kann.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Haushalts-Netto", f"{n_hh:.0f} €")
col2.metric("Rentenlücke", f"{r_luecke:.0f} €", delta="Bedarf" if brutto>0 else None, delta_color="inverse")
col3.metric("BU-Lücke", f"{b_luecke:.0f} €", delta="Risiko" if brutto>0 else None, delta_color="inverse")
col4.metric("Förderwege", f"{len(f_wege)}")

st.divider()

# --- CHAT-SYSTEM ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Der umfassende Berater-Prompt (Deine Instruktionen)
system_prompt = f"""
Du bist Günther, ein erfahrener Versicherungsberater der R+V Versicherung.
QUALIFIKATION: Vollumfänglich (Kranken, Vorsorge, Geldanlage, Komposit, Tier).
STANDARDS: Du berätst nach deutschem Recht, IDD und DIN 77230.
TONFALL: Hilfsbereit, kundenorientiert, professionell, kurze Sätze, "Du"-Form.
REGEL: Keine Halluzinationen. Nutze reale R+V Produkte (z.B. R+V BerufsunfähigkeitsPolice, R+V PrivatRente).

AKTUELLE KUNDENDATEN:
- Alter: {alter}, Steuerklasse: {st_klasse}, Kinder: {kinder}
- Monatliches Brutto: {brutto} €
- Berechnetes Netto: {n_hh:.0f} €
- Rentenlücke (inflationsbereinigt): {r_luecke:.0f} €
- BU-Lücke (Existenzrisiko): {b_luecke:.0f} €
- Mögliche Förderungen: {", ".join(f_wege) if f_wege else "Keine direkt ersichtlich"}

AUFGABE:
1. Wenn der Kunde noch kein Brutto (0 €) eingegeben hat, weise höflich darauf hin.
2. Beginne das Gespräch erst richtig, wenn der Kunde zustimmt.
3. Bereite Ergebnisse anschaulich auf (Nutze Tabellen für Lücken).
4. Gehe auf Bedürfnisse ein und priorisiere Existenzschutz (BU) vor Altersvorsorge (DIN 77230).
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Hallo ich bin Günther, dein persönlicher Versicherungsberater, wie kann ich dir helfen? Soll ich deine aktuelle Vorsorgesituation einmal analysieren?"})

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Deine Nachricht an Günther..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
            
        with st.spinner("Günther erstellt deine Analyse..."):
            # Retry-Logik gegen Fehler 429
            for i in range(3): # 3 Versuche
                try:
                    response = model.generate_content(history)
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    break
                except Exception as e:
                    if "429" in str(e) and i < 2:
                        time.sleep(2) # Kurz warten
                        continue
                    else: raise e
            
    except Exception as e:
        st.error(f"Hinweis: Der Server ist gerade stark ausgelastet ({e}). Bitte sende deine Nachricht in 10 Sekunden nochmal.")
