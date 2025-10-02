# app.py
import os
import json
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="🧠 Mind Reading Recommender", layout="centered")
st.title("🧠 Mind Reading Recommender (Azure)")

# URL de base (sans clé). On ajoutera la clé si elle est fournie.
API_BASE = "https://mind-reading-func.azurewebsites.net/api/recommend"

# Récupérer la clé de fonction si fournie (Streamlit Cloud: st.secrets, sinon env)
FUNCTION_KEY = None
if st.secrets and "FUNCTION_KEY" in st.secrets:
    FUNCTION_KEY = st.secrets["FUNCTION_KEY"]
else:
    FUNCTION_KEY = os.environ.get("FUNCTION_KEY")

# UI: inputs
col1, col2 = st.columns([3, 1])
with col1:
    user_id_input = st.text_input("Entrez votre user_id :", value="")
with col2:
    top_n = st.number_input("Top N", min_value=1, max_value=20, value=5, step=1)

show_meta = st.checkbox("Afficher diagnostics / réponse brute (debug)", value=False)

# Option: montrer/éditer la clé (utile pour debug local uniquement)
with st.expander("Clé de fonction (si nécessaire) — garde privée"):
    st.write("Si ton Azure Function nécessite une clé, place-la dans `st.secrets['FUNCTION_KEY']` ou dans la variable d'environnement `FUNCTION_KEY`.")
    if FUNCTION_KEY:
        st.write("Clé détectée (masquée):", FUNCTION_KEY[:4] + "..." + FUNCTION_KEY[-4:])
    else:
        st.write("Pas de clé détectée.")

def build_request_url_and_headers(base_url: str, key: str):
    headers = {"Content-Type": "application/json"}
    url = base_url
    if key:
        # On envoie la clé dans l'URL (query param) et aussi en header pour compatibilité
        separator = "&" if "?" in base_url else "?"
        url = f"{base_url}{separator}code={key}"
        headers["x-functions-key"] = key
    return url, headers

# Action button
if st.button("Recommander"):
    user_id_input = (user_id_input or "").strip()
    if user_id_input == "":
        st.error("Merci d'entrer un user_id.")
    else:
        # essayer de parser user_id en int quand possible
        try:
            user_id_val = int(user_id_input)
        except Exception:
            # si ce n'est pas un entier, on envoie en string — la Function gère les deux
            user_id_val = user_id_input

        payload = {"user_id": user_id_val, "top_n": int(top_n)}
        url, headers = build_request_url_and_headers(API_BASE, FUNCTION_KEY)

        st.info(f"Envoi de la requête à : `{url}`")
        with st.spinner("Appel de l'API Azure..."):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=30)
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Erreur réseau lors de l'appel : {e}")
            else:
                # si tout va bien
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        st.error("La réponse n'est pas du JSON valide.")
                        if show_meta:
                            st.text(resp.text)
                    else:
                        st.success("✅ Recommandations Content-Based reçues depuis Azure !")

                        # affichage des recommandations
                        recs = data.get("content_based", [])
                        if not recs:
                            st.warning("Aucune recommandation trouvée pour cet utilisateur.")
                        else:
                            df = pd.DataFrame(recs)
                            # colonnes d'intérêt (afficher seulement celles existantes)
                            cols = [c for c in ("article_id", "similarity", "category_id", "publisher_id", "words_count", "created_at_ts", "user_id") if c in df.columns]
                            st.dataframe(df[cols] if cols else df, use_container_width=True)

                            # message si moins que demandé
                            if len(df) < int(top_n):
                                st.info(f"Seulement {len(df)} recommandation(s) retournée(s) (top demandé: {top_n}).")

                        # afficher meta/diagnostics si demandé
                        if show_meta:
                            st.subheader("Diagnostics retournés par la Function")
                            meta = data.get("meta") or data.get("diagnostics") or {}
                            st.json(meta)

                else:
                    # code d'erreur HTTP
                    st.error(f"Erreur HTTP {resp.status_code}")
                    # essayer d'afficher le body JSON
                    try:
                        err = resp.json()
                        st.json(err)
                    except Exception:
                        st.text(resp.text)
