import logging
import os
import json
import tempfile
import traceback
import azure.functions as func

URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
DEFAULT_TOP_N = int(os.environ.get("TOP_N", 5))

def make_error_response(msg, details=None, status_code=500):
    payload = {"status": "error", "message": msg}
    if details is not None:
        payload["details"] = details
    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json"
    )

def _safe_load(path):
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

def _get_recs_from_df(df, user_id, top_n):
    try:
        if "user_id" in df.columns:
            try:
                user_id_int = int(user_id)
                mask = df["user_id"].astype("Int64") == user_id_int
            except Exception:
                mask = df["user_id"].astype(str) == str(user_id)
            df_user = df[mask]
            if not df_user.empty:
                if "similarity" in df_user.columns:
                    df_user = df_user.sort_values(by="similarity", ascending=False)
                elif "created_at_ts" in df_user.columns:
                    df_user = df_user.sort_values(by="created_at_ts", ascending=False)
                return df_user.head(top_n).to_dict(orient="records")

        if "article_id" in df.columns and "similarity" in df.columns:
            df_sorted = df.sort_values(by="similarity", ascending=False)
            return df_sorted.head(top_n).to_dict(orient="records")
    except Exception:
        logging.exception("Erreur dans _get_recs_from_df")
    return []

def get_global_top(df, top_n):
    if "similarity" in df.columns and "article_id" in df.columns:
        return df.sort_values("similarity", ascending=False).head(top_n).to_dict(orient="records")
    if "created_at_ts" in df.columns and "article_id" in df.columns:
        return df.sort_values("created_at_ts", ascending=False).head(top_n).to_dict(orient="records")
    return []

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Function Recommend triggered")
    diagnostics = {"phase": "start"}

    try:
        import requests
        import pandas as pd
    except Exception as e:
        tb = traceback.format_exc()
        diagnostics.update({"phase": "imports", "error": str(e), "traceback": tb})
        return make_error_response("ImportError dans la Function.", details=diagnostics)

    # --- Récupération paramètres ---
    user_id = None
    top_n = DEFAULT_TOP_N
    body = {}

    # Query string d’abord
    if req.params.get("user_id"):
        user_id = req.params.get("user_id")
        if req.params.get("top_n"):
            top_n = int(req.params.get("top_n"))

    # Sinon essayer body brut
    if not user_id:
        try:
            raw_body = req.get_body().decode("utf-8")
            diagnostics["raw_body"] = raw_body
            if raw_body:
                body = json.loads(raw_body)
                user_id = body.get("user_id")
                top_n = int(body.get("top_n", top_n))
        except Exception as e:
            diagnostics["body_error"] = str(e)

    if not user_id:
        return make_error_response(
            "Paramètre user_id requis (POST JSON ou query string).",
            details={"received_body": body, "diagnostics": diagnostics},
            status_code=400,
        )

    diagnostics["received_user_id"] = user_id
    diagnostics["requested_top_n"] = top_n

    # --- Télécharger et charger le blob ---
    tmp_file = os.path.join(tempfile.gettempdir(), "recommend_content.pkl")
    try:
        resp = requests.get(URL_CONTENT, stream=True, timeout=60)
        diagnostics["get_status_code"] = resp.status_code
        if resp.status_code != 200:
            return make_error_response("Erreur HTTP lors du téléchargement du blob", details=diagnostics)
        with open(tmp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        diagnostics["downloaded_bytes"] = os.path.getsize(tmp_file)
        obj = _safe_load(tmp_file)
        diagnostics["loaded_type"] = str(type(obj))
    except Exception as e:
        tb = traceback.format_exc()
        diagnostics.update({"phase": "download_or_load", "error": str(e), "traceback": tb})
        return make_error_response("Erreur chargement blob", details=diagnostics)

    # --- Générer recommandations ---
    try:
        recs = []
        if hasattr(obj, "head") and hasattr(obj, "columns"):
            recs = _get_recs_from_df(obj, user_id, top_n)
            diagnostics["df_shape"] = getattr(obj, "shape", None)
        elif isinstance(obj, dict):
            key = str(user_id)
            if key in obj:
                items = obj[key]
                for it in items[:top_n]:
                    if isinstance(it, dict):
                        recs.append(it)
                    elif isinstance(it, (list, tuple)) and len(it) >= 2:
                        recs.append({"article_id": it[0], "similarity": float(it[1])})
                    else:
                        recs.append({"article_id": it})
        if len(recs) < top_n:
            recs += get_global_top(obj, top_n - len(recs))
        recs = recs[:top_n]
        diagnostics["found_recs"] = len(recs)
    except Exception as e:
        tb = traceback.format_exc()
        diagnostics.update({"phase": "recommend", "error": str(e), "traceback": tb})
        return make_error_response("Erreur génération recommandations", details=diagnostics)

    payload = {
        "status": "ok",
        "user_id": user_id,
        "content_based": recs,
        "meta": diagnostics,
    }
    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
