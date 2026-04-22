import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CONTAINER_NAME = "invoices"
# Resolves to backend/storage_pdf/
LOCAL_STORAGE_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "storage_pdf"
)


class AzureStorageClient:
    def __init__(self):
        self._client = None
        self._connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

    def _is_local(self) -> bool:
        return not self._connection_string.strip()

    def _get_client(self):
        if self._client is None:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
        return self._client

    def upload_file(self, file_content: bytes, blob_name: str) -> str:
        if self._is_local():
            local_path = os.path.join(LOCAL_STORAGE_BASE, blob_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_content)
            logger.info("Saved locally: %s", local_path)
            return f"local://{local_path}"
        # Azure path
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
        if self._is_local():
            local_path = os.path.join(LOCAL_STORAGE_BASE, blob_path)
            return f"local://{local_path}"
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas
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
        return f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_path}?{sas_token}"

    def file_exists(self, blob_name: str) -> bool:
        if self._is_local():
            return os.path.exists(os.path.join(LOCAL_STORAGE_BASE, blob_name))
        try:
            client = self._get_client()
            blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            return blob_client.exists()
        except Exception:
            return False


azure_storage_client = AzureStorageClient()
