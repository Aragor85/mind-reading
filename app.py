import os
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="🧠 Mind Reading Recommender", layout="wide")
st.title("🧠 Mind Reading Recommender content_based")

API_URL = os.environ.get("AZURE_FUNCTION_URL", "https://mind-reading-func.azurewebsites.net/api/recommend")
FUNCTION_KEY = os.environ.get("AZURE_FUNCTION_KEY")  # à définir dans Container App

with st.form("req_form"):
    user_id_input = st.text_input("Entrez votre user_id :")
    top_n = st.number_input("Top N", min_value=1, max_value=5, value=5, step=1)
    submit = st.form_submit_button("Recommander")

if submit:
    user_id_input = (user_id_input or "").strip()
    if user_id_input == "":
        st.error("Merci d'entrer un user_id.")
    elif not user_id_input.isdigit():
        st.error("user_id doit être un entier.")
    else:
        user_id = int(user_id_input)
        payload = {"user_id": user_id, "top_n": int(top_n)}
        headers = {"Content-Type": "application/json"}
        if FUNCTION_KEY:
            headers["x-functions-key"] = FUNCTION_KEY

        with st.spinner("🔄 Contact Azure Funct..."):
            try:
                resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            except requests.exceptions.Timeout:
                st.error("⏱️ Timeout lors de la requête vers l'API.")
                st.stop()
            except Exception as e:
                st.error(f"❌ Erreur réseau: {e}")
                st.stop()

        if resp.status_code != 200:
            st.error(f"Erreur HTTP {resp.status_code} : {resp.text}")
        else:
            try:
                data = resp.json()
            except Exception as e:
                st.error(f"Réponse invalide JSON : {e}")
                st.code(resp.text)
                st.stop()

            if data.get("status") != "ok":
                st.error(f"API renvoie une erreur: {data.get('message')}")
                st.json(data.get("meta"))
            else:
                recs = data.get("content_based", [])
                st.success(f"✅ {len(recs)} recommandation(s) reçue(s)")
                if len(recs) == 0:
                    st.warning("Aucune recommandation pour cet utilisateur.")
                else:
                    df = pd.DataFrame(recs)

                    # --- Garder seulement article_id et similarity ---
                    cols = [c for c in ("article_id", "similarity") if c in df.columns]
                    if 'article_id' in df.columns:
                        # Convertir en string pour garder les ID non numériques intacts
                        df['article_id'] = df['article_id'].astype(str)

                    st.dataframe(df[cols], use_container_width=True)

                # afficher meta (diagnostics) repliable
                if "meta" in data:
                    st.expander("🔍 Détails / diagnostics").write(data["meta"])
