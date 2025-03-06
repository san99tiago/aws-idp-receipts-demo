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


class ProcessImage(BaseStepFunction):
    """
    This class contains methods that serve as the "image processing" for the State Machine.
    """

    def __init__(self, event):
        super().__init__(event, logger=logger)

    def process_image(self):
        """
        Method to validate the input message and process the expected response.
        """

        self.logger.info("Starting process_image for the IDP")

        # TODO: Validate if Textract or Rekognition is worth it for the use case as Backup plan?
        self.process_image_from_s3(
            s3_image_key=self.event.get("object_key"),
        )

        self.logger.info("Processing image finished successfully")

        return self.event

    def process_image_from_s3(
        self,
        s3_image_key: str,
        local_image_path_without_extension: str = "/tmp/processed_image",
    ):
        """
        Downloads an image from S3, processes it using Amazon Bedrock,
        and returns a JSON definition of the image.

        :param s3_image_key: The key of the image in the S3 bucket.
        :return: JSON definition of the image.
        """
        # Download the image from S3
        image_file_path = (
            f"{local_image_path_without_extension}.{self.event.get('input_extension')}"
        )
        s3_client.download_file(S3_BUCKET_NAME, s3_image_key, image_file_path)

        # Read and encode the image as a Base64 string
        with open(image_file_path, "rb") as image_file:
            binary_data = image_file.read()
            base_64_encoded_data = base64.b64encode(binary_data)
            base64_string = base_64_encoded_data.decode("utf-8")

        # Update the system prompt
        system_list = [{"text": SYSTEM_PROMPT}]

        # Define the user message including the image and prompt
        message_list = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": self.event.get("input_extension"),
                            "source": {"bytes": base64_string},
                        }
                    },
                    {"text": "Provide a JSON definition of the image."},
                ],
            }
        ]

        # Configure inference parameters
        inf_params = {"maxTokens": 300, "topP": 0.1, "topK": 20, "temperature": 0.3}

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
        self.event["response_process_image_txt"] = response_text

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
