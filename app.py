import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
from io import BytesIO

# --- KONFIGURATION (Löwe als Icon = Absturzsicher) ---
st.set_page_config(page_title="R+V Profi-Berater", page_icon="🦁", layout="wide")

# --- FUNKTION: R+V LOGO LADEN (Ausfallsicher) ---
def get_logo():
    # Wir versuchen, das Logo von einer stabilen Quelle zu laden
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/R%2BV-Logo.svg/512px-R%2BV-Logo.svg.png"
    try:
        # User-Agent Header verhindert Blockierung
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except:
        pass
    return None # Falls es fehlschlägt, geben wir "Nichts" zurück, damit kein Fehler kommt

# Logo einmal laden
logo_img = get_logo()

# --- DESIGN (CSS) ---
st.markdown("""
<style>
    .stChatMessage p { font-size: 1.2rem !important; line-height: 1.6 !important; }
    .stChatMessage { border: 1px solid #e0e0e0; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)

# --- MATHEMATIK ---
def berechne_netto_genauer(brutto, steuerklasse, kinder):
    faktoren = {1: 0.39, 2: 0.36, 3: 0.30, 4: 0.39, 5: 0.52, 6: 0.60}
    abzug_quote = faktoren.get(steuerklasse, 0.40) - (kinder * 0.01)
    if abzug_quote < 0.2: abzug_quote = 0.2
    netto = brutto * (1 - abzug_quote)
    return netto, netto + (kinder * 250)

def ermittle_foerderung(brutto, steuerklasse, kinder, status):
    potenziale = []
    if steuerklasse != 6: potenziale.append("bAV (Direktversicherung) - Sozialabgaben sparen")
    if kinder > 0: potenziale.append(f"Riester-Rente - {kinder}x Kinderzulage sichern")
    elif brutto < 2500: potenziale.append("Riester-Rente - Förderquote prüfen")
    if brutto > 5200 or steuerklasse in [1, 3]: potenziale.append("Basisrente (Rürup) - Steuerlast senken")
    return potenziale

def berechne_alle_luecken(brutto, netto_hh, alter, rentenalter, inflation):
    jahre = rentenalter - alter
    gesetzl_rente = brutto * 0.48 
    kaufkraft = (1 + (inflation/100)) ** jahre
    wunsch_rente = netto_hh * 0.85 * kaufkraft
    rente_luecke = max(0, wunsch_rente - gesetzl_rente)
    
    # BU (Berufsunfähigkeit)
    # Annahme: Staat zahlt max ca. 34% vom Brutto als volle EM-Rente
    em_rente = brutto * 0.34
    bu_luecke = max(0, netto_hh - em_rente)
    
    return rente_luecke, bu_luecke

# --- SIDEBAR ---
with st.sidebar:
    if logo_img:
        st.image(logo_img, width=60)
    else:
        st.header("🦁 R+V") # Text-Alternative falls Internet hakt
        
    st.header("Kundenprofil")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    steuerklasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=2 if status=="Verheiratet" else 0)
    kinder = st.number_input("Kinder", 0, 8, 0)
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Brutto", 520, 20000, 4500)
    
    st.divider()
    if st.button("Reset"):
        st.session_state.messages = []
        st.rerun()

# --- BERECHNUNG ---
netto, netto_hh = berechne_netto_genauer(brutto, steuerklasse, kinder)
rente_luecke, bu_luecke = berechne_alle_luecken(brutto, netto_hh, alter, 67, 2.0)
foerder_liste = ermittle_foerderung(brutto, steuerklasse, kinder, status)
foerder_str = "\n- ".join(foerder_liste)

# --- DASHBOARD HEADER ---
c1, c2 = st.columns([1, 6])
with c1:
    if logo_img:
        st.image(logo_img, width=100)
    else:
        st.title("🦁")
with c2:
    st.title("Profi-Bedarfsanalyse")
    st.caption(f"Status: {status} | Steuerklasse {steuerklasse} | {kinder} Kinder")

# --- DIE 4 KACHELN ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Dein Netto (mtl.)", f"{netto_hh:.0f} €", help="Geschätztes Haushaltsnetto inkl. Kindergeld")
col2.metric("Rentenlücke", f"{rente_luecke:.0f} €", delta="- Handlungsbedarf", delta_color="inverse")
col3.metric("BU-Lücke", f"{bu_luecke:.0f} €", delta="- Existenzbedrohend", delta_color="inverse", help="Fehlbetrag bei Erwerbsminderung")
col4.metric("Förder-Chancen", f"{len(foerder_liste)}", delta="Staatl. Zuschüsse", delta_color="normal")

st.divider()

# --- KI GÜNTHER ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

system_prompt = f"""
Du bist Günther, R+V Experte.
Kunde: {alter}J, {status}, {kinder} Kinder. Brutto {brutto}.
Finanz-Check:
1. Netto-Haushalt: {netto_hh:.0f} €
2. Rentenlücke: {rente_luecke:.0f} €
3. BU-LÜCKE (WICHTIG!): {bu_luecke:.0f} € (Wenn er nicht mehr arbeiten kann).
4. Förder-Optionen: {foerder_str}.

Deine Aufgabe:
- Erwähne die hohe BU-Lücke, das ist existenzbedrohend! Priorität 1.
- Empfiehl die R+V BerufsunfähigkeitsPolice.
- Sei freundlich, Duz-Form.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    
    # Dynamischer Start je nach Risiko
    if bu_luecke > 1000:
        intro_text = f"### 👋 Hallo!\nIch bin Günther. Ich habe deine Daten geprüft.\n\nEhrlich gesagt: Die **BU-Lücke von {bu_luecke:.0f} €** macht mir Sorgen. Das ist das Geld, das fehlt, wenn du krankheitsbedingt ausfällst. Lass uns zuerst die **R+V BerufsunfähigkeitsPolice** ansehen, bevor wir zur Rente kommen, okay?"
    else:
        intro_text = f"### 👋 Hallo!\nIch bin Günther. Dein Netto sieht gut aus ({netto_hh:.0f} €). Bei der Rente fehlen uns später ca. **{rente_luecke:.0f} €**. Wollen wir uns ansehen, wie wir das mit staatlicher Förderung schließen?"
        
    st.session_state.messages.append({"role": "assistant", "content": intro_text})

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Deine Frage an Günther..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        history = [{"role": "user", "parts": [system_prompt]}]
        for m in st.session_state.messages:
            r = "user" if m["role"] == "user" else "model"
            history.append({"role": r, "parts": [m["content"]]})
            
        with st.spinner("..."):
            response = model.generate_content(history)
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
    except Exception as e:
        st.error(e)
