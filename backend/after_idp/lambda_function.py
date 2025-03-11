# Built-in imports
import os


# Own imports
from common.logger import custom_logger
from common.helpers.dynamodb_helper import DynamoDBHelper

# External imports
from aws_lambda_powertools.utilities.typing import LambdaContext


TABLE_NAME = os.environ.get("TABLE_NAME")
BUCKET_NAME = os.environ.get("BUCKET_NAME")

logger = custom_logger()
dynamodb_helper = DynamoDBHelper(table_name=TABLE_NAME)


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: LambdaContext):

    logger.info("PROCESSING PDF...")

    return {
        "statusCode": 200,
        "body": {"message": "PDF processed successfully"},
    }
