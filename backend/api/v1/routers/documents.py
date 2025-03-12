# Built-in imports
from typing import Annotated
from uuid import uuid4

# Own imports
from api.access_patterns.documents import Documents

# External imports
from fastapi import APIRouter, Header, HTTPException
from aws_lambda_powertools import Logger


logger = Logger(
    service="api-documents-idp",
    log_uncaught_exceptions=True,
    owner="san99tiago",
)
doc_helper = Documents(logger)

router = APIRouter()


@router.get("/documents", tags=["documents"])
async def read_all_documents(
    correlation_id: Annotated[str | None, Header()] = uuid4(),
):
    try:
        logger.append_keys(correlation_id=correlation_id)
        logger.info("Starting documents handler for read_all_documents()")

        documents = Documents(logger=logger)
        result = documents.get_all_documents()
        logger.info("Finished read_document_item() successfully")
        return result

    except Exception as e:
        logger.error(f"Error in read_all_documents(): {e}")
        raise e


@router.get("/documents/{document_id}", tags=["documents"])
async def read_document_item(
    document_id: str,
    correlation_id: Annotated[str | None, Header()] = uuid4(),
):
    try:
        logger.append_keys(correlation_id=correlation_id)
        logger.info("Starting documents handler for read_document_item()")

        todo = Documents(logger=logger)
        result = todo.get_document_by_ulid(ulid=document_id)
        logger.info("Finished read_document_item() successfully")
        return result

    except Exception as e:
        logger.error(f"Error in read_document_item(): {e}")
        raise e


# Intentionally not able to create documents for now... Only via IDP processing...
# TODO: Validate if needed to migrate the IDP processing creation to a POST endpoint.


@router.patch("/documents/{document_id}", tags=["documents"])
async def patch_todo_item(
    document_id: str,
    document_details: dict,
    correlation_id: Annotated[str | None, Header()] = uuid4(),
):
    try:
        logger.append_keys(correlation_id=correlation_id)
        logger.info("Starting documents handler for patch_todo_item()")

        logger.debug(f"document_details: {document_details}")
        # TODO: Add validation of body/patch payload
        # TODO: Actually PATCH the document... For now passthrough

        documents = Documents(logger=logger)
        result = documents.patch_document(
            ulid=document_id,
            document_data=document_details,
            send_sqs_message=True,
        )

        logger.info("Finished patch_document_item() successfully")
        return result

    except Exception as e:
        logger.error(f"Error in patch_document_item(): {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/documents/{document_id}", tags=["documents"])
async def delete_document_item(
    document_id: str,
    correlation_id: Annotated[str | None, Header()] = uuid4(),
):
    try:
        logger.append_keys(correlation_id=correlation_id)
        logger.info("Starting documents handler for delete_document_item()")

        documents = Documents(logger=logger)
        result = documents.delete_document(ulid=document_id)

        logger.info("Finished delete_document_item() successfully")
        return result

    except Exception as e:
        logger.error(f"Error in delete_document_item(): {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
