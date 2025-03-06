# Built-in imports
import os

# Own imports
from common.logger import custom_logger
from state_machine.base_step_function import BaseStepFunction
from common.helpers.dynamodb_helper import DynamoDBHelper

# External imports
from ulid import ULID

logger = custom_logger()

TABLE_NAME = os.environ.get("TABLE_NAME")
dynamodb_helper = DynamoDBHelper(table_name=TABLE_NAME)


class SaveData(BaseStepFunction):
    """
    This class contains methods that will "save the data to DynamoDB" for the State Machine.
    """

    def __init__(self, event):
        super().__init__(event, logger=logger)

    def save_data(self):
        """
        Method to save the data to DynamoDB to the user.
        """

        self.logger.info("Starting save_data for the IDP")

        # TODO: Prepare data into DynamoDB Single Table Design PK/SK schema...
        # TODO: Save processed document in DynamoDB for future IDP-API processing

        # Generate document unique identifier as ULID
        document_id = str(ULID())
        self.event["document_id"] = document_id

        dynamodb_item = {
            "PK": f"DOCUMENT#{document_id}",
            "SK": "VERSION#1",  # Hardcoded as '1' for now...
            "data": self.event.get("response_process_document_json", "NOT_FOUND"),
            "input_type": self.event.get("input_type", "NOT_FOUND"),
            "correlation_id": self.event.get("correlation_id", "NOT_FOUND"),
            "object_key": self.event.get("object_key", "NOT_FOUND"),
            "input_extension": self.event.get("input_extension", "NOT_FOUND"),
            "s3_event_time": self.event.get("time", "NOT_FOUND"),
        }
        response = dynamodb_helper.put_item(dynamodb_item)
        logger.debug(f"Response from DynamoDB: {response}")

        self.logger.info("Saving data finished successfully")

        self.event["save_data_response_status_code"] = 200
        return self.event
