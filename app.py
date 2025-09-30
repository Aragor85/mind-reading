import streamlit as st
import requests
import pandas as pd

st.title("🧠 Mind Reading Recommender (Azure)")

# URL publique de ton Azure Function App
API_URL = "https://mind-reading-func.azurewebsites.net/api/recommend"

user_id = st.text_input("Entrez votre user_id :")

if st.button("Recommander"):
    try:
        resp = requests.post(API_URL, json={"user_id": user_id})
        if resp.status_code == 200:
            data = resp.json()
            st.success("✅ Recommandations Content-Based reçues depuis Azure !")

            # === Content-Based ===
            st.subheader("📚 Recommandations Content-Based")
            df_content = pd.DataFrame(data["diagnostics"]["summary"]["head_sample"])
            st.dataframe(df_content)

        else:
            st.error(f"Erreur {resp.status_code}: {resp.text}")

    except Exception as e:
        st.error(f"❌ Impossible de contacter l’API Azure : {e}")
