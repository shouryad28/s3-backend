import boto3
import os
from fastapi import UploadFile, HTTPException
from dotenv import load_dotenv
load_dotenv()

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")  # Updated to match your bucket
BUCKET = os.environ.get("S3_BUCKET", "explainer-videos-prod")  # Updated to match your bucket
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

# Debug logging
print(f"AWS Configuration:")
print(f"  Region: {AWS_REGION}")
print(f"  Bucket: {BUCKET}")
# print(f"  Access Key: {ACCESS_KEY}")
# print(f"  Secret Key: {SECRET_KEY}")
print(f"  Has Access Key: {bool(ACCESS_KEY)}")
print(f"  Has Secret Key: {bool(SECRET_KEY)}")

# Initialize S3 client
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
) if ACCESS_KEY and SECRET_KEY else boto3.client('s3')

MAX_BYTES = 20 * 1024 * 1024  # 20 MB cap

def norm_prefix(p: str) -> str:
    """Normalize prefix to ensure proper folder structure"""
    return "" if not p else (p if p.endswith("/") else p + "/")

async def upload_file_to_s3(file: UploadFile, prefix: str = "", filename: str = None) -> dict:
    """Upload file to S3 and return result"""
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB")
    
    key = (norm_prefix(prefix) + (filename or file.filename)).lstrip("/")
    
    s3.put_object(
        Bucket=BUCKET, 
        Key=key, 
        Body=data,
        ContentType=file.content_type or "application/octet-stream"
    )
    
    return {"ok": True, "key": key}

def list_s3_objects(prefix: str = "", token: str = None) -> dict:
    """List objects in S3 bucket with folder structure"""
    try:
        # First check if bucket exists
        s3.head_bucket(Bucket=BUCKET)
        print(f"✓ Bucket '{BUCKET}' exists and is accessible")
    except Exception as e:
        print(f"✗ Bucket check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bucket access error: {str(e)}")
    
    kwargs = {
        "Bucket": BUCKET,
        "Prefix": norm_prefix(prefix),
        "Delimiter": "/",
        "MaxKeys": 1000,
    }
    
    if token:
        kwargs["ContinuationToken"] = token
    
    print(f"Listing objects with: {kwargs}")
    resp = s3.list_objects_v2(**kwargs)
    
    folders = [cp["Prefix"] for cp in resp.get("CommonPrefixes", [])]
    files = [
        {"Key": o["Key"], "Size": o.get("Size", 0)}
        for o in resp.get("Contents", [])
        if o["Key"] != norm_prefix(prefix)
    ]
    
    return {
        "folders": folders,
        "files": files,
        "isTruncated": resp.get("IsTruncated", False),
        "nextToken": resp.get("NextContinuationToken"),
    }

def create_s3_folder(folder_name: str) -> dict:
    """Create an empty folder in S3 bucket"""
    # Ensure folder name ends with '/' to represent a folder
    folder_key = norm_prefix(folder_name)
    
    # Create empty object with folder key
    s3.put_object(Bucket=BUCKET, Key=folder_key)
    
    return {"ok": True, "folder": folder_key}

def delete_s3_object(key: str) -> dict:
    """Delete a single object from S3"""
    s3.delete_object(Bucket=BUCKET, Key=key)
    return {"ok": True, "deleted": key}

def rename_s3_object(old_key: str, new_key: str) -> dict:
    """Rename a single file (object) in S3 by copying to new key and deleting original"""
    try:
        # Copy the object to the new key
        s3.copy_object(
            Bucket=BUCKET,
            Key=new_key,
            CopySource={"Bucket": BUCKET, "Key": old_key}
        )
        
        # Delete the original object
        s3.delete_object(Bucket=BUCKET, Key=old_key)
        
        return {"ok": True, "message": f"Renamed {old_key} to {new_key}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename object: {str(e)}")

def rename_s3_folder(old_prefix: str, new_prefix: str) -> dict:
    """Rename a 'folder' in S3 by copying all objects with old prefix to new prefix"""
    try:
        old_p = norm_prefix(old_prefix)
        new_p = norm_prefix(new_prefix)
        
        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=BUCKET, Prefix=old_p)
        
        to_delete = []
        total_copied = 0
        
        for page in page_iterator:
            for obj in page.get("Contents", []):
                src_key = obj["Key"]
                # Calculate new key by replacing the old prefix with new prefix
                dst_key = new_p + src_key[len(old_p):]
                
                # Copy the object to new location
                s3.copy_object(
                    Bucket=BUCKET,
                    Key=dst_key,
                    CopySource={"Bucket": BUCKET, "Key": src_key}
                )
                
                to_delete.append({"Key": src_key})
                total_copied += 1
                
                # Delete in batches of 1000
                if len(to_delete) == 1000:
                    s3.delete_objects(
                        Bucket=BUCKET, 
                        Delete={"Objects": to_delete, "Quiet": True}
                    )
                    to_delete = []
        
        # Delete any remaining objects
        if to_delete:
            s3.delete_objects(
                Bucket=BUCKET, 
                Delete={"Objects": to_delete, "Quiet": True}
            )
        
        return {"ok": True, "message": f"Renamed folder {old_prefix} to {new_prefix}", "objectsRenamed": total_copied}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename folder: {str(e)}")

def delete_s3_folder(prefix: str) -> dict:
    """Delete all objects in a folder prefix"""
    p = norm_prefix(prefix)
    token = None
    total = 0
    
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": p, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
            
        page = s3.list_objects_v2(**kwargs)
        keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        
        # Delete in batches of 1000
        for i in range(0, len(keys), 1000):
            chunk = keys[i:i+1000]
            if chunk:
                s3.delete_objects(
                    Bucket=BUCKET, 
                    Delete={"Objects": chunk, "Quiet": True}
                )
                total += len(chunk)
        
        token = page.get("NextContinuationToken")
        if not token:
            break
    
    return {"ok": True, "deletedCount": total}

# Legacy function for backward compatibility
def get_files(folder_name: str):
    """Legacy function - use list_s3_objects instead"""
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=folder_name)
    return response.get('Contents', [])