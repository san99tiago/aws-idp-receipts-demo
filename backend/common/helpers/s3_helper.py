import os
import boto3

# Own imports
from common.logger import custom_logger


logger = custom_logger()
s3_client = boto3.client("s3")


def upload_pdf_to_s3(bucket_name, file_path, object_name=None, expiration=600) -> str:
    """
    Uploads a PDF to an S3 bucket and generates a temporary public URL.

    :param bucket_name: The name of the S3 bucket.
    :param file_path: Path to the PDF file to upload.
    :param object_name: The S3 object name. If None, file_path's basename is used.
    """
    try:

        # If no object name is provided, use the file name
        if object_name is None:
            object_name = os.path.basename(file_path)

        # Upload the file
        result = s3_client.upload_file(file_path, bucket_name, object_name)
        logger.info(f"File uploaded successfully to {bucket_name}/{object_name}")
        return result
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return f"An unexpected error occurred: {e}"


# Local tests/validations
if __name__ == "__main__":

    # Example usage
    bucket_name = "san99tiago-manual-tests-430118815432"
    file_path = "./temp/certificate.pdf"

    # Call the function to upload the file and generate the URL
    presigned_url = upload_pdf_to_s3(bucket_name, file_path)

    if presigned_url.startswith("http"):
        logger.info("Temporary URL generated:", presigned_url)
    else:
        logger.info(presigned_url)
