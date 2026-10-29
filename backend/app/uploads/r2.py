import os
import boto3
from botocore.config import Config
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings

class R2StorageService:
    def __init__(self):
        self.bucket = settings.R2_BUCKET_NAME
        self.endpoint = settings.R2_ENDPOINT_URL
        if not self.endpoint and settings.R2_ACCOUNT_ID:
            self.endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

        self.has_credentials = bool(
            settings.R2_ACCESS_KEY_ID and 
            settings.R2_SECRET_ACCESS_KEY and 
            self.endpoint
        )

        if self.has_credentials:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=Config(signature_version="s3v4")
            )
        else:
            self.s3_client = None
            self.local_storage_dir = Path("./storage/r2_mock")
            self.local_storage_dir.mkdir(parents=True, exist_ok=True)

    def create_multipart_upload(self, key: str) -> str:
        if self.has_credentials:
            res = self.s3_client.create_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                ContentType="application/pdf"
            )
            return res["UploadId"]
        else:
            upload_id = f"mock-upload-{abs(hash(key))}"
            (self.local_storage_dir / upload_id).mkdir(parents=True, exist_ok=True)
            return upload_id

    def generate_presigned_part_url(self, key: str, upload_id: str, part_number: int) -> str:
        if self.has_credentials:
            return self.s3_client.generate_presigned_url(
                ClientMethod="upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": part_number
                },
                ExpiresIn=900  # 15 minutes
            )
        else:
            return f"{settings.APP_ORIGIN}/api/uploads/mock-part?key={key}&upload_id={upload_id}&part={part_number}"

    def complete_multipart_upload(self, key: str, upload_id: str, parts: List[Dict[str, any]]) -> Dict[str, any]:
        if self.has_credentials:
            sorted_parts = sorted(parts, key=lambda x: x["PartNumber"])
            return self.s3_client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": sorted_parts}
            )
        else:
            return {"Location": f"mock://{self.bucket}/{key}", "Key": key}

    def head_object(self, key: str) -> Dict[str, any]:
        if self.has_credentials:
            return self.s3_client.head_object(Bucket=self.bucket, Key=key)
        else:
            mock_file = self.local_storage_dir / key.replace("/", "_")
            size = mock_file.stat().st_size if mock_file.exists() else 1024
            return {"ContentLength": size}

    def get_first_kb(self, key: str) -> bytes:
        if self.has_credentials:
            res = self.s3_client.get_object(Bucket=self.bucket, Key=key, Range="bytes=0-1023")
            return res["Body"].read()
        else:
            mock_file = self.local_storage_dir / key.replace("/", "_")
            if mock_file.exists():
                with open(mock_file, "rb") as f:
                    return f.read(1024)
            # Default PDF magic bytes
            return b"%PDF-1.7\r\n%"

    def stream_to_temp_file(self, key: str, target_temp_path: Path):
        """Streams R2 object to a temp file on disk in 1MB reads (constant memory)."""
        target_temp_path.parent.mkdir(parents=True, exist_ok=True)
        if self.has_credentials:
            res = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            body = res["Body"]
            with open(target_temp_path, "wb") as f:
                while chunk := body.read(1024 * 1024):
                    f.write(chunk)
        else:
            mock_file = self.local_storage_dir / key.replace("/", "_")
            if mock_file.exists():
                with open(mock_file, "rb") as src, open(target_temp_path, "wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
            else:
                # If mock file doesn't exist, generate a small test PDF into the temp path
                from scripts.make_fixture_pdf import generate_pdf
                generate_pdf(str(target_temp_path), target_pages=5)

storage_service = R2StorageService()
