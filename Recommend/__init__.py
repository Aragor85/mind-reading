import logging
import pickle
import joblib
import numpy as np
import azure.functions as func
import os
import pandas as pd
import requests
import traceback
import json

# URLs vers tes blobs
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
URL_SURPRISE = "https://mindreadingstorage.blob.core.windows.net/surprisesvdmodel/surprise_svd_model_all_3.pkl"

# Répertoire temporaire dans Azure Functions pour stocker blob 
TMP_DIR = "/tmp"
CONTENT_PATH = os.path.join(TMP_DIR, "content.pkl")
SURPRISE_PATH = os.path.join(TMP_DIR, "surprise.pkl")


def download_file(url, dest_path):
    """Télécharger un fichier depuis un blob vers /tmp"""
    if not os.path.exists(dest_path):
        logging.info(f"Téléchargement du modèle depuis {url} ...")
        resp = requests.get(url)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        logging.info(f"✅ Fichier sauvegardé dans {dest_path}")
    else:
        logging.info(f"⚡ Fichier déjà en cache : {dest_path}")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Mind Reading recommender triggered (cloud mode).")

    user_id = req.params.get("user_id")
    if not user_id:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            user_id = req_body.get("user_id")

    if not user_id:
        return func.HttpResponse(
            "Please pass a user_id on the query string or in the request body",
            status_code=400,
        )

    try:
        # === 1. Télécharger les modèles si nécessaire ===
        download_file(URL_CONTENT, CONTENT_PATH)
        download_file(URL_SURPRISE, SURPRISE_PATH)

        # === 2. Charger les modèles ===
        content_df = joblib.load(CONTENT_PATH)  # DataFrame
        svd_model = pickle.load(open(SURPRISE_PATH, "rb"))  # SVD

        logging.info("✅ Modèles chargés depuis le blob")

        # === 3. Recommandations content-based ===
        content_recs = (
            content_df[content_df["user_id"] == int(user_id)]
            .sort_values("similarity", ascending=False)
            .head(5)[["article_id", "similarity"]]
            .reset_index(drop=True)
        )

        # === 4. Recommandations collaborative (Surprise) ===
        all_items = content_df["article_id"].unique()[:200]
        predictions = []
        for iid in all_items:
            pred = svd_model.predict(int(user_id), int(iid))
            predictions.append((iid, pred.est))

        surprise_recs = (
            pd.DataFrame(predictions, columns=["article_id", "pred_score"])
            .sort_values("pred_score", ascending=False)
            .head(5)
            .reset_index(drop=True)
        )

        # === 5. Réponse JSON ===
        result = {
            "user_id": user_id,
            "content_based": content_recs.to_dict(orient="records"),
            "surprise": surprise_recs.to_dict(orient="records"),
        }

        return func.HttpResponse(
            body=json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Erreur dans la Function: {e}\n{tb}")
        return func.HttpResponse(
            body=json.dumps({"error": str(e), "traceback": tb}),
            status_code=500,
            mimetype="application/json"
        )
