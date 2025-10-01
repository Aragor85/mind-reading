import logging
import os
import json
import tempfile
import traceback
import azure.functions as func

# URL du blob content (garde ton URL)
URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"

DEFAULT_TOP_N = int(os.environ.get("TOP_N", 5))

def make_error_response(msg, details=None, status_code=500):
    payload = {"status": "error", "message": msg}
    if details is not None:
        payload["details"] = details
    return func.HttpResponse(body=json.dumps(payload, ensure_ascii=False), status_code=status_code, mimetype="application/json")

def _safe_load(path):
    # charge joblib ou pickle
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        try:
            import pickle
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            raise

def _normalize_recs_from_obj(obj, user_id, top_n):
    """
    Retourne une liste de recommandations normalisées :
    [{'article_id':..., 'similarity':..., ...}, ...]
    Gère DataFrame, dict(user->list), dict global, listes, etc.
    """
    import pandas as pd
    recs = []

    # CAS 1 : DataFrame
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
        # ---- cas où df contient une colonne user_id ----
        if 'user_id' in df.columns:
            df_user = df[df['user_id'].astype(str) == str(user_id)]
            if not df_user.empty:
                if 'similarity' in df_user.columns:
                    df_user = df_user.sort_values(by='similarity', ascending=False)
                recs = df_user.head(top_n).to_dict(orient='records')
                return recs
        # ---- cas où df est déjà une table de (article_id, similarity) ----
        if 'article_id' in df.columns and 'similarity' in df.columns:
            df_sorted = df.sort_values(by='similarity', ascending=False)
            recs = df_sorted.head(top_n).to_dict(orient='records')
            return recs

    # CAS 2 : dict mapping user_id -> list(...)
    if isinstance(obj, dict):
        # clé user as str or same type
        for key in (str(user_id), user_id):
            if key in obj:
                items = obj[key]
                # normaliser items
                normalized = []
                for it in items[:top_n]:
                    if isinstance(it, dict):
                        normalized.append(it)
                    elif isinstance(it, (list, tuple)) and len(it) >= 2:
                        normalized.append({'article_id': it[0], 'similarity': float(it[1])})
                    else:
                        normalized.append({'article_id': it})
                return normalized
        # sinon si dict contient global list under some key (e.g. 'global'/'top')
        for guess in ('global', 'top', 'popular', 'recommendations'):
            if guess in obj and isinstance(obj[guess], (list,tuple)):
                items = obj[guess][:top_n]
                normalized = []
                for it in items:
                    if isinstance(it, dict):
                        normalized.append(it)
                    elif isinstance(it, (list,tuple)) and len(it) >= 2:
                        normalized.append({'article_id': it[0], 'similarity': float(it[1])})
                    else:
                        normalized.append({'article_id': it})
                return normalized

    # CAS 3 : list-like top-level
    if isinstance(obj, (list, tuple)):
        normalized = []
        for it in obj[:top_n]:
            if isinstance(it, dict):
                normalized.append(it)
            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                normalized.append({'article_id': it[0], 'similarity': float(it[1])})
            else:
                normalized.append({'article_id': it})
        return normalized

    # fallback : empty
    return []

def get_global_top(obj, top_n):
    """fallback: try to get global top items from object"""
    import pandas as pd
    if isinstance(obj, pd.DataFrame):
        if 'similarity' in obj.columns and 'article_id' in obj.columns:
            return obj.sort_values('similarity', ascending=False).head(top_n).to_dict(orient='records')
        if 'popularity' in obj.columns and 'article_id' in obj.columns:
            return obj.sort_values('popularity', ascending=False).head(top_n).to_dict(orient='records')
    if isinstance(obj, dict):
        for k in ('global','top','popular','recommendations'):
            if k in obj and isinstance(obj[k], list):
                return _normalize_recs_from_obj({k: obj[k]}, None, top_n)
    if isinstance(obj, (list,tuple)):
        return _normalize_recs_from_obj(obj, None, top_n)
    return []

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Function Recommend triggered")
    diagnostics = {"phase": "start"}

    # imports runtime
    try:
        import requests
        import joblib
        import pandas as pd
        import pickle
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Import error")
        diagnostics.update({"phase": "imports", "import_error": str(e), "traceback": tb})
        return make_error_response("ImportError dans la Function (voir details).", details=diagnostics, status_code=500)

    # parse request
    try:
        body = req.get_json(silent=True) or {}
    except Exception:
        body = {}
    user_id = body.get("user_id") or req.params.get("user_id") if hasattr(req, "params") else body.get("user_id")
    try:
        top_n = int(body.get("top_n", DEFAULT_TOP_N))
    except Exception:
        top_n = DEFAULT_TOP_N

    if not user_id:
        return make_error_response("Paramètre user_id requis (POST JSON ou query string).", details={"received_body": body}, status_code=400)

    # download blob to tmp file
    tmp_file = os.path.join(tempfile.gettempdir(), "recommend_content.pkl")
    diagnostics["tmp_file"] = tmp_file
    try:
        # attempt HEAD for diagnostics
        try:
            head = requests.head(URL_CONTENT, allow_redirects=True, timeout=10)
            diagnostics["head_status_code"] = head.status_code
        except Exception as e_head:
            diagnostics["head_error"] = str(e_head)

        resp = requests.get(URL_CONTENT, stream=True, timeout=60)
        diagnostics["get_status_code"] = resp.status_code
        if resp.status_code != 200:
            return make_error_response("Erreur HTTP lors du téléchargement du blob", details=diagnostics, status_code=500)

        with open(tmp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
        diagnostics["downloaded_bytes"] = os.path.getsize(tmp_file)
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur pendant le download")
        diagnostics.update({"phase": "download_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Exception pendant le téléchargement du blob", details=diagnostics, status_code=500)

    # load object
    try:
        diagnostics["phase"] = "load"
        obj = _safe_load(tmp_file)
        diagnostics["loaded_type"] = str(type(obj))
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur lors du chargement du fichier")
        diagnostics.update({"phase": "load_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Erreur de désérialisation du fichier", details=diagnostics, status_code=500)

    # build recommendations
    try:
        diagnostics["phase"] = "recommend"
        recs = _normalize_recs_from_obj(obj, user_id, top_n)
        diagnostics["found_recs"] = len(recs)

        # fallback: if fewer than requested, try global top
        if len(recs) < top_n:
            fallback = get_global_top(obj, top_n)
            # merge preserving uniqueness by article_id
            seen = set(r.get('article_id') for r in recs if r.get('article_id') is not None)
            for item in fallback:
                aid = item.get('article_id')
                if aid not in seen:
                    recs.append(item)
                    seen.add(aid)
                if len(recs) >= top_n:
                    break
            diagnostics["after_fallback_recs"] = len(recs)

        # trim to top_n
        recs = recs[:top_n]
    except Exception as e:
        tb = traceback.format_exc()
        logging.exception("Erreur pendant la génération des recommandations")
        diagnostics.update({"phase": "recommend_exception", "exception": str(e), "traceback": tb})
        return make_error_response("Erreur lors du calcul des recommandations", details=diagnostics, status_code=500)

    # build response
    payload = {
        "status": "ok",
        "user_id": user_id,
        "content_based": recs,
        "meta": diagnostics
    }
    return func.HttpResponse(body=json.dumps(payload, ensure_ascii=False), status_code=200, mimetype="application/json")
