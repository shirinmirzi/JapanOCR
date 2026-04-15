import os
import logging
from datetime import datetime, timedelta, timezone
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

logger = logging.getLogger(__name__)

CONTAINER_NAME = "invoices"


class AzureStorageClient:
    def __init__(self):
        self._client = None
        self._connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            if not self._connection_string:
                raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set")
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
        return self._client

    def upload_file(self, file_content: bytes, blob_name: str) -> str:
        client = self._get_client()
        container_client = client.get_container_client(CONTAINER_NAME)
        try:
            container_client.create_container()
        except Exception:
            pass  # Container already exists
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(file_content, overwrite=True)
        return blob_client.url

    def generate_sas_url(self, blob_path: str, expiry_minutes: int = 60) -> str:
        client = self._get_client()
        account_name = client.account_name
        account_key = client.credential.account_key
        expiry = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=CONTAINER_NAME,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )
        blob_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_path}?{sas_token}"
        return blob_url

    def file_exists(self, blob_name: str) -> bool:
        try:
            client = self._get_client()
            blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            return blob_client.exists()
        except Exception:
            return False


azure_storage_client = AzureStorageClient()
