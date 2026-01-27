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

# Günthers neues "warmes" Gehirn
system_prompt = f"""
Du bist Günther. Ein Typ, mit dem man gerne ein Bier trinkt oder einen Kaffee, 
der aber verdammt viel Ahnung von Versicherungen hat (R+V). 

DEIN STIL:
- Du bist herzlich, locker und direkt. Kein Fach-Chinesisch.
- Du nutzt das "Du" ganz natürlich.
- Sag niemals "nach DIN 77230" oder "IDD-konform". Berate einfach danach, ohne es zu benennen.
- Wenn die BU-Lücke groß ist, sag nicht "Existenzrisiko", sondern eher: "Mensch, wenn dir was passiert, wird's finanziell echt eng. Das müssen wir uns zuerst anschauen."

DEINE DATEN FÜR DIESEN CHAT:
- Alter: {alter}, {kinder} Kinder, Brutto: {brutto} €
- Netto: {n_hh:.0f} €, Rentenlücke: {r_luecke:.0f} €, BU-Lücke: {b_luecke:.0f} €

DEIN AUFTRAG:
1. Falls Brutto 0 ist: Sag charmant, dass du ohne eine Zahl im Feld links nicht wirklich rechnen kannst.
2. Wenn Brutto da ist: Warte kurz auf ein "Go".
3. Wenn du analysierst: Mach es anschaulich. Erklär dem Kunden, warum die BU-Lücke wichtiger ist als die Rente, als würdest du es einem guten Freund erklären.
4. Nutze Tabellen nur, wenn es wirklich hilft, die Übersicht zu behalten.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    # Herzlichere Begrüßung
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "### Moin! Ich bin Günther. 👋\n\nSchön, dass du da bist! Ich hab hier schon mal deine Eckdaten im Blick. Sollen wir mal gemeinsam drüber schauen, wo du gut aufgestellt bist und wo wir vielleicht noch mal ran müssen?"
    })

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Schreib mir einfach..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
            
        with st.spinner("Ich schau mal kurz drüber..."):
            for i in range(3):
                try:
                    response = model.generate_content(history)
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    break
                except Exception as e:
                    if "429" in str(e) and i < 2:
                        time.sleep(3)
                        continue
                    else: raise e
    except Exception as e:
        st.error(f"Sorry, mein System hakt kurz. Probier's bitte in 10 Sekunden noch mal! ({e})")
