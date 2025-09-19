# AWS Environment Setup

## Quick Fix for NoSuchBucket Error

Your bucket `explainer-videos-prod` exists in `us-west-2` region. Set these environment variables:

```bash
export AWS_REGION="us-west-2"
export S3_BUCKET="explainer-videos-prod"
export AWS_ACCESS_KEY_ID="your-access-key-here"
export AWS_SECRET_ACCESS_KEY="your-secret-key-here"
```

## Testing the Connection

1. Start your FastAPI server:
   ```bash
   uvicorn app:app --reload
   ```

2. Test the S3 connection:
   ```bash
   curl http://localhost:8000/s3/test
   ```

## Required AWS Permissions

Your IAM user/role needs these permissions:
- `s3:ListBucket`
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:GetBucketLocation`

## Alternative: Create IAM Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": "arn:aws:s3:::explainer-videos-prod"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::explainer-videos-prod/*"
        }
    ]
}
```
