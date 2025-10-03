import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🧠 Mind Reading Recommender", layout="wide")
st.title("🧠 Mind Reading Recommender")

# --- Config ---
CONTENT_API_URL = os.environ.get("CONTENT_API_URL", "https://mind-reading-func.azurewebsites.net/api/recommend")
AZURE_FUNCTION_KEY = os.environ.get("AZURE_FUNCTION_KEY")  # optionnel
DEFAULT_TOP_N = int(os.environ.get("TOP_N", 5))

def send_request(user_id, top_n=DEFAULT_TOP_N):
    """Appelle l’Azure Function et retourne les recommandations (Content + Surprise)."""
    url = CONTENT_API_URL
    if AZURE_FUNCTION_KEY:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}code={AZURE_FUNCTION_KEY}"
    try:
        resp = requests.post(url, json={"user_id": user_id, "top_n": top_n}, timeout=30)
        return resp.json() if resp.status_code == 200 else {"status":"error","text":resp.text}
    except Exception as e:
        return {"status":"error","error":str(e)}

# --- UI ---
user_id_input = st.text_input("Entrez votre user_id :", value="")
top_n_input = st.number_input("Top N", min_value=1, max_value=20, value=DEFAULT_TOP_N, step=1)

if st.button("Recommander"):
    if user_id_input.strip() == "":
        st.error("Merci d'entrer un user_id.")
    else:
        st.info(f"Recommandations pour user_id={user_id_input}, top_n={top_n_input}")
        with st.spinner("Récupération des recommandations..."):
            result = send_request(user_id_input.strip(), int(top_n_input))

        if result.get("status") != "ok":
            st.error(f"Erreur API: {result}")
        else:
            col1, col2 = st.columns((1,1))

            with col1:
                st.subheader("🔥 Content-Based")
                recs_cb = result.get("content_based", [])
                if recs_cb:
                    df_cb = pd.DataFrame(recs_cb)
                    st.dataframe(df_cb, use_container_width=True)
                else:
                    st.warning("Pas de recommandations content-based")

            with col2:
                st.subheader("🎯 Surprise (SVD)")
                recs_sp = result.get("surprise_svd", [])
                if recs_sp:
                    df_sp = pd.DataFrame(recs_sp)
                    st.dataframe(df_sp, use_container_width=True)
                else:
                    st.warning("Pas de recommandations surprise")
