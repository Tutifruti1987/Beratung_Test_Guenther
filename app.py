import streamlit as st
import google.generativeai as genai
import os

st.title("🔧 API Diagnose-Tool")

# API Key holen
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("Kein API Key in den Secrets gefunden!")
    st.stop()

genai.configure(api_key=api_key)

st.write(f"API Key Endung: ...{api_key[-4:]}")

if st.button("Test: Welche Modelle sehe ich?"):
    try:
        st.info("Frage Google Server ab...")
        models = list(genai.list_models())
        
        found_any = False
        st.write("### Verfügbare Modelle für deinen Key:")
        
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                st.success(f"✅ {m.name}")
                found_any = True
                
        if not found_any:
            st.warning("Keine Text-Modelle gefunden. Prüfe Google AI Studio Region/Billing.")
            
    except Exception as e:
        st.error(f"Fehler bei der Verbindung: {e}")
        st.markdown("---")
        st.write("**Mögliche Ursachen:**")
        st.write("1. API Key ist ungültig.")
        st.write("2. 'Google AI Studio' ist in deinem Google-Konto nicht aktiv.")
        st.write("3. Bibliothek zu alt (wurde requirements.txt aktualisiert?).")
