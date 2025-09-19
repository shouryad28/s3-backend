from typing import List, Optional

from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from utils.s3_helper import (
    upload_file_to_s3, 
    list_s3_objects, 
    delete_s3_object, 
    delete_s3_folder,
    create_s3_folder,
    rename_s3_object,
    rename_s3_folder,
    get_files  # legacy function
)
load_dotenv()
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FolderRequest(BaseModel):
    folder_name: str

class RenameObjectRequest(BaseModel):
    old_key: str
    new_key: str

class RenameFolderRequest(BaseModel):
    old_prefix: str
    new_prefix: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/s3/test")
def test_s3_connection():
    """Test S3 connection and bucket access"""
    from utils.s3_helper import s3, BUCKET, AWS_REGION
    try:
        # Check bucket exists and is accessible
        s3.head_bucket(Bucket=BUCKET)
        
        # Try to list first few objects
        response = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=5)
        
        return {
            "status": "success",
            "bucket": BUCKET,
            "region": AWS_REGION,
            "bucket_accessible": True,
            "sample_objects": len(response.get("Contents", [])),
            "message": "S3 connection working properly"
        }
    except Exception as e:
        return {
            "status": "error", 
            "bucket": BUCKET,
            "region": AWS_REGION,
            "error": str(e),
            "bucket_accessible": False
        }

# New upload endpoint with multipart/form-data support
@app.post("/s3/upload")
async def upload(
    prefix: str = Form(""), 
    filename: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    return await upload_file_to_s3(file, prefix, filename)

# List objects with folder structure
@app.get("/s3/list")
def list_objects(
    prefix: str = Query("", description="e.g. 'assets/'"),
    token: Optional[str] = None
):
    return list_s3_objects(prefix, token)

# Delete single object
@app.delete("/s3/object")
def delete_object(key: str):
    return delete_s3_object(key)

# Delete folder (all objects with prefix)
@app.delete("/s3/folder")
def delete_folder(prefix: str):
    return delete_s3_folder(prefix)

# Create empty folder
@app.post("/s3/folder")
def create_folder(folder_name: FolderRequest):
    return create_s3_folder(folder_name.folder_name)

# Rename single file (object)
@app.put("/s3/object/rename")
def rename_object(request: RenameObjectRequest):
    return rename_s3_object(request.old_key, request.new_key)

# Rename folder (all objects with prefix)
@app.put("/s3/folder/rename")
def rename_folder(request: RenameFolderRequest):
    return rename_s3_folder(request.old_prefix, request.new_prefix)

# Legacy endpoints for backward compatibility
@app.get('/s3/get_files/{folder_name}')
def get_files_legacy(folder_name: str):
    files = get_files(folder_name)
    return files

@app.post('/s3/upload_file')
async def upload_file_legacy(file: UploadFile = File(...)):
    return await upload_file_to_s3(file)

