import logging
import os
import json
import tempfile
import traceback
import azure.functions as func

# URL du blob content
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"

def make_error_response(msg, details=None, status_code=500):
    payload = {"status": "error", "message": msg}
    if details is not None:
        payload["details"] = details
    return func.HttpResponse(body=json.dumps(payload, ensure_ascii=False), status_code=status_code, mimetype="application/json")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Function Recommend (defensive loader) triggered")
    diagnostics = {"phase": "start"}

    # 1) Importer à l'intérieur pour attraper les erreurs d'import au runtime
    try:
        import requests
        import joblib
        import pandas as pd
        import pickle
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Import error")
        diagnostics.update({
            "phase": "imports",
            "import_error": str(e),
            "traceback": tb
        })
        return make_error_response("ImportError dans la Function (voir details).", details=diagnostics, status_code=500)

    # 2) Préparer un chemin temporaire
    tmp_file = os.path.join(tempfile.gettempdir(), "content_defensive.pkl")
    diagnostics["tmp_file"] = tmp_file

    # 3) Fonction de téléchargement simple avec diagnostic
    try:
        diagnostics["phase"] = "download"
        logging.info(f"Tentative de téléchargement depuis {URL_CONTENT} vers {tmp_file}")
        # HEAD pour diagnostiquer
        try:
            head = requests.head(URL_CONTENT, allow_redirects=True, timeout=10)
            diagnostics["head_status_code"] = head.status_code
            diagnostics["head_headers_sample"] = dict(list(head.headers.items())[:10])
        except Exception as e_head:
            diagnostics["head_error"] = str(e_head)

        resp = requests.get(URL_CONTENT, stream=True, timeout=60)
        diagnostics["get_status_code"] = resp.status_code
        if resp.status_code != 200:
            diagnostics["get_reason"] = getattr(resp, "reason", None)
            logging.error("HTTP GET returned non-200")
            return make_error_response("Erreur HTTP lors du téléchargement du blob", details=diagnostics, status_code=500)

        # écrire le fichier
        size = 0
        with open(tmp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                size += len(chunk)
        diagnostics["downloaded_bytes"] = size
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur pendant le download")
        diagnostics.update({"phase": "download_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Exception pendant le téléchargement du blob", details=diagnostics, status_code=500)

    # 4) Tentative de chargement safe (joblib/pickle) avec diagnostics
    try:
        diagnostics["phase"] = "load"
        # premier essai : joblib
        try:
            obj = joblib.load(tmp_file)
            diagnostics["loader_used"] = "joblib"
        except Exception as ej:
            diagnostics["joblib_error"] = str(ej)
            # fallback pickle
            try:
                with open(tmp_file, "rb") as f:
                    obj = pickle.load(f)
                diagnostics["loader_used"] = "pickle"
            except Exception as ep:
                diagnostics["pickle_error"] = str(ep)
                raise RuntimeError({"joblib": str(ej), "pickle": str(ep)})
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur lors du chargement du fichier")
        diagnostics.update({"phase": "load_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Erreur de désérialisation du fichier", details=diagnostics, status_code=500)

    # 5) Si on a un DataFrame, renvoyer un petit résumé ; sinon renvoyer le type
    try:
        diagnostics["phase"] = "summary"
        if isinstance(obj, pd.DataFrame):
            summary = {
                "type": "DataFrame",
                "shape": obj.shape,
                "columns_sample": list(obj.columns[:30]),
                "head_sample": obj.head(3).to_dict(orient="records")
            }
        else:
            summary = {"type": str(type(obj)), "repr": str(obj)[:1000]}
        diagnostics["summary"] = summary
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur pendant la summarisation")
        diagnostics.update({"phase": "summary_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Erreur lors de la création du résumé", details=diagnostics, status_code=500)

    # 6) Tout OK -> renvoyer diagnostics + résumé (200)
    return func.HttpResponse(body=json.dumps({"status": "ok", "diagnostics": diagnostics}, ensure_ascii=False), status_code=200, mimetype="application/json")
