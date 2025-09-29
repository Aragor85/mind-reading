import logging
import joblib
import os
import pandas as pd
import requests
import json

# URL vers le blob content
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"

# Répertoire temporaire dans Azure Functions
TMP_DIR = "/tmp"
CONTENT_PATH = os.path.join(TMP_DIR, "content.pkl")


def download_file(url, dest_path):
    """Télécharger un fichier depuis le blob vers /tmp"""
    if not os.path.exists(dest_path):
        logging.info(f"Début téléchargement depuis {url} ...")
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"✅ Fichier sauvegardé dans {dest_path}")
    else:
        logging.info(f"⚡ Fichier déjà en cache : {dest_path}")


def main(req) -> dict:
    logging.info("Content-only recommender triggered.")

    # === Récupérer user_id ===
    user_id = req.params.get("user_id")
    if not user_id:
        try:
            req_body = req.get_json()
            user_id = req_body.get("user_id")
        except Exception:
            pass

    if not user_id:
        return {
            "status": 400,
            "body": "Please pass a user_id on the query string or in the request body"
        }

    try:
        # Télécharger le fichier content
        download_file(URL_CONTENT, CONTENT_PATH)

        # Charger le dataframe content
        content_df = joblib.load(CONTENT_PATH)
        logging.info(f"content_df loaded: type={type(content_df)}, shape={getattr(content_df, 'shape', None)}")

        # Filtrer recommandations content-based
        user_id_int = int(user_id)
        content_recs = (
            content_df[content_df["user_id"] == user_id_int]
            .sort_values("similarity", ascending=False)
            .head(5)[["article_id", "similarity"]]
            .reset_index(drop=True)
        )

        logging.info(f"content-based recommendations:\n{content_recs}")

        # Réponse JSON
        result = {
            "user_id": user_id,
            "content_based": content_recs.to_dict(orient="records")
        }

        return {
            "status": 200,
            "body": json.dumps(result),
            "mimetype": "application/json"
        }

    except Exception as e:
        logging.error(f"Erreur dans la Function: {e}")
        return {
            "status": 500,
            "body": json.dumps({"error": str(e)}),
            "mimetype": "application/json"
        }
