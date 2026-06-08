import logging

import azure.functions as func

from foundry_tools_app import (
    execute_tool,
    get_pipeline_status,
    invoke_foundry_supervisor_agent,
    json_response,
    parse_json_body,
    process_service_bus_event,
)


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _handle_tool_request(req: func.HttpRequest, route_name: str) -> func.HttpResponse:
    payload, error = parse_json_body(req)
    if error:
        return json_response(func, {"error": "invalid_request", "message": error}, 400)

    result, status_code = execute_tool(route_name, payload)
    return json_response(func, result, status_code)


@app.route(route="run-w2-pipeline", methods=["POST"])
def run_w2_pipeline(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "run-w2-pipeline")


@app.route(route="status/{correlationId}", methods=["GET"])
def get_w2_pipeline_status(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = req.route_params.get("correlationId", "")
    tenant_id = req.params.get("tenantId", "")
    result, status_code = get_pipeline_status(correlation_id, tenant_id)
    return json_response(func, result, status_code)


@app.route(route="invoke-foundry-agent", methods=["POST"])
def invoke_foundry_agent(req: func.HttpRequest) -> func.HttpResponse:
    payload, error = parse_json_body(req)
    if error:
        return json_response(func, {"error": "invalid_request", "message": error}, 400)

    result, status_code = invoke_foundry_supervisor_agent(payload)
    return json_response(func, result, status_code)


@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%W2_SERVICEBUS_QUEUE_NAME%",
    connection="W2_SERVICEBUS_CONNECTION_STRING",
)
def process_w2_ingestion_queue(msg: func.ServiceBusMessage) -> None:
    message_body = msg.get_body().decode("utf-8")
    logging.info("Processing W-2 ingestion event from Service Bus.")
    result = process_service_bus_event(message_body)
    logging.info(
        "W-2 pipeline completed from Service Bus: correlationId=%s status=%s",
        result.get("correlationId"),
        result.get("status"),
    )


@app.route(route="start-w2-pipeline", methods=["POST"])
def start_w2_pipeline(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "start-w2-pipeline")


@app.route(route="process-w2-intake", methods=["POST"])
def process_w2_intake(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "process-w2-intake")


@app.route(route="extract-w2-document", methods=["POST"])
def extract_w2_document(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "extract-w2-document")


@app.route(route="validate-w2-facts", methods=["POST"])
def validate_w2_facts(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "validate-w2-facts")


@app.route(route="submit-w2-human-review", methods=["POST"])
def submit_w2_human_review(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "submit-w2-human-review")


@app.route(route="map-w2-tax-facts", methods=["POST"])
def map_w2_tax_facts(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "map-w2-tax-facts")


@app.route(route="generate-form-1040-document", methods=["POST"])
def generate_form_1040_document(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "generate-form-1040-document")


@app.route(route="evaluate-w2-compliance", methods=["POST"])
def evaluate_w2_compliance(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "evaluate-w2-compliance")


@app.route(route="persist-w2-pipeline-checkpoint", methods=["POST"])
def persist_w2_pipeline_checkpoint(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "persist-w2-pipeline-checkpoint")


@app.route(route="persist-completed-w2-pipeline", methods=["POST"])
def persist_completed_w2_pipeline(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "persist-completed-w2-pipeline")


@app.route(route="get-runtime-configuration", methods=["POST"])
def get_runtime_configuration(req: func.HttpRequest) -> func.HttpResponse:
    return _handle_tool_request(req, "get-runtime-configuration")
