"""
Japan OCR Tool - Azure Blob Storage Client

Abstracts file storage behind a single interface that works both with Azure
Blob Storage (production) and a local filesystem directory (development/testing).

Key Features:
- Transparent local mode: falls back to backend/storage_pdf/ when no
  Azure connection string is configured
- SAS URL generation: time-limited read-only URLs for secure file downloads
- Lazy client init: Azure SDK imported and connected only on first use

Dependencies: azure-storage-blob (optional; only needed in Azure mode)
Author: SHIRIN MIRZI M K
"""

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
    """
    Storage abstraction supporting both Azure Blob Storage and local filesystem.

    Attributes:
        _client: Lazily initialised BlobServiceClient; None until first Azure call.
        _connection_string: Azure Storage connection string from environment;
            empty string signals local-filesystem mode.
    """

    def __init__(self):
        """
        Initialise the client from environment configuration.

        No network connection is made here; Azure SDK is imported and
        connected lazily on the first upload or SAS generation call.
        """
        self._client = None
        self._connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

    def _is_local(self) -> bool:
        """
        Return True when running in local-filesystem mode.

        Returns:
            True if no Azure connection string is configured, False otherwise.
        """
        return not self._connection_string.strip()

    def _get_client(self):
        """
        Return the BlobServiceClient, initialising it on first access.

        Returns:
            azure.storage.blob.BlobServiceClient connected via the
            AZURE_STORAGE_CONNECTION_STRING environment variable.
        """
        if self._client is None:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
        return self._client

    def upload_file(self, file_content: bytes, blob_name: str) -> str:
        """
        Upload bytes to Azure Blob Storage or the local filesystem.

        Args:
            file_content: Raw bytes of the file to store.
            blob_name: Relative path used as the blob name / local sub-path,
                e.g. "executions/20250430_143022/ProcessedFiles/invoice.pdf".

        Returns:
            A "local://<absolute-path>" URI in local mode, or the public
            Azure blob URL in Azure mode.
        """
        if self._is_local():
            local_path = os.path.join(LOCAL_STORAGE_BASE, blob_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_content)
            logger.info("Saved locally: %s", local_path)
            return f"local://{local_path}"
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
        """
        Generate a time-limited SAS download URL for a stored blob.

        Args:
            blob_path: Relative path of the blob within the container.
            expiry_minutes: How long the SAS token remains valid; defaults
                to 60 minutes.

        Returns:
            A "local://<absolute-path>" URI in local mode, or a full HTTPS
            SAS URL in Azure mode valid for expiry_minutes.
        """
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
        """
        Check whether a blob or local file exists without downloading it.

        Args:
            blob_name: Relative path of the blob to check.

        Returns:
            True if the file exists, False if it does not or if the check
            raises an exception (treated as non-existent).
        """
        if self._is_local():
            return os.path.exists(os.path.join(LOCAL_STORAGE_BASE, blob_name))
        try:
            client = self._get_client()
            blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            return blob_client.exists()
        except Exception:
            return False


azure_storage_client = AzureStorageClient()
