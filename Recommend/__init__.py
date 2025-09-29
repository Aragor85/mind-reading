import logging
import azure.functions as func
import pandas as pd
import joblib
import os
import requests
import tempfile
import traceback

URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"

def download_file(url, dest_path):
    logging.info(f"➡️ Download check: {dest_path}")
    if not os.path.exists(dest_path):
        logging.info(f"⬇️ Downloading from {url} ...")
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        logging.info(f"✅ File saved at {dest_path}")
    else:
        logging.info(f"⚡ File already present: {dest_path}")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("🚀 Azure Function triggered (step 2 blob load)")

    try:
        tmp_file = os.path.join(tempfile.gettempdir(), "content.pkl")
        logging.info(f"📂 Temp path: {tmp_file}")

        # Step 1 : Download
        download_file(URL_CONTENT, tmp_file)

        # Step 2 : Load with joblib
        logging.info("📦 Loading pickle file with joblib...")
        df = joblib.load(tmp_file)
        logging.info(f"✅ Loaded successfully. Type: {type(df)}")

        # Step 3 : Convert to JSON (safe)
        if isinstance(df, pd.DataFrame):
            result = {
                "columns": list(df.columns),
                "shape": df.shape,
                "head": df.head(3).to_dict(orient="records")
            }
        else:
            result = {
                "type": str(type(df)),
                "repr": str(df)[:500]  # éviter un dump énorme
            }

        return func.HttpResponse(
            body=str(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error("❌ ERROR in function execution")
        logging.error(traceback.format_exc())  # stacktrace complet dans logs Azure
        return func.HttpResponse(
            body=f"Erreur: {repr(e)}",
            status_code=500
        )
