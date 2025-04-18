# Built-in imports
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Own imports
from common.logger import custom_logger

logger = custom_logger()


class DynamoDBHelper:
    """Custom DynamoDB Helper for simplifying CRUD operations."""

    def __init__(self, table_name: str, endpoint_url: str = None) -> None:
        """
        :param table_name (str): Name of the DynamoDB table to connect with.
        :param endpoint_url (Optional(str)): Endpoint for DynamoDB (only for local tests).
        """
        self.table_name = table_name
        self.dynamodb_client = boto3.client("dynamodb", endpoint_url=endpoint_url)
        self.dynamodb_resource = boto3.resource("dynamodb", endpoint_url=endpoint_url)
        self.table = self.dynamodb_resource.Table(self.table_name)

    @staticmethod
    def dynamodb_to_json(dynamodb_item: dict) -> dict:
        """
        Converts a DynamoDB formatted item to a plain JSON dict.
        :param dynamodb_item (dict): Item in DynamoDB format.
        :return (dict): Converted JSON dictionary.
        """
        from boto3.dynamodb.types import TypeDeserializer

        deserializer = TypeDeserializer()
        return {k: deserializer.deserialize(v) for k, v in dynamodb_item.items()}

    def get_item_by_pk_and_sk(self, partition_key: str, sort_key: str) -> dict:
        """
        Method to get a single DynamoDB item from the primary key (pk+sk).
        :param partition_key (str): partition key value.
        :param sort_key (str): sort key value.
        """
        logger.info(
            f"Starting get_item_by_pk_and_sk with"
            f"pk: ({partition_key}) and sk: ({sort_key})"
        )

        # The structure key for a single-table-design "PK" and "SK" naming
        primary_key_dict = {
            "PK": {
                "S": partition_key,
            },
            "SK": {
                "S": sort_key,
            },
        }
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key=primary_key_dict,
            )
            if "Item" in response:
                return self.dynamodb_to_json(response["Item"])
            else:
                return {}

        except ClientError as error:
            logger.error(
                f"get_item operation failed for: "
                f"table_name: {self.table_name}."
                f"pk: {partition_key}."
                f"sk: {sort_key}."
                f"error: {error}."
            )
            raise error

    def query_by_pk_and_sk_begins_with(
        self,
        partition_key: str,
        sort_key_portion: str,
        limit: int = 50,
        gsi_index_name: str = None,
    ) -> list[dict]:
        """
        Method to run a query against DynamoDB with partition key and the sort
        key with <begins-with> functionality on it.
        :param partition_key (str): partition key value.
        :param sort_key_portion (str): sort key portion to use in query.
        :param limit (int): limit of how many results to retrieve.
        :param gsi_index_name (str): Optional name of the GSI to query.
        """
        logger.info(
            f"Starting query_items with pk: ({partition_key}), "
            f"sk: ({sort_key_portion}), "
            f"gsi_index_name: ({gsi_index_name})"
        )

        all_items = []
        try:
            # Define the key condition for the query
            key_condition = Key("PK").eq(partition_key) & Key("SK").begins_with(
                sort_key_portion
            )

            # If querying a GSI, adjust the key names
            if gsi_index_name:
                key_condition = Key("GSI1PK").eq(partition_key) & Key(
                    "GSI1SK"
                ).begins_with(sort_key_portion)

            # Initial query
            query_params = {
                "KeyConditionExpression": key_condition,
                "Limit": limit,
            }
            if gsi_index_name:
                query_params["IndexName"] = gsi_index_name

            response = self.table.query(**query_params)
            if "Items" in response:
                all_items.extend(response["Items"])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.query(**query_params)
                if "Items" in response:
                    all_items.extend(response["Items"])

            return all_items
        except ClientError as error:
            logger.error(
                f"Query operation failed for: "
                f"table_name: {self.table_name}, "
                f"pk: {partition_key}, "
                f"sk: {sort_key_portion}, "
                f"gsi_index_name: {gsi_index_name}, "
                f"error: {error}."
            )
            raise error

    def put_item(self, data: dict) -> dict:
        """
        Method to add a single DynamoDB item.
        :param data (dict): Item to be added in a JSON format (without the "S", "N", "B" approach).
        """
        logger.info("Starting put_item operation.")
        logger.debug(data, message_details=f"Data to be added to {self.table_name}")

        try:
            response = self.table.put_item(
                TableName=self.table_name,
                Item=data,
            )
            logger.info(response)
            return response
        except ClientError as error:
            logger.error(
                f"put_item operation failed for: "
                f"table_name: {self.table_name}."
                f"data: {data}."
                f"error: {error}."
            )
            raise error

    def delete_item(self, partition_key: str, sort_key: str):
        """
        Method to delete a single DynamoDB item from the primary key (pk+sk).
        :param partition_key (str): partition key value.
        :param sort_key (str): sort key value.
        """
        logger.info(
            f"Starting delete_item with" f"pk: ({partition_key}) and sk: ({sort_key})"
        )
        try:
            response = self.table.delete_item(
                Key={
                    "PK": partition_key,
                    "SK": sort_key,
                },
            )
            return response
        except Exception as error:
            logger.error(
                f"delete_item operation failed for: "
                f"table_name: {self.table_name}."
                f"pk: {partition_key}."
                f"sk: {sort_key}."
                f"error: {str(error)}."
            )
            raise error

    # TODO: add pagination!!!
    def scan_all_items(self) -> list[dict]:
        """
        Method to scan all items in a DynamoDB table.
        """
        logger.info("Starting scan_all_items operation.")

        try:
            response = self.table.scan()
            if "Items" in response:
                return response["Items"]
            else:
                return []
        except ClientError as error:
            logger.error(
                f"scan_all_items operation failed for: "
                f"table_name: {self.table_name}."
                f"error: {error}."
            )
            raise error
