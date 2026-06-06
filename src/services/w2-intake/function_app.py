import azure.functions as func

from w2_intake_app import main


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="upload-w2", methods=["POST"])
def upload_w2(req: func.HttpRequest) -> func.HttpResponse:
    return main(req)
