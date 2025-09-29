import logging
import azure.functions as func
import pandas as pd
import joblib
import os
import tempfile

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Test Function triggered (step 1).")

    try:
        # Création d'un petit DataFrame
        df = pd.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30]})

        # Sauvegarde temporaire avec joblib
        tmp_file = os.path.join(tempfile.gettempdir(), "test_df.pkl")
        joblib.dump(df, tmp_file)

        # Rechargement
        df_loaded = joblib.load(tmp_file)

        # Retourne quelques infos
        result = {
            "columns": list(df_loaded.columns),
            "shape": df_loaded.shape,
            "values": df_loaded.to_dict(orient="records")
        }

        return func.HttpResponse(
            body=str(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Erreur dans le test pandas/joblib: {e}")
        return func.HttpResponse(
            body=f"Erreur: {e}",
            status_code=500
        )
