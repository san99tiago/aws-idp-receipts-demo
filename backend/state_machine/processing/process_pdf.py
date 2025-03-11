# Built-in imports
import os
import json
import boto3
import base64

# Own imports
from common.logger import custom_logger
from state_machine.base_step_function import BaseStepFunction
from state_machine.processing.idp_system_prompt import SYSTEM_PROMPT


logger = custom_logger()

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
BEDROCK_LLM_MODEL_ID = os.environ.get("BEDROCK_LLM_MODEL_ID")

# Initialize S3 and Bedrock clients
s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime")


class ProcessPDF(BaseStepFunction):
    """
    This class contains methods that serve as the "PDF processing" for the State Machine.
    """

    def __init__(self, event):
        super().__init__(event, logger=logger)

    def process_pdf(self):
        """
        Method to validate the input message and process the expected response.
        """

        self.logger.info("Starting process_pdf for the IDP")

        # TODO: Validate if Textract or other AWS services are worth it for the use case as Backup plan?
        self.process_pdf_from_s3(
            s3_pdf_key=self.event.get("s3_key_original_asset"),
        )

        self.logger.info("Processing PDF finished successfully")

        return self.event

    def process_pdf_from_s3(
        self,
        s3_pdf_key: str,
        local_pdf_path: str = "/tmp/processed_pdf.pdf",
    ):
        """
        Downloads a PDF from S3, processes it using Amazon Bedrock,
        and returns a JSON definition of the PDF content.

        :param s3_pdf_key: The key of the PDF in the S3 bucket.
        :param local_pdf_path: Path to save the downloaded PDF locally.
        :return: JSON definition of the PDF content.
        """
        # Download the PDF from S3
        s3_client.download_file(S3_BUCKET_NAME, s3_pdf_key, local_pdf_path)

        # Read and encode the PDF as a Base64 string
        with open(local_pdf_path, "rb") as pdf_file:
            binary_data = pdf_file.read()
            base_64_encoded_data = base64.b64encode(binary_data)
            base64_string = base_64_encoded_data.decode("utf-8")

        # Update the system prompt
        system_list = [{"text": SYSTEM_PROMPT}]

        # Define the user message including the PDF and prompt
        message_list = [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": "pdf",
                            "name": "DocumentPDFmessages",
                            "source": {"bytes": base64_string},
                        }
                    },
                    {"text": "Provide a JSON definition of the PDF."},
                ],
            }
        ]

        # Configure inference parameters
        inf_params = {"maxTokens": 5000, "topP": 0.1, "topK": 20, "temperature": 0.3}

        # Create the native request
        native_request = {
            "schemaVersion": "messages-v1",
            "messages": message_list,
            "system": system_list,
            "inferenceConfig": inf_params,
        }

        # Invoke the Bedrock model
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_LLM_MODEL_ID, body=json.dumps(native_request)
        )
        model_response = json.loads(response["body"].read())
        logger.debug(model_response, extra_message="model_response")

        # Extract and return the JSON definition
        response_text = model_response["output"]["message"]["content"]
        logger.debug(response_text, extra_message="response_text")
        self.event["response_process_pdf_txt"] = response_text

        # Load the Response JSON into a Python dictionary
        text_json_response = response_text[0]["text"]

        # Remove the JSON format (open/close def)
        json_response_parsed = text_json_response.replace("```json", "").replace(
            "```", ""
        )
        json_response = json.loads(json_response_parsed)
        logger.debug(json_response, extra_message="json_response")
        self.event["response_process_document_json"] = json_response

        return json_response
