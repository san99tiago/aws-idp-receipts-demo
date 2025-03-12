# Built-in imports
import os
import uuid
import json

# Own imports
from api.access_patterns.documents import Documents
from common.logger import custom_logger
from after_idp.generate_certificates import generate_document_pdf
from common.helpers.s3_helper import upload_pdf_to_s3
from common.helpers.dynamodb_helper import DynamoDBHelper


# External imports
from aws_lambda_powertools.utilities.typing import LambdaContext
import json

logger = custom_logger()

TABLE_NAME = os.environ.get("TABLE_NAME")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
ENDPOINT_URL = os.environ.get("ENDPOINT_URL")  # Used for local testing

dynamodb_helper = DynamoDBHelper(TABLE_NAME, ENDPOINT_URL)


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: LambdaContext):

    logger.info("PROCESSING PDF...")

    # Get the S3 key from the event
    event_body_string = event["Records"][0]["body"]
    event_body = json.loads(event_body_string)
    document_id = event_body["document_id"]
    logger.info(f"document_id: {document_id}")

    # Download the DynamoDB item for the current document
    todo = Documents(logger=logger)
    result = todo.get_document_by_ulid(ulid=document_id)
    logger.info("Finished read_document_item() successfully")

    logger.info(f"FLAG 1: {document_id}")

    # Generate PDF File
    pdf_local_path = generate_document_pdf(
        title="DemoBank",
        project_details="Proyecto No: 980",
        document_key="No.",
        amount_key="POR:",
        amount_value=result.get("data", {}).get("total", "PENDIENTE"),
        details_1="QUEDAN en nuestro poder para revisión las Factura(s)/Recibido(s) No.: 4209,4215",
        valor_en_letras=result.get("data", {}).get("valor_en_letras", "PENDIENTE"),
        date=result.get("data", {}).get("fecha_generacion", "N/A"),
        nombre_emisor=result.get("data", {}).get("nombre_receptor", "N/A"),
        final_note="This document is issued for DEMO purposes only.",
    )
    logger.debug(f"pdf_local_path: {pdf_local_path}")

    logger.info(f"FLAG 2: {document_id}")

    # Upload the local certificate to an S3 bucket and generate public URL for 10 mins
    s3_certificate_key_path = f"certificates/{str(uuid.uuid4())}/bank_certificate.pdf"
    upload_pdf_to_s3(
        bucket_name=S3_BUCKET_NAME,
        file_path=pdf_local_path,
        object_name=s3_certificate_key_path,
    )

    logger.info(f"FLAG 3: {document_id}")

    # UPDATE DYNAMODB TABLE WITH S3_Processed_KEY
    # Update DynamoDB item with the S3 key final asset (generated certificate)
    logger.info(f"Updating DOCUMENT item by ULID: {document_id}")

    ####
    todo.patch_document(
        ulid=document_id,
        send_sqs_message=False,
        document_data={
            "s3_key_final_asset": s3_certificate_key_path,
            "data": {  # Added to avoid key errors in the patch document (TODO: Cleanup)
                "metadata": "process_after_idp_done",
            },
        },
    )

    logger.info(f"FLAG 4: {document_id}")

    return {
        "statusCode": 200,
        "body": {"message": "PDF processed successfully"},
    }
