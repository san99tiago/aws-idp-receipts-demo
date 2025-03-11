# Built-in imports
import os
import boto3
from datetime import datetime, timezone
from typing import Optional

# External imports
from aws_lambda_powertools import Logger

# Own imports
from common.logger import custom_logger
from common.helpers.dynamodb_helper import DynamoDBHelper
from common.helpers.sqs_helper import SQSHelper


# Initialize DynamoDB helper for item's abstraction
TABLE_NAME = os.environ.get("TABLE_NAME")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
SQS_URL_AFTER_IDP_PROCESSING = os.environ.get("SQS_URL_AFTER_IDP_PROCESSING")
ENDPOINT_URL = os.environ.get("ENDPOINT_URL")  # Used for local testing
dynamodb_helper = DynamoDBHelper(TABLE_NAME, ENDPOINT_URL)
sqs_helper = SQSHelper(SQS_URL_AFTER_IDP_PROCESSING)
s3_client = boto3.client("s3")  # TODO: Refactor to dedicated helper


class Documents:
    """Class to define Documents items in a simple fashion."""

    def __init__(self, logger: Optional[Logger] = None) -> None:
        """
        :param logger (Optional(Logger)): Logger object.
        """
        self.logger = logger or custom_logger()

    # TODO: Add pagination
    def get_all_documents(self) -> list:
        """
        Method to get all DOCUMENT items for a given user.
        """
        self.logger.info("Retrieving all DOCUMENT items for")

        # Return the latest X documents based on creation time (ordered)
        results = dynamodb_helper.query_by_pk_and_sk_begins_with(
            partition_key="ALL_DOCUMENTS",
            sort_key_portion="CREATED_AT#",
            limit=30,  # TODO: Enable parameter from HTTP request and pagination
            gsi_index_name="GSI1",  # Intentional query GSI1 to get ordered documents
        )

        # Filter results to ONLY return PK and SK
        filtered_results = [
            {
                "document_id": result.get("PK").split("#")[1],
                "document_name": result.get("s3_key_original_asset"),
                "status": result.get("status"),
                "last_processed": result.get("last_processed"),
            }
            for result in results
        ]
        # TODO: Add pagination capabilities... (next key, etc)

        self.logger.debug(filtered_results)
        self.logger.info(f"Items from query: {len(filtered_results)}")
        return filtered_results

    def get_document_by_ulid(self, ulid: str) -> dict:
        """
        Method to get a DOCUMENT item by its ULID.
        :param ulid (str): ULID for a specific DOCUMENT item.
        """
        self.logger.info(f"Retrieving DOCUMENT item by ULID: {ulid}.")

        result = dynamodb_helper.query_by_pk_and_sk_begins_with(
            partition_key=f"DOCUMENT#{ulid}",
            sort_key_portion="VERSION#",
            limit=1,  # We only need the first item (LATEST)
        )
        result = (
            result[0] if result else None
        )  # Intentionally access first item (latest)
        self.logger.debug(result, message_details="query_by_pk_and_sk_begins_with")

        if not result:
            self.logger.debug(
                f"get_document_by_ulid returned non-existing DOCUMENT item: {ulid}"
            )
            return {}

        # Get S3 Key from DynamoDB item
        s3_key = result.get("s3_key_original_asset")

        # Generate a pre-signed URL for the S3 Key
        self.logger.debug(f"Generating pre-signed URL for S3 Key: {s3_key}")
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600,  # Image URL expires in 1 hour
        )
        self.logger.debug(presigned_url, message_details="presigned_url_result")

        # Return document item and its corresponding presigned url
        return result | {"presigned_url": presigned_url}

    def patch_document(self, ulid: str, document_data: dict):
        """
        Method to patch an existing DOCUMENT item.
        :param ulid (str): ULID for a specific DOCUMENT item.
        :param document_data (dict): Data for the new DOCUMENT item.
        """
        # DOCUMENT: Implement patch logic
        self.logger.info(f"Updating DOCUMENT item by ULID: {ulid}")

        # Validate that DOCUMENT item exists
        existing_document_item = self.get_document_by_ulid(ulid)
        if not existing_document_item:
            self.logger.info(
                f"delete_document failed due to non-existing DOCUMENT item to delete: {ulid}"
            )
            return {
                "status": "error",
                "message": "not found",
            }

        # ISO 8601 timestamp for ordering
        timestamp = datetime.now(timezone.utc).isoformat()
        print(timestamp)

        document_data["status"] = "PAID"
        document_data["last_processed"] = timestamp

        # Note: internal dict data merged as follows to avoid data loss
        data_dict_original = existing_document_item["data"]
        data_dict_new = document_data["data"]

        # Update new_data with caution first (internal level of dict)
        new_data = data_dict_original | data_dict_new

        # Update existing_document_item with new_data
        document_data["data"] = new_data

        # Update document with new data (PATCH new fields only)
        new_data = existing_document_item | document_data

        # Update DynamoDB item
        result = dynamodb_helper.put_item(new_data)
        self.logger.info(f"Response from DynamoDB: {result}")

        # Send SQS Message for after IDP processing...
        try:
            response = sqs_helper.send_message(
                {
                    "document_id": ulid,
                    "s3_key_original_asset": existing_document_item.get(
                        "s3_key_original_asset"
                    ),
                    "correlation_id": existing_document_item.get("correlation_id"),
                    "data": existing_document_item.get("data"),
                }
            )
            self.logger.debug(f"Response from SQS: {response}")
        except Exception as e:
            self.logger.error(f"Error sending message to SQS: {e}")

        return {
            "status": "success",
            "message": f"Item patched successfully at {timestamp}",
        }

    def delete_document(self, ulid: str):
        """
        Method to delete an existing DOCUMENT item.
        :param ulid (str): ULID for a specific DOCUMENT item.
        :param document_data (dict): Data for the new DOCUMENT item.
        """

        # Validate that DOCUMENT item exists
        existing_document_item = self.get_document_by_ulid(ulid)
        if not existing_document_item:
            self.logger.info(
                f"delete_document failed due to non-existing DOCUMENT item to delete: {ulid}"
            )
            return {
                "status": "error",
                "message": "not found",
            }

        result = dynamodb_helper.delete_item(
            partition_key=f"DOCUMENT#{ulid}",
            sort_key="VERSION#1",  # Hardcoded as '1' for now...
        )
        self.logger.debug(result)

        return {
            "status": "success",
            "message": f"successfully deleted document with id: {ulid}",
        }
