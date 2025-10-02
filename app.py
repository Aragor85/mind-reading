import os
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="🧠 Mind Reading Recommender", layout="wide")
st.title("🧠 Mind Reading Recommender (Azure)")

API_URL = "https://mind-reading-func.azurewebsites.net/api/recommend"

# Récupérer la clé depuis les variables d'environnement
FUNCTION_KEY = os.environ.get("AZURE_FUNCTION_KEY")
if not FUNCTION_KEY:
    st.warning("⚠️ La variable d'environnement AZURE_FUNCTION_KEY n'est pas définie !")

# Input utilisateur
user_id_input = st.text_input("Entrez votre user_id :")

# Bouton pour générer les recommandations
if st.button("Recommander"):
    user_id_input = (user_id_input or "").strip()
    if user_id_input == "":
        st.error("Merci d'entrer un user_id.")
    elif not user_id_input.isdigit():
        st.error("user_id doit être un entier.")
    else:
        user_id = int(user_id_input)
        payload = {"user_id": user_id, "top_n": 5}

        # Ajouter la clé dans l'en-tête si elle existe
        headers = {"Content-Type": "application/json"}
        if FUNCTION_KEY:
            headers["x-functions-key"] = FUNCTION_KEY

        with st.spinner("🔄 Contact de l’API Azure..."):
            try:
                resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
                st.text(f"Status HTTP: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") != "ok":
                        st.error(f"Erreur API: {data.get('message')}")
                        st.json(data.get("meta"))
                    else:
                        recs = data.get("content_based", [])
                        if not recs:
                            st.warning("Aucune recommandation trouvée pour cet utilisateur.")
                        else:
                            df = pd.DataFrame(recs)
                            cols = [c for c in ("article_id","similarity","category_id","publisher_id","words_count","created_at_ts") if c in df.columns]
                            st.dataframe(df[cols] if cols else df)

                            st.success(f"{len(df)} recommandation(s) reçue(s) !")
                            with st.expander("🔍 Détails de debug / meta"):
                                st.json(data.get("meta"))
                else:
                    st.error(f"Erreur {resp.status_code}: {resp.text}")

            except requests.exceptions.Timeout:
                st.error("⏱️ Timeout: impossible de contacter l’API Azure.")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Erreur lors de la requête HTTP : {e}")
            except Exception as e:
                st.error(f"❌ Erreur inattendue : {e}")
