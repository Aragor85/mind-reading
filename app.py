import streamlit as st
import requests
import pandas as pd

st.title("🧠 Mind Reading Recommender (Azure)")

API_URL = "https://mind-reading-func.azurewebsites.net/api/recommend"

user_id_input = st.text_input("Entrez votre user_id :")

if st.button("Recommander"):
    try:
        user_id_input = (user_id_input or "").strip()
        if user_id_input == "":
            st.error("Merci d'entrer un user_id.")
        elif not user_id_input.isdigit():
            st.error("user_id doit être un entier.")
        else:
            user_id = int(user_id_input)
            payload = {"user_id": user_id, "top_n": 5}
            # force explicit content-type header
            headers = {"Content-Type": "application/json"}
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=20)

            if resp.status_code == 200:
                data = resp.json()
                st.success("✅ Recommandations Content-Based reçues depuis Azure !")
                recs = data.get("content_based", [])
                if not recs:
                    st.warning("Aucune recommandation trouvée pour cet utilisateur.")
                else:
                    df = pd.DataFrame(recs)
                    cols = [c for c in ("article_id","similarity","category_id","publisher_id","words_count","created_at_ts") if c in df.columns]
                    st.dataframe(df[cols] if cols else df)
                    if len(df) < 5:
                        st.info(f"Seulement {len(df)} recommandation(s) retournée(s) (top demandé: 5).")
            else:
                st.error(f"Erreur {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"❌ Impossible de contacter l’API Azure : {e}")
