import streamlit as st
import google.generativeai as genai

# --- KONFIGURATION ---
st.set_page_config(page_title="R+V Profi-Check", page_icon="🦁", layout="wide")

# --- MATHEMATIK & LOGIK ---

def berechne_netto_genauer(brutto, steuerklasse, kinder):
    # Annäherungsfaktoren für 2024/2025 (Abzüge: Lohnsteuer + Sozialvers.)
    # Dies ersetzt keine DATEV-Berechnung, reicht aber für Beratungsimpulse!
    
    faktoren = {
        1: 0.39, # Ledig: ca 39% Abzug
        2: 0.36, # Alleinerziehend (Entlastungsbetrag): ca 36%
        3: 0.30, # Verheiratet (Besserverdiener): ca 30%
        4: 0.39, # Verheiratet (Gleich): ca 39%
        5: 0.52, # Verheiratet (Zuverdiener): ca 52% (hohe Abzüge!)
        6: 0.60  # Zweitjob: ca 60%
    }
    
    abzug_quote = faktoren.get(steuerklasse, 0.40)
    
    # Kinderfreibeträge senken die Steuerlast leicht (simuliert durch 1% Punkt pro Kind weniger Abzug)
    abzug_quote = abzug_quote - (kinder * 0.01)
    if abzug_quote < 0.2: abzug_quote = 0.2 # Minimum
    
    netto = brutto * (1 - abzug_quote)
    kindergeld = kinder * 250
    return netto, netto + kindergeld

def ermittle_foerderung(brutto, steuerklasse, kinder, status):
    # Logik-Weiche: Welche Töpfe stehen offen?
    potenziale = []
    
    # 1. bAV (Betriebliche Altersvorsorge)
    if steuerklasse != 6: # Fast jeder Arbeitnehmer
        potenziale.append("bAV (Direktversicherung): Brutto-Entgeltumwandlung spart Steuer & Sozialabgaben.")
        
    # 2. Riester (Zulagen-Rente)
    if kinder > 0:
        potenziale.append(f"Riester-Rente: Hohe Zulagenförderung durch {kinder} Kind(er) interessant.")
    elif brutto < 2500: # Geringverdiener
        potenziale.append("Riester-Rente: Förderquote prüfen (Grundzulage).")
        
    # 3. Rürup / Basisrente (Steuer-Rente)
    if brutto > 5200 or steuerklasse in [1, 3]: # Gutverdiener
        potenziale.append("Basisrente (Rürup): Hohe steuerliche Absetzbarkeit nutzen (Steuerhebel).")
        
    return potenziale

def berechne_luecken(brutto, netto_hh, alter, rentenalter, inflation, kinder):
    # Rente
    jahre = rentenalter - alter
    # Gesetzl. Rente ist Brutto-abhängig, nicht Netto!
    gesetzl_rente_erwartet = brutto * 0.48 
    kaufkraft = (1 + (inflation/100)) ** jahre
    
    wunsch_rente = netto_hh * 0.85 * kaufkraft # 85% vom heutigen Haushaltnetto halten
    rente_luecke = wunsch_rente - gesetzl_rente_erwartet
    
    # BU (34% Regel)
    bu_luecke = netto_hh - (brutto * 0.34)
    
    return max(0, rente_luecke), max(0, bu_luecke)

# --- SIDEBAR EINGABEN ---
with st.sidebar:
    st.header("📋 Steuer & Status")
    status = st.selectbox("Familienstand", ["Ledig", "Verheiratet", "Verwitwet"])
    steuerklasse = st.selectbox("Steuerklasse", [1, 2, 3, 4, 5, 6], index=0 if status=="Ledig" else 3)
    kinder = st.number_input("Kinder (Kindergeld)", 0, 8, 0)
    
    st.header("💰 Einkommen")
    alter = st.number_input("Alter", 18, 67, 35)
    brutto = st.number_input("Brutto (Monat)", 520, 20000, 4000)
    
    st.divider()
    if st.button("Reset Chat"):
        st.session_state.messages = []
        st.rerun()

# --- BERECHNUNGEN IM HINTERGRUND ---
netto, netto_hh = berechne_netto_genauer(brutto, steuerklasse, kinder)
rente_luecke, bu_luecke = berechne_luecken(brutto, netto_hh, alter, 67, 2.0, kinder)
foerder_liste = ermittle_foerderung(brutto, steuerklasse, kinder, status)
foerder_string = "\n- ".join(foerder_liste) # Für die KI formatieren

# --- DASHBOARD ---
st.title("🦁 R+V Profi-Berater")
st.caption(f"Steuerklasse {steuerklasse} | {kinder} Kinder | Netto-Haushalt ca. {netto_hh:.0f} €")

c1, c2, c3 = st.columns(3)
c1.metric("Dein Netto", f"{netto:.0f} €", help="Geschätzt nach Steuerklasse")
c2.metric("Rentenlücke", f"{rente_luecke:.0f} €", delta="Inflation 2% p.a.")
c3.metric("Mögliche Förderwege", f"{len(foerder_liste)}", help="Anzahl staatl. geförderter Optionen")

with st.expander("ℹ️ Details zu den Förderwegen (System-Analyse)"):
    for f in foerder_liste:
        st.write(f"• {f}")

st.divider()

# --- KI GÜNTHER ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("API Key fehlt.")
    st.stop()

system_instruction = f"""
Du bist Günther, R+V Versicherungsexperte (IDD, DIN 77230).
Du berätst ganzheitlich zu Vorsorge und Steuern.

KUNDEN-PROFIL:
- Alter: {alter}, Steuerklasse: {steuerklasse}, Kinder: {kinder}
- Brutto: {brutto}€ -> Netto (Haushalt): {netto_hh:.0f}€
- RENTENLÜCKE: {rente_luecke:.0f}€ (dringend!)
- BU-LÜCKE: {bu_luecke:.0f}€

SYSTEM-ANALYSE DER FÖRDERUNG (NUTZE DIESE HINWEISE):
Die Analyse hat folgende passende Wege identifiziert:
- {foerder_string}

DEINE AUFGABE:
1. Erkläre dem Kunden, was die Steuerklasse {steuerklasse} für sein Netto bedeutet.
2. Sprich die identifizierten Förderwege aktiv an (z.B. "Da du Kinder hast, lohnt sich Riester...").
3. Verknüpfe das mit R+V Produkten (R+V-AnlageKombi Safe+Smart, R+V-Direktversicherung, etc.).
4. Sei locker, professionell und nutze das "Du". 
5. Frage am Ende konkret, welchen Förderweg er genauer wissen will.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    start_msg = f"Hallo! Ich habe deine Daten (Steuerklasse {steuerklasse}) durchgerechnet. Wir haben eine Rentenlücke von ca. {rente_luecke:.0f} €, aber die gute Nachricht ist: Ich sehe **{len(foerder_liste)} Möglichkeiten für staatliche Zuschüsse**. Soll ich dir zeigen, wie du dir Geld vom Staat zurückholst?"
    st.session_state.messages.append({"role": "assistant", "content": start_msg})

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Antworte Günther..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        history = [{"role": "user", "parts": [system_instruction]}]
        for m in st.session_state.messages:
            r = "user" if m["role"] == "user" else "model"
            history.append({"role": r, "parts": [m["content"]]})
            
        with st.spinner("Günther prüft Fördertöpfe..."):
            response = model.generate_content(history)
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
    except Exception as e:
        st.error(e)
