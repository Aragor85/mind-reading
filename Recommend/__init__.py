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

URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
URL_SURPRISE = "https://mindreadingstorage.blob.core.windows.net/surprisesvdmodel/surprise_svd_model_all_3.pkl"

TMP_DIR = "/tmp"
CONTENT_PATH = os.path.join(TMP_DIR, "content.pkl")
SURPRISE_PATH = os.path.join(TMP_DIR, "surprise.pkl")

def download_file(url, dest_path):
    if not os.path.exists(dest_path):
        resp = requests.get(url)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(resp.content)

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.params.get("user_id")
        if not user_id:
            try:
                req_body = req.get_json()
                user_id = req_body.get("user_id")
            except Exception:
                return func.HttpResponse(
                    "Please pass a user_id on the query string or in the request body",
                    status_code=400,
                )

        # Téléchargement modèles
        download_file(URL_CONTENT, CONTENT_PATH)
        download_file(URL_SURPRISE, SURPRISE_PATH)

        # Chargement
        content_df = joblib.load(CONTENT_PATH)
        svd_model = pickle.load(open(SURPRISE_PATH, "rb"))

        # Content-based
        content_recs = (
            content_df[content_df["user_id"] == int(user_id)]
            .sort_values("similarity", ascending=False)
            .head(5)[["article_id", "similarity"]]
            .reset_index(drop=True)
        )

        # Collaborative
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
        # ⚡ renvoyer l'erreur complète au client HTTP
        err_msg = f"🔥 Internal error: {str(e)}\n\n{traceback.format_exc()}"
        return func.HttpResponse(err_msg, status_code=500)
