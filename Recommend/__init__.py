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

# URLs vers les blobs
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
URL_SURPRISE = "https://mindreadingstorage.blob.core.windows.net/surprisesvdmodel/surprise_svd_model_all_3.pkl"

# Répertoire temporaire dans Azure Functions pour stocker les fichiers
TMP_DIR = "/tmp"
CONTENT_PATH = os.path.join(TMP_DIR, "content.pkl")
SURPRISE_PATH = os.path.join(TMP_DIR, "surprise.pkl")


def download_file(url, dest_path):
    """Télécharger un fichier depuis un blob vers /tmp"""
    if not os.path.exists(dest_path):
        logging.info(f"Début téléchargement depuis {url} ...")
        try:
            resp = requests.get(url, stream=True, timeout=30)
            logging.info(f"HTTP GET {url} status: {resp.status_code}")
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"✅ Fichier sauvegardé dans {dest_path}")
        except Exception as e:
            logging.error(f"Erreur lors du téléchargement de {url}: {e}")
            raise
    else:
        logging.info(f"⚡ Fichier déjà en cache : {dest_path}")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Mind Reading recommender triggered (cloud mode).")

    # === Récupérer user_id ===
    user_id = req.params.get("user_id")
    if not user_id:
        try:
            req_body = req.get_json()
            user_id = req_body.get("user_id")
        except ValueError:
            pass

    if not user_id:
        logging.warning("Aucun user_id fourni dans la requête")
        return func.HttpResponse(
            "Please pass a user_id on the query string or in the request body",
            status_code=400,
        )

    try:
        # === 1. Télécharger les modèles si nécessaire ===
        download_file(URL_CONTENT, CONTENT_PATH)
        download_file(URL_SURPRISE, SURPRISE_PATH)

        # === 2. Charger les modèles ===
        logging.info("Chargement du content_df ...")
        try:
            content_df = joblib.load(CONTENT_PATH)
            logging.info(f"content_df loaded: type={type(content_df)}, shape={getattr(content_df, 'shape', None)}")
        except Exception as ex:
            logging.error(f"Échec du chargement content_df avec joblib: {ex}")
            raise

        logging.info("Chargement du svd_model ...")
        svd_model = None
        try:
            svd_model = joblib.load(SURPRISE_PATH)
            logging.info(f"svd_model loaded via joblib: type={type(svd_model)}")
        except Exception as ex_joblib:
            logging.warning(f"joblib.load failed for svd_model: {ex_joblib} — fallback to pickle.load")
            try:
                with open(SURPRISE_PATH, "rb") as f:
                    svd_model = pickle.load(f)
                logging.info(f"svd_model loaded via pickle: type={type(svd_model)}")
            except Exception as ex_pickle:
                logging.error(f"Failed to load svd_model: joblib_err={ex_joblib}, pickle_err={ex_pickle}")
                raise

        logging.info("✅ Modèles chargés depuis le blob")

        # === 3. Recommandations content-based ===
        logging.info(f"Génération recommandations content-based pour user_id={user_id}")
        content_recs = (
            content_df[content_df["user_id"] == int(user_id)]
            .sort_values("similarity", ascending=False)
            .head(5)[["article_id", "similarity"]]
            .reset_index(drop=True)
        )
        logging.info(f"content-based recommendations:\n{content_recs}")

        # === 4. Recommandations collaborative (Surprise) ===
        logging.info(f"Génération recommandations collaborative pour user_id={user_id}")
        all_items = content_df["article_id"].unique()[:200]
        predictions = []
        for iid in all_items:
            try:
                pred = svd_model.predict(int(user_id), int(iid))
                predictions.append((iid, pred.est))
            except Exception as e_pred:
                logging.error(f"Erreur prediction item {iid}: {e_pred}")

        surprise_recs = (
            pd.DataFrame(predictions, columns=["article_id", "pred_score"])
            .sort_values("pred_score", ascending=False)
            .head(5)
            .reset_index(drop=True)
        )
        logging.info(f"surprise recommendations:\n{surprise_recs}")

        # === 5. Réponse JSON ===
        result = {
            "user_id": user_id,
            "content_based": content_recs.to_dict(orient="records"),
            "surprise": surprise_recs.to_dict(orient="records"),
        }

        logging.info("Réponse générée avec succès ✅")
        return func.HttpResponse(
            body=json.dumps(result),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Erreur dans la Function: {e}\n{tb}")
        return func.HttpResponse(
            body=json.dumps({"error": str(e), "traceback": tb}),
            status_code=500,
            mimetype="application/json",
        )
