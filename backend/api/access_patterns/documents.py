# Built-in imports
import os
import boto3
from typing import Optional

# External imports
from fastapi import HTTPException
from aws_lambda_powertools import Logger

# Own imports
from common.logger import custom_logger
from common.helpers.dynamodb_helper import DynamoDBHelper

# Initialize DynamoDB helper for item's abstraction
TABLE_NAME = os.environ.get("TABLE_NAME")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
ENDPOINT_URL = os.environ.get("ENDPOINT_URL")  # Used for local testing
dynamodb_helper = DynamoDBHelper(TABLE_NAME, ENDPOINT_URL)
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

        # Note: does not have pagination (for now...)
        results = dynamodb_helper.scan_all_items()

        # Filter results to ONLY return PK and SK
        filtered_results = [
            {
                "PK": result.get("PK"),
                "SK": result.get("SK"),
                "object_key": result.get("object_key"),
            }
            for result in results
        ]

        self.logger.debug(filtered_results)
        self.logger.info(f"Items from query: {len(filtered_results)}")
        return filtered_results

    def get_document_by_ulid(self, ulid: str) -> dict:
        """
        Method to get a DOCUMENT item by its ULID.
        :param ulid (str): ULID for a specific DOCUMENT item.
        """
        self.logger.info(f"Retrieving DOCUMENT item by ULID: {ulid}.")

        result = dynamodb_helper.get_item_by_pk_and_sk(
            partition_key=f"DOCUMENT#{ulid}",
            sort_key="VERSION#1",  # Hardcoded as '1' for now...
        )
        self.logger.debug(result, message_details="get_item_by_pk_and_sk_result")

        if not result:
            self.logger.debug(
                f"get_document_by_ulid returned non-existing DOCUMENT item: {ulid}"
            )
            return {}

        # Get S3 Key from DynamoDB item
        s3_key = result.get("object_key")

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

        return {
            "status": "success",
            "message": "Patch endpoint not supported yet, be ready for updates soon",
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
