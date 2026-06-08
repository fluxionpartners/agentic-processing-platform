import base64
import binascii
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

CONTAINER_NAME = os.getenv("W2_CONTAINER_NAME", "raw-w2")
SERVICE_BUS_QUEUE = os.getenv("W2_SERVICEBUS_QUEUE_NAME", "w2-ingestion-queue")
STORAGE_CONNECTION = os.getenv("W2_STORAGE_CONNECTION_STRING")
SERVICE_BUS_CONNECTION = os.getenv("W2_SERVICEBUS_CONNECTION_STRING")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_blob_name(payload: Dict[str, Any]) -> str:
    tenant_id = payload["tenantId"].strip()
    taxpayer_id = payload["taxpayerId"].strip()
    document_name = payload["documentName"].strip()
    tax_year = payload.get("taxYear") or str(utc_now().year)
    safe_name = document_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"{tenant_id}/{taxpayer_id}/{tax_year}/{timestamp}_{safe_name}"


def validate_payload(payload: Dict[str, Any]) -> Optional[str]:
    required_fields = ["tenantId", "taxpayerId", "documentName", "documentBase64"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


def upload_blob(blob_name: str, document_bytes: bytes) -> str:
    from azure.storage.blob import BlobClient

    blob_client = BlobClient.from_connection_string(
        conn_str=STORAGE_CONNECTION,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
    )
    blob_client.upload_blob(document_bytes, overwrite=False)
    return blob_client.url


def publish_ingestion_event(payload: Dict[str, Any], blob_uri: str) -> str:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    correlation_id = payload.get("correlationId") or str(utc_now().timestamp())
    event_payload = {
        "schemaVersion": "1.0",
        "eventType": "W2DocumentUploaded",
        "occurredAt": utc_now().isoformat(),
        "tenantId": payload["tenantId"],
        "taxpayerId": payload["taxpayerId"],
        "documentName": payload["documentName"],
        "blobUri": blob_uri,
        "taxYear": payload.get("taxYear"),
        "correlationId": correlation_id,
    }

    with ServiceBusClient.from_connection_string(conn_str=SERVICE_BUS_CONNECTION) as client:
        sender = client.get_queue_sender(queue_name=SERVICE_BUS_QUEUE)
        with sender:
            message = ServiceBusMessage(json.dumps(event_payload), subject="W2DocumentUploaded")
            sender.send_messages(message)
            return message.message_id


def should_publish_ingestion_event(payload: Dict[str, Any]) -> bool:
    execution_mode = str(payload.get("executionMode") or "direct").strip().lower()
    return execution_mode not in {"foundry-agent", "agent", "supervisor-agent"}


def main(req):
    import azure.functions as func

    if STORAGE_CONNECTION is None or SERVICE_BUS_CONNECTION is None:
        logging.error("Missing W-2 intake configuration values.")
        return func.HttpResponse(
            "Server configuration is incomplete. Check environment variables.",
            status_code=500,
        )

    try:
        request_body = req.get_body().decode("utf-8")
        payload = json.loads(request_body)
    except ValueError:
        logging.warning("Invalid JSON payload.")
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    validation_error = validate_payload(payload)
    if validation_error:
        logging.warning("Validation failed: %s", validation_error)
        return func.HttpResponse(validation_error, status_code=400)

    try:
        document_bytes = base64.b64decode(payload["documentBase64"], validate=True)
    except (binascii.Error, ValueError):
        logging.warning("documentBase64 was invalid base64 data.")
        return func.HttpResponse("documentBase64 must be valid base64.", status_code=400)

    blob_name = build_blob_name(payload)
    try:
        blob_uri = upload_blob(blob_name, document_bytes)
        message_id = publish_ingestion_event(payload, blob_uri) if should_publish_ingestion_event(payload) else ""
    except Exception as exc:
        logging.exception("Ingestion failed.")
        return func.HttpResponse(f"Failed to ingest document: {str(exc)}", status_code=500)

    response_body = {
        "status": "accepted",
        "blobUri": blob_uri,
        "messageId": message_id,
        "correlationId": payload.get("correlationId"),
        "executionMode": payload.get("executionMode") or "direct",
    }

    logging.info("W-2 ingestion accepted: %s", blob_uri)
    return func.HttpResponse(json.dumps(response_body), status_code=202, mimetype="application/json")
