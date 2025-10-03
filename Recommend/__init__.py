import logging
import os
import json
import tempfile
import azure.functions as func

URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
URL_SURPRISE = "https://mindreadingstorage.blob.core.windows.net/surprisesvdmodel/surprise_svd_model_all_3.pkl"

DEFAULT_TOP_N = int(os.environ.get("TOP_N", 5))


def make_error_response(msg, details=None, status_code=500):
    payload = {"status": "error", "message": msg}
    if details:
        payload["details"] = details
    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json"
    )


def _safe_load(path):
    """Charger un modèle avec joblib si dispo, sinon fallback vers pickle."""
    try:
        try:
            import joblib
            logging.info(f"Chargement avec joblib: {path}")
            return joblib.load(path)
        except ImportError:
            logging.warning("Joblib non disponible, fallback vers pickle")
            import pickle
            with open(path, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logging.error(f"Erreur lors du chargement du modèle {path} : {e}")
        raise


def _get_recs_from_df(df, user_id, top_n, score_col="similarity"):
    """Filtrer un DataFrame (content-based)."""
    try:
        if "user_id" in df.columns:
            try:
                user_id_int = int(user_id)
                mask = df["user_id"].astype("Int64") == user_id_int
            except Exception:
                mask = df["user_id"].astype(str) == str(user_id)
            df_user = df[mask]
            if not df_user.empty:
                if score_col in df_user.columns:
                    df_user = df_user.sort_values(by=score_col, ascending=False)
                return df_user.head(top_n).to_dict(orient="records")
    except Exception:
        logging.exception("Erreur dans _get_recs_from_df")
    return []


def _predict_topn_with_surprise_model(model, item_list, user_id, top_n, raw=False):
    """Top-N predictions avec Surprise model."""
    preds = []
    uid = str(user_id)
    for item in item_list:
        try:
            iid = str(item)
            r = model.predict(uid, iid)
            est = getattr(r, "est", None)
            if est is not None:
                preds.append((iid, float(est)))
        except Exception:
            continue
    preds.sort(key=lambda x: x[1], reverse=True)
    return [{"article_id": iid, "estimated_rating": est} for iid, est in preds[:top_n]]


def _get_surprise_recs(obj, user_id, top_n):
    """Détecter et générer des recs avec un modèle Surprise."""
    # dict avec recs déjà calculées
    if isinstance(obj, dict) and "recommendations" in obj:
        return obj["recommendations"][:top_n]

    # dict avec model + items
    if isinstance(obj, dict) and "model" in obj:
        model = obj["model"]
        items = obj.get("items") or obj.get("all_items") or []
        return _predict_topn_with_surprise_model(model, items, user_id, top_n)

    # modèle surprise direct
    if hasattr(obj, "trainset"):
        try:
            item_raw_ids = [obj.trainset.to_raw_iid(i) for i in range(obj.trainset.n_items)]
            return _predict_topn_with_surprise_model(obj, item_raw_ids, user_id, top_n, raw=True)
        except Exception:
            logging.exception("Erreur lors de la génération de recs avec Surprise")
            pass

    return []


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Function Recommend triggered")

    try:
        import requests
        import pandas as pd
    except Exception as e:
        return make_error_response("Erreur d'import", str(e))

    # --- Params ---
    user_id = req.params.get("user_id") or None
    top_n = int(req.params.get("top_n") or DEFAULT_TOP_N)

    if not user_id:
        try:
            body = json.loads(req.get_body().decode("utf-8"))
            user_id = body.get("user_id")
            top_n = int(body.get("top_n", top_n))
        except Exception:
            pass

    if not user_id:
        return make_error_response("Paramètre user_id manquant", status_code=400)

    recs_content, recs_surprise = [], []

    # Charger Content-Based
    try:
        logging.info("Téléchargement du modèle Content-Based depuis Blob...")
        tmp_content = os.path.join(tempfile.gettempdir(), "content.pkl")
        resp = requests.get(URL_CONTENT, stream=True, timeout=60)
        with open(tmp_content, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        logging.info("Chargement du modèle Content-Based terminé.")
        df_content = _safe_load(tmp_content)
        recs_content = _get_recs_from_df(df_content, user_id, top_n, score_col="similarity")
    except Exception as e:
        logging.error(f"Erreur Content: {e}")

    # Charger Surprise
    try:
        logging.info("Téléchargement du modèle Surprise SVD depuis Blob...")
        tmp_surprise = os.path.join(tempfile.gettempdir(), "surprise.pkl")
        resp = requests.get(URL_SURPRISE, stream=True, timeout=60)
        with open(tmp_surprise, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        logging.info("Chargement du modèle Surprise terminé.")
        obj_surprise = _safe_load(tmp_surprise)
        recs_surprise = _get_surprise_recs(obj_surprise, user_id, top_n)
    except Exception as e:
        logging.error(f"Erreur Surprise: {e}")

    payload = {
        "status": "ok",
        "user_id": user_id,
        "content_based": recs_content,
        "surprise_svd": recs_surprise,
    }

    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False),
        status_code=200,
        mimetype="application/json"
    )
