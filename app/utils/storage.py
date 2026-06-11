import os
import uuid

from flask import current_app, url_for
from werkzeug.utils import secure_filename

ALLOWED = {
    "pdf": {"pdf"},
    "ppt": {"ppt", "pptx"},
    "internal": {"pdf", "ppt", "pptx", "doc", "docx", "zip", "txt", "md"},
    "submission": {"pdf", "zip", "doc", "docx", "txt", "py", "ipynb", "md"},
}


def _s3_client():
    import boto3

    cfg = current_app.config
    if not cfg.get("AWS_S3_BUCKET") or not cfg.get("AWS_ACCESS_KEY_ID"):
        return None
    return boto3.client(
        "s3",
        aws_access_key_id=cfg["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["AWS_SECRET_ACCESS_KEY"],
        region_name=cfg["AWS_S3_REGION"],
    )


def allowed_file(filename, kind):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED.get(kind, set())


def save_file(file_storage, prefix="files"):
    """Store an uploaded file in S3 when configured, else local uploads.

    Returns the stored object key (relative path / S3 key).
    """
    filename = secure_filename(file_storage.filename)
    key = f"{prefix}/{uuid.uuid4().hex}_{filename}"

    client = _s3_client()
    if client:
        client.upload_fileobj(
            file_storage, current_app.config["AWS_S3_BUCKET"], key,
            ExtraArgs={"ContentType": file_storage.mimetype or "application/octet-stream"},
        )
        return key

    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], prefix)
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, key.split("/", 1)[1]))
    return key


def file_url(key):
    """Public/temporary URL for a stored key."""
    if not key:
        return None
    client = _s3_client()
    if client:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": current_app.config["AWS_S3_BUCKET"], "Key": key},
            ExpiresIn=3600,
        )
    return url_for("static", filename=f"uploads/{key}")
