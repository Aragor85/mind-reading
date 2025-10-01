import streamlit as st
import requests
import pandas as pd

st.title("🧠 Mind Reading Recommender (Azure)")

API_URL = "https://mind-reading-func.azurewebsites.net/api/recommend"  

user_id_input = st.text_input("Entrez votre user_id :")

if st.button("Recommander"):
    try:
        if not user_id_input.strip().isdigit():
            st.error("❌ Merci d’entrer un entier valide pour user_id.")
        else:
            user_id = int(user_id_input)  # conversion ici
            payload = {"user_id": user_id, "top_n": 5}
            headers = {"Content-Type": "application/json"}

            resp = requests.post(API_URL,json={"user_id": user_id, "top_n": 5},headers={"Content-Type": "application/json"},timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                st.success("✅ Recommandations Content-Based reçues depuis Azure !")

                recs = data.get("content_based", [])
                if len(recs) == 0:
                    st.warning("Aucune recommandation trouvée pour cet utilisateur.")
                else:
                    df = pd.DataFrame(recs)
                    # colonnes à afficher
                    cols = []
                    for c in ("article_id", "similarity", "category_id", "publisher_id", "words_count"):
                        if c in df.columns:
                            cols.append(c)
                    st.dataframe(df[cols] if cols else df)

                    if len(df) < 5:
                        st.info(f"Seulement {len(df)} recommandation(s) retournée(s) (top demandé: 5).")
            else:
                st.error(f"Erreur {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"❌ Impossible de contacter l’API Azure : {e}")
