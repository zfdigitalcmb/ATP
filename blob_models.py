# blob_models.py
import os
from azure.storage.blob import ContainerClient
from dotenv import load_dotenv
load_dotenv()

def download_missing_models():
    """
    Downloads only missing .pt model files from Azure Blob Storage
    to the local 'models' folder.
    """
    container_url = os.environ.get("AZURE_BLOB_CONTAINER_URL_MODELS_IPV_AI")
    sas_token = os.environ.get("AZURE_BLOB_SAS_MODELS_IPV_AI")
    local_dir = "models"

    if not container_url or not sas_token:
        print("⚠️ Azure model container URL or SAS token not found in environment.")
        return

    os.makedirs(local_dir, exist_ok=True)

    # Connect to container
    container_client = ContainerClient.from_container_url(f"{container_url}?{sas_token}")
    print("🔗 Connected to Azure Blob Container for models.")

    # List all .pt blobs
    blobs = [b.name for b in container_client.list_blobs() if b.name.endswith(".pt")]
    print(f"📦 Found {len(blobs)} model(s) in container.")

    downloaded, skipped = 0, 0
    for blob_name in blobs:
        local_path = os.path.join(local_dir, os.path.basename(blob_name))

        # Skip if model already exists locally
        if os.path.exists(local_path):
            print(f"✅ Skipped (already exists): {blob_name}")
            skipped += 1
            continue

        # Download missing model
        print(f"⬇️ Downloading: {blob_name} ...")
        blob_client = container_client.get_blob_client(blob_name)
        with open(local_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

        print(f"✅ Downloaded: {blob_name}")
        downloaded += 1

    print(f"🎯 Models ready — Downloaded: {downloaded}, Skipped: {skipped}")
