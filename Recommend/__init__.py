import logging
import azure.functions as func
import pandas as pd
import joblib
import os
import requests
import tempfile

# URL de ton blob
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"

def download_file(url, dest_path):
    """Télécharger un fichier si pas déjà présent"""
    if not os.path.exists(dest_path):
        logging.info(f"Téléchargement depuis {url} ...")
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        logging.info(f"✅ Fichier sauvegardé dans {dest_path}")
    else:
        logging.info(f"⚡ Fichier déjà présent : {dest_path}")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Test Function triggered (step 2: blob load).")

    try:
        tmp_file = os.path.join(tempfile.gettempdir(), "content.pkl")

        # Télécharger le fichier
        download_file(URL_CONTENT, tmp_file)

        # Charger le DataFrame
        df = joblib.load(tmp_file)

        # Préparer une petite réponse
        result = {
            "columns": list(df.columns),
            "shape": df.shape,
            "head": df.head(5).to_dict(orient="records")
        }

        return func.HttpResponse(
            body=str(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Erreur dans le test blob content: {e}")
        return func.HttpResponse(
            body=f"Erreur: {e}",
            status_code=500
        )
