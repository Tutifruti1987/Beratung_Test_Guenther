import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO
import time

# --- SETUP ---
st.set_page_config(page_title="R+V Günther", page_icon="🦁", layout="wide")

def get_logo():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=2)
        return Image.open(BytesIO(response.content))
    except: return None 

logo_img = get_logo()

# --- STYLING ---
st.markdown("""
<style>
    .stChatMessage p { font-size: 1.2rem !important; line-height: 1.6 !important; }
    .stChatMessage { border-radius: 15px; padding: 15px; border: 1px solid #e0e6ed; box-shadow: 2px 2px 8px rgba(0,0,0,0.05); }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #003366; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- MATHE (FIXED: GIBT JETZT GENAU 4 WERTE ZURÜCK) ---
def berechne_analyse(brutto, steuerklasse, kinder, alter):
    if brutto <= 0: return 0, 0, 0, 0
    
    # Netto-Basis
    st_faktor = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    netto = brutto * (1 - (st_faktor.get(steuerklasse, 0.40) - (kinder * 0.012)))
    netto_hh = netto + (kinder * 250)
    
    # Lücken (vereinfacht nach DIN-Logik)
    r_luecke = max(0, (netto_hh * 0.85 * (1.02**(67-alter))) - (brutto * 0.48))
    b_luecke = max(0, netto_hh - (brutto * 0.34))
    
    # Anzahl Förderwege
    f_anzahl = 0
    if steuerklasse != 6: f_anzahl += 1
    if kinder > 0: f_anzahl += 1
    if brutto > 5000: f_anzahl += 1
    
    return netto_hh, r_luecke, b_luecke, f_anzahl

# --- SIDEBAR ---
with st.sidebar:
    if logo_img: st.image(logo_img, width=80)
    st.header("📋 Deine Daten")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    st_klasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Anzahl Kinder", 0, 10, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Bruttogehalt (mtl.) in € *", 0, 25000, 0)
    if st.button("Gespräch löschen"):
        st.session_state.messages = []
        st.rerun()

# --- WERTE BERECHNEN (JETZT KORREKTES UNPACKING) ---
n_hh, r_luecke, b_luecke, f_anzahl = berechne_analyse(brutto, st_klasse, kinder, alter)

# --- DASHBOARD ---
c1, c2 = st.columns([1, 4])
with c1: 
    if logo_img: st.image(logo_img, width=120)
with c2: 
    st.title("R+V Vorsorge-Check")
    st.subheader("Beratung mit Günther")

if brutto == 0:
    st.info("👈 Moin! Trag links mal kurz dein Brutto ein, dann kann ich loslegen.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Netto-Haushalt", f"{n_hh:.0f} €")
col2.metric("Rentenlücke", f"{r_luecke:.0f} €")
col3.metric("BU-Lücke", f"{b_luecke:.0f} €")
col4.metric("Förderwege", f"{f_anzahl}")

st.divider()

# --- CHAT ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Günthers Charakter
# Günthers neues Profil: Seriöser Berater, kompetent & direkt
system_prompt = f"""
Du bist Günther, ein erfahrener Vorsorge-Experte der R+V. 
DEIN STIL:
- Professionell, sachlich und kompetent. 
- Du nutzt das "Du", bleibst aber höflich (keine flapsigen Sprüche wie "wa?" oder "Sümmchen").
- Deine Sätze sind klar und auf den Punkt. Komm ohne Umschweife zur Sache.
- Fachbegriffe nutzt du nur, wenn du sie kurz erklärst.

DEINE ANALYSE-LOGIK:
- Priorisiere den Einkommensschutz (BU) vor der Altersvorsorge. 
- Erkläre sachlich: Die BU sichert die Existenz im Hier und Jetzt, die Rente den Lebensstandard im Alter.

AKTUELLE DATEN:
- Monatliches Brutto: {brutto} € | Netto: {n_hh:.0f} €
- Rentenlücke: {r_luecke:.0f} € | BU-Lücke: {b_luecke:.0f} €

AUFTRAG:
1. Analysiere die Daten nur auf Wunsch kurz und präzise.
2. Nutze eine saubere Tabelle für die Zahlen.
3. Gib eine klare Empfehlung ab, welcher Schritt als nächstes sinnvoll ist (z.B. R+V BerufsunfähigkeitsPolice).
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Moin! Ich bin Günther. 👋 Schön, dass du da bist. Sollen wir mal gemeinsam über deine Zahlen schauen?"})

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Schreib mir einfach..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        # Flash-Lite für bessere Quoten bei Google
        model = genai.GenerativeModel('models/gemini-2.0-flash-lite')
        
        # Nur relevante Historie senden (Tokens sparen)
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages[-4:]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
            
        with st.spinner("Ich schau mal drüber..."):
            # Sanfter Retry bei Überlastung
            for i in range(3):
                try:
                    response = model.generate_content(history)
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    break
                except Exception as e:
                    if "429" in str(e) and i < 2:
                        time.sleep(4)
                        continue
                    else: raise e
    except Exception as e:
        st.error("Sry, Google ist gerade überlastet. Warte kurz 20 Sek. und schreib mir dann nochmal! 🙏")
