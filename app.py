import streamlit as st
import requests
import pandas as pd

st.title("🧠 Mind Reading Recommender (Azure)")

API_URL = "https://mind-reading-func.azurewebsites.net/api/recommend"  # mets l'URL exacte

user_id = st.text_input("Entrez votre user_id :")

if st.button("Recommander"):
    try:
        resp = requests.post(API_URL, json={"user_id": user_id, "top_n": 5}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            st.success("✅ Recommandations Content-Based reçues depuis Azure !")

            recs = data.get("content_based", [])
            if len(recs) == 0:
                st.warning("Aucune recommandation trouvée pour cet utilisateur.")
            else:
                df = pd.DataFrame(recs)
                # colonnes à afficher si présentes
                cols = []
                if 'article_id' in df.columns:
                    cols.append('article_id')
                if 'similarity' in df.columns:
                    cols.append('similarity')
                # ajoute d'autres colonnes si utiles pour toi
                st.dataframe(df[cols] if cols else df)
                if len(df) < 5:
                    st.info(f"Seulement {len(df)} recommandation(s) retournée(s) (top demandé: 5).")
        else:
            st.error(f"Erreur {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"❌ Impossible de contacter l’API Azure : {e}")
