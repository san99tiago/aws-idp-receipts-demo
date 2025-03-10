# Built-in imports
import os


# Local Imports
from common.logger import custom_logger
from common.helpers.dynamodb_helper import DynamoDBHelper
from state_machine.base_step_function import BaseStepFunction


S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

logger = custom_logger()


class ValidateInput(BaseStepFunction):
    """
    This class contains methods that serve as event validation for the State Machine.
    """

    def __init__(self, event):
        super().__init__(event, logger=logger)

    def validate_input(self):
        """
        Method to validate the input JSON body for the beginning of the State Machine.
        """
        self.logger.info("Starting validate_input JSON body validation")
        self.event["input_type"] = "other"

        # TODO: Add a more complex validation here (Python schema, etc.)

        # Parse S3 Event details for IDP processing
        bucket_name = (
            self.event.get("detail", {}).get("bucket", {}).get("name", "NOT_FOUND")
        )
        s3_key_original_asset = (
            self.event.get("detail", {}).get("object", {}).get("key", "NOT_FOUND")
        )
        input_extension = (
            s3_key_original_asset.split(".")[-1]
            if "." in s3_key_original_asset
            else "other"
        )

        self.logger.info(
            f"Event details... bucket_name: {bucket_name}, s3_key_original_asset: {s3_key_original_asset}, input_extension: {input_extension}"
        )
        self.event["bucket_name"] = bucket_name
        self.event["s3_key_original_asset"] = s3_key_original_asset
        self.event["input_extension"] = input_extension

        # Categorize input based on extension
        if input_extension in ["jpg", "jpeg", "png"]:
            self.event["input_type"] = "image"
        else:
            self.event["input_type"] = input_extension

        # Add relevant data fields for traceability in the next State Machine steps
        self.event["correlation_id"] = self.correlation_id

        return self.event
