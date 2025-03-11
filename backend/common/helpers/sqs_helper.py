# Built-in imports
import json
import boto3

# Own imports
from common.logger import custom_logger

logger = custom_logger()


class SQSHelper:
    """Custom SQS Helper for simplifying CRUD operations."""

    def __init__(self, queue_url: str) -> None:
        """
        :param queue_url (str): SQS URL for sending the messages.
        """
        self.queue_url = queue_url
        self.sqs_client = boto3.client("sqs")

    def send_message(self, message: dict):
        try:
            input_message: dict = {**message}

            logger.info(
                f"Sending to queue: {self.queue_url} message: {str(input_message)}"
            )

            queue_response = self.sqs_client.send_message(
                MessageBody=json.dumps(input_message),
                QueueUrl=self.queue_url,
            )
            logger.info(f"Response from Queue: {queue_response}")
            return queue_response
        except Exception as error:
            logger.error(
                f"send_message operation failed for: "
                f"queue_url: {self.queue_url}."
                f"error: {error}."
            )
            raise error
