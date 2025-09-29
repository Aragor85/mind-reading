import logging
import azure.functions as func
import json

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Healthcheck endpoint triggered")
    return func.HttpResponse(
        body=json.dumps({"message": "Function deployed successfully!"}),
        status_code=200,
        mimetype="application/json"
    )
