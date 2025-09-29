import logging
import azure.functions as func
import pandas as pd
import joblib
import os
import requests
import tempfile
import traceback
import json
import pickle
from io import BytesIO

URL_CONTENT = "https://mindreadingstorage.blob.core.windows.net/similaritycosinussurembeddingspca40/recommendations_vectorized.pkl"
#URL_SURPRISE = "..."  # si besoin plus tard

def download_file_verbose(url, dest_path):
    logging.info(f"➡️ Check file at: {dest_path}")
    if os.path.exists(dest_path):
        stat = os.stat(dest_path)
        logging.info(f"⚡ File already exists: size={stat.st_size} bytes, mtime={stat.st_mtime}")
        return {"status": "cached", "size": stat.st_size}

    # HEAD first (in case CORS / redirect / auth issues)
    try:
        head = requests.head(url, allow_redirects=True, timeout=15)
        logging.info(f"HTTP HEAD: status={head.status_code}, headers={dict(head.headers)}")
    except Exception as e:
        logging.warning(f"HEAD failed: {e}")

    try:
        resp = requests.get(url, stream=True, timeout=60)
        logging.info(f"HTTP GET: status={resp.status_code}")
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"GET request failed: {e}")
        raise

    total_written = 0
    try:
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                total_written += len(chunk)
        logging.info(f"✅ Saved to {dest_path} ({total_written} bytes)")
    except Exception as e:
        logging.error(f"Failed writing file: {e}")
        raise

    return {"status": "downloaded", "size": total_written, "resp_headers": dict(resp.headers)}

def safe_preview_file(path, n=512):
    try:
        with open(path, "rb") as f:
            data = f.read(n)
        # show as escaped repr (avoid binary explosion)
        return repr(data[:n])
    except Exception as e:
        return f"<cannot read preview: {e}>"

def try_joblib_then_pickle(path):
    errors = {}
    # joblib
    try:
        obj = joblib.load(path)
        return {"obj": obj, "loader": "joblib", "error": None}
    except Exception as e_joblib:
        errors["joblib"] = str(e_joblib)
        logging.warning(f"joblib.load failed: {e_joblib}")

    # try pickle
    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)
        return {"obj": obj, "loader": "pickle", "error": None}
    except Exception as e_pickle:
        errors["pickle"] = str(e_pickle)
        logging.warning(f"pickle.load failed: {e_pickle}")

    return {"obj": None, "loader": None, "error": errors}

def dataframe_summary(df):
    try:
        if isinstance(df, pd.DataFrame):
            return {
                "type": "DataFrame",
                "shape": df.shape,
                "columns": list(df.columns[:50]),
                "head": df.head(5).to_dict(orient="records")
            }
        else:
            return {"type": str(type(df)), "repr": str(df)[:500]}
    except Exception as e:
        logging.error(f"Error creating summary: {e}")
        return {"type": "error", "error": str(e)}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("🚀 Function Recommend triggered - verbose debug mode")
    tmp_file = os.path.join(tempfile.gettempdir(), "content_verbose.pkl")
    diagnostics = {"tmp_file": tmp_file}

    try:
        # 1) download with diagnostics
        dl_info = download_file_verbose(URL_CONTENT, tmp_file)
        diagnostics["download"] = dl_info

        # 2) file preview + stat
        try:
            stat = os.stat(tmp_file)
            diagnostics["file_stat"] = {"size": stat.st_size, "mtime": stat.st_mtime}
            diagnostics["file_preview"] = safe_preview_file(tmp_file, n=1024)
        except Exception as e:
            diagnostics["file_stat_error"] = str(e)

        # 3) try load
        load_result = try_joblib_then_pickle(tmp_file)
        diagnostics["load_attempt"] = {"loader": load_result.get("loader"), "error": load_result.get("error")}

        if load_result.get("obj") is None:
            # failed to load
            raise RuntimeError(f"Failed to deserialize file. loaders_errors={load_result.get('error')}")

        obj = load_result["obj"]

        # 4) summary
        diagnostics["object_summary"] = dataframe_summary(obj)

        # Return success with diagnostics (safe)
        return func.HttpResponse(
            body=json.dumps({"status": "ok", "diagnostics": diagnostics}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        tb = traceback.format_exc()
        logging.error("❌ Exception during function execution")
        logging.error(tb)
        diagnostics["exception"] = str(e)
        diagnostics["traceback"] = tb
        # include last 1KB of file if exists for debugging
        try:
            if os.path.exists(tmp_file):
                diagnostics["file_tail_preview"] = safe_preview_file(tmp_file, n=1024)
        except Exception as ex2:
            diagnostics["file_preview_error"] = str(ex2)

        # Return detailed JSON so GH Actions sees the message
        return func.HttpResponse(
            body=json.dumps({"status": "error", "diagnostics": diagnostics}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json"
        )
