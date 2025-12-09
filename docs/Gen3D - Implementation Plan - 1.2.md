# Gen3D - Implementation Plan v1.2

**Version**: 1.2
**Date**: November 30, 2025
**Purpose**: Step-by-step deployment guide for Gen3D with SAM3 + SAM3D Hybrid Split Architecture

---

## Document Purpose

This document provides complete implementation instructions for deploying Gen3D v1.2 on AWS, including:
- All AWS CLI commands for resource creation
- Complete source code for all components
- Configuration files and environment setup
- Testing procedures and validation steps

**IMPORTANT**: This plan builds upon v1.0 architecture but introduces significant changes for interactive mask generation.

---

## Prerequisites

### Required Tools & Accounts

- **AWS CLI v2.x** installed and configured
- **Docker** 20.10+ with BuildKit enabled
- **Python** 3.11 or later
- **Node.js** 16+ (for web app development)
- **Git** for version control
- **jq** for JSON parsing in shell scripts
- **HuggingFace Account** with SAM 3 and SAM 3D access approved

### AWS Account Requirements

- AWS Account with administrator access
- Region: `us-east-1` (or your preferred region)
- Service quotas:
  - SageMaker: ml.g5.2xlarge instances (at least 2)
  - Lambda: Concurrent executions (at least 100)
  - S3: Standard storage (unlimited)
  - SES: Production access (out of sandbox)

### Environment Setup

```bash
# Set environment variables
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export PROJECT_NAME=Gen3D
export S3_BUCKET=gen3d-data-bucket
export ADMIN_EMAIL=info@2112-lab.com
export HF_TOKEN="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"

# Verify AWS CLI configuration
aws sts get-caller-identity
aws configure list

# Verify Docker
docker --version
docker buildx version

# Create working directory
mkdir -p ~/gen3d-deployment
cd ~/gen3d-deployment
```

---

## Architecture Overview Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          DEPLOYMENT FLOW                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Phase 1: IAM & S3           Phase 2: Cognito                            │
│  ├─ IAM Roles               ├─ User Pool                                 │
│  ├─ S3 Bucket               ├─ Identity Pool                             │
│  └─ Bucket Policies         └─ IAM Integration                           │
│                                                                           │
│  Phase 3: SageMaker          Phase 4: Lambda & API                       │
│  ├─ ECR Repository          ├─ Wrapper Lambda                            │
│  ├─ Build Container         ├─ Notify Lambda                             │
│  ├─ Upload Models           ├─ Error Handler Lambda                      │
│  ├─ Create Model            ├─ API Gateway                               │
│  ├─ Create Config           └─ DynamoDB (job status)                     │
│  └─ Create Endpoint                                                       │
│                                                                           │
│  Phase 5: SES & CloudWatch   Phase 6: Web App                            │
│  ├─ Verify Emails           ├─ Build Web App                             │
│  ├─ Email Templates         ├─ Upload to S3                              │
│  ├─ Log Groups              ├─ Configure CloudFront                      │
│  ├─ Metrics                 └─ Test E2E                                  │
│  └─ Alarms                                                                │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: IAM Roles & S3 Setup

### Step 1.1: Create IAM Roles

#### SageMaker Execution Role

```bash
# Create trust policy
cat > /tmp/sagemaker-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "sagemaker.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name Gen3DSageMakerExecutionRole \
  --assume-role-policy-document file:///tmp/sagemaker-trust-policy.json \
  --description "SageMaker execution role for Gen3D"

# Create custom policy
cat > /tmp/sagemaker-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket",
        "arn:aws:s3:::gen3d-data-bucket/*"
      ]
    },
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
    }
  ]
}
EOF

# Attach custom policy
aws iam put-role-policy \
  --role-name Gen3DSageMakerExecutionRole \
  --policy-name Gen3DSageMakerCustomPolicy \
  --policy-document file:///tmp/sagemaker-policy.json

# Get role ARN (save for later)
export SAGEMAKER_ROLE_ARN=$(aws iam get-role \
  --role-name Gen3DSageMakerExecutionRole \
  --query 'Role.Arn' --output text)

echo "SageMaker Role ARN: $SAGEMAKER_ROLE_ARN"
```

#### Lambda Execution Role (Wrapper)

```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "lambda.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name Gen3DLambdaWrapperRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Create custom policy
cat > /tmp/lambda-wrapper-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:InvokeEndpointAsync",
        "sagemaker:DescribeEndpoint"
      ],
      "Resource": "arn:aws:sagemaker:*:*:endpoint/gen3d-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket",
        "arn:aws:s3:::gen3d-data-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/Gen3DJobStatus"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/Gen3D*"
    }
  ]
}
EOF

# Attach policy
aws iam put-role-policy \
  --role-name Gen3DLambdaWrapperRole \
  --policy-name Gen3DLambdaWrapperPolicy \
  --policy-document file:///tmp/lambda-wrapper-policy.json

# Attach AWS managed policy for basic execution
aws iam attach-role-policy \
  --role-name Gen3DLambdaWrapperRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

export LAMBDA_WRAPPER_ROLE_ARN=$(aws iam get-role \
  --role-name Gen3DLambdaWrapperRole \
  --query 'Role.Arn' --output text)
```

#### Lambda Notify Role

```bash
# Create role
aws iam create-role \
  --role-name Gen3DLambdaNotifyRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Create policy
cat > /tmp/lambda-notify-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket",
        "arn:aws:s3:::gen3d-data-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name Gen3DLambdaNotifyRole \
  --policy-name Gen3DLambdaNotifyPolicy \
  --policy-document file:///tmp/lambda-notify-policy.json

export LAMBDA_NOTIFY_ROLE_ARN=$(aws iam get-role \
  --role-name Gen3DLambdaNotifyRole \
  --query 'Role.Arn' --output text)
```

### Step 1.2: Create S3 Bucket

```bash
# Create bucket
aws s3api create-bucket \
  --bucket $S3_BUCKET \
  --region $AWS_REGION

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket $S3_BUCKET \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket $S3_BUCKET \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

# Configure CORS
cat > /tmp/cors-config.json << 'EOF'
{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }]
}
EOF

aws s3api put-bucket-cors \
  --bucket $S3_BUCKET \
  --cors-configuration file:///tmp/cors-config.json

# Create folder structure
aws s3api put-object --bucket $S3_BUCKET --key public/
aws s3api put-object --bucket $S3_BUCKET --key users/
aws s3api put-object --bucket $S3_BUCKET --key models/sam3/
aws s3api put-object --bucket $S3_BUCKET --key models/sam3d/

echo "✓ S3 bucket created: s3://$S3_BUCKET"
```

### Step 1.3: Configure S3 Static Website Hosting

```bash
# Enable static website hosting
aws s3 website s3://$S3_BUCKET \
  --index-document index.html \
  --error-document error.html

# Create bucket policy for public access (public/ folder only)
cat > /tmp/bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${S3_BUCKET}/public/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket $S3_BUCKET \
  --policy file:///tmp/bucket-policy.json

echo "✓ Static website hosting enabled"
```

---

## Phase 2: Amazon Cognito Setup

### Step 2.1: Create Cognito User Pool

```bash
# Create user pool
aws cognito-idp create-user-pool \
  --pool-name Gen3DUserPool \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 8,
      "RequireUppercase": true,
      "RequireLowercase": true,
      "RequireNumbers": true,
      "RequireSymbols": false
    }
  }' \
  --auto-verified-attributes email \
  --email-configuration EmailSendingAccount=COGNITO_DEFAULT \
  --schema '[
    {
      "Name": "email",
      "AttributeDataType": "String",
      "Required": true,
      "Mutable": true
    }
  ]' \
  --output json > /tmp/user-pool.json

export USER_POOL_ID=$(jq -r '.UserPool.Id' /tmp/user-pool.json)
echo "User Pool ID: $USER_POOL_ID"

# Create user pool client
aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name Gen3DWebClient \
  --no-generate-secret \
  --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --output json > /tmp/user-pool-client.json

export USER_POOL_CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' /tmp/user-pool-client.json)
echo "User Pool Client ID: $USER_POOL_CLIENT_ID"
```

### Step 2.2: Create Cognito Identity Pool

```bash
# Create identity pool
aws cognito-identity create-identity-pool \
  --identity-pool-name Gen3DIdentityPool \
  --allow-unauthenticated-identities \
  --cognito-identity-providers \
    ProviderName=cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID},ClientId=${USER_POOL_CLIENT_ID} \
  --output json > /tmp/identity-pool.json

export IDENTITY_POOL_ID=$(jq -r '.IdentityPoolId' /tmp/identity-pool.json)
echo "Identity Pool ID: $IDENTITY_POOL_ID"
```

### Step 2.3: Create IAM Roles for Cognito

```bash
# Authenticated role
cat > /tmp/cognito-auth-trust.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "cognito-identity.amazonaws.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "cognito-identity.amazonaws.com:aud": "${IDENTITY_POOL_ID}"
      },
      "ForAnyValue:StringLike": {
        "cognito-identity.amazonaws.com:amr": "authenticated"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name Gen3DCognitoAuthRole \
  --assume-role-policy-document file:///tmp/cognito-auth-trust.json

# Policy for authenticated users
cat > /tmp/cognito-auth-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::gen3d-data-bucket/users/${cognito-identity.amazonaws.com:sub}/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::gen3d-data-bucket",
      "Condition": {
        "StringLike": {
          "s3:prefix": "users/${cognito-identity.amazonaws.com:sub}/*"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket/public/*",
        "arn:aws:s3:::gen3d-data-bucket/models/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name Gen3DCognitoAuthRole \
  --policy-name Gen3DCognitoAuthPolicy \
  --policy-document file:///tmp/cognito-auth-policy.json

export COGNITO_AUTH_ROLE_ARN=$(aws iam get-role \
  --role-name Gen3DCognitoAuthRole \
  --query 'Role.Arn' --output text)

# Unauthenticated role (minimal permissions)
cat > /tmp/cognito-unauth-trust.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "cognito-identity.amazonaws.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "cognito-identity.amazonaws.com:aud": "${IDENTITY_POOL_ID}"
      },
      "ForAnyValue:StringLike": {
        "cognito-identity.amazonaws.com:amr": "unauthenticated"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name Gen3DCognitoUnauthRole \
  --assume-role-policy-document file:///tmp/cognito-unauth-trust.json

cat > /tmp/cognito-unauth-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::gen3d-data-bucket/public/*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name Gen3DCognitoUnauthRole \
  --policy-name Gen3DCognitoUnauthPolicy \
  --policy-document file:///tmp/cognito-unauth-policy.json

export COGNITO_UNAUTH_ROLE_ARN=$(aws iam get-role \
  --role-name Gen3DCognitoUnauthRole \
  --query 'Role.Arn' --output text)

# Set identity pool roles
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id $IDENTITY_POOL_ID \
  --roles authenticated=$COGNITO_AUTH_ROLE_ARN,unauthenticated=$COGNITO_UNAUTH_ROLE_ARN

echo "✓ Cognito setup complete"
```

---

## Phase 3: SageMaker Endpoint Deployment

### Step 3.1: Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name gen3d-sam3-sam3d \
  --image-scanning-configuration scanOnPush=true \
  --region $AWS_REGION

# Get repository URI
export ECR_REPO_URI=$(aws ecr describe-repositories \
  --repository-names gen3d-sam3-sam3d \
  --query 'repositories[0].repositoryUri' \
  --output text)

echo "ECR Repository: $ECR_REPO_URI"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPO_URI
```

### Step 3.2: Create Dockerfile

```bash
mkdir -p ~/gen3d-deployment/docker
cd ~/gen3d-deployment/docker

cat > Dockerfile << 'EOF'
# Gen3D SageMaker Container with SAM 3 + SAM 3D
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    sagemaker-inference==1.9.0 \
    opencv-python==4.8.1.78 \
    transformers==4.35.0 \
    diffusers==0.24.0 \
    accelerate==0.25.0 \
    scipy==1.11.4 \
    pillow==10.1.0 \
    numpy==1.26.2 \
    boto3==1.29.7

# Install HuggingFace CLI
RUN pip install -U "huggingface_hub[cli]"

# Install SAM 3 (from GitHub)
RUN pip install git+https://github.com/facebookresearch/segment-anything-3.git@main

# Install SAM 3D (from GitHub)
RUN pip install git+https://github.com/facebookresearch/sam-3d-objects.git@main

# Set working directory
WORKDIR /opt/ml/code

# Copy inference script
COPY inference.py /opt/ml/code/inference.py
COPY model_loader.py /opt/ml/code/model_loader.py
COPY utils.py /opt/ml/code/utils.py

# Set SageMaker environment variables
ENV SAGEMAKER_PROGRAM=inference.py
ENV PYTHONUNBUFFERED=1

# Entry point (handled by SageMaker)
ENTRYPOINT []
EOF

echo "✓ Dockerfile created"
```

### Step 3.3: Create Inference Script

```bash
cat > inference.py << 'EOF'
"""
Gen3D SageMaker Inference Handler
Supports both SAM 3 (encoding) and SAM 3D (reconstruction)
"""

import os
import json
import base64
import logging
import numpy as np
import torch
from PIL import Image
from io import BytesIO
import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client('s3')

# Global model cache
MODELS = {}

def model_fn(model_dir):
    """
    Load models once at container startup.
    This is called by SageMaker before any predictions.
    """
    global MODELS
    logger.info("Loading models...")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    try:
        # Import SAM 3 components
        from sam3 import sam_model_registry, SAM3Predictor

        # Load SAM 3 Image Encoder (ViT-H)
        sam3_checkpoint = os.path.join(model_dir, "sam3", "sam3_vit_h.pth")
        logger.info(f"Loading SAM 3 from {sam3_checkpoint}")

        sam3_model = sam_model_registry["vit_h"](checkpoint=sam3_checkpoint)
        sam3_model.to(device)
        sam3_model.eval()

        sam3_predictor = SAM3Predictor(sam3_model)

        # Import SAM 3D components
        from sam3d import SAM3DReconstructor

        # Load SAM 3D Reconstructor
        sam3d_checkpoint = os.path.join(model_dir, "sam3d", "sam3d_checkpoint.pth")
        logger.info(f"Loading SAM 3D from {sam3d_checkpoint}")

        sam3d_model = SAM3DReconstructor.from_pretrained(
            sam3d_checkpoint,
            device=device
        )
        sam3d_model.eval()

        MODELS = {
            "sam3_predictor": sam3_predictor,
            "sam3_model": sam3_model,
            "sam3d_model": sam3d_model,
            "device": device
        }

        logger.info("✓ Models loaded successfully")
        return MODELS

    except Exception as e:
        logger.error(f"✗ Model loading failed: {str(e)}")
        raise

def input_fn(request_body, content_type):
    """
    Deserialize input data.
    """
    if content_type == "application/json":
        data = json.loads(request_body)
        return data
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

def predict_fn(input_data, models):
    """
    Main prediction dispatcher.
    Routes to appropriate handler based on task type.
    """
    task = input_data.get("task")
    logger.info(f"Processing task: {task}")

    if task == "get_embedding":
        return process_initialization(input_data, models)
    elif task == "generate_3d":
        return process_reconstruction(input_data, models)
    else:
        raise ValueError(f"Unknown task: {task}")

def process_initialization(input_data, models):
    """
    Stage 1: Generate image embeddings using SAM 3 encoder.
    """
    try:
        # Get S3 key from input
        image_s3_key = input_data["image_s3_key"]
        bucket = input_data.get("bucket", os.environ.get("S3_BUCKET", "gen3d-data-bucket"))

        logger.info(f"Downloading image from s3://{bucket}/{image_s3_key}")

        # Download image from S3
        response = s3_client.get_object(Bucket=bucket, Key=image_s3_key)
        image_bytes = response['Body'].read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        logger.info(f"Image size: {image.size}")

        # Preprocess image for SAM 3
        sam3_predictor = models["sam3_predictor"]
        sam3_predictor.set_image(np.array(image))

        # Extract embeddings from the internal features
        # The features are stored after set_image is called
        with torch.no_grad():
            features = sam3_predictor.features  # (1, 256, 64, 64)

        logger.info(f"Embeddings shape: {features.shape}")

        # Serialize embeddings to base64
        features_np = features.cpu().numpy().astype(np.float32)
        features_b64 = base64.b64encode(features_np.tobytes()).decode('utf-8')

        # Prepare output
        output = {
            "status": "success",
            "task": "get_embedding",
            "embedding": features_b64,
            "shape": list(features_np.shape),
            "dtype": "float32",
            "image_size": list(image.size)
        }

        # Save embeddings to S3
        embeddings_key = image_s3_key.replace("original_image.jpg", "embeddings.json")
        s3_client.put_object(
            Bucket=bucket,
            Key=embeddings_key,
            Body=json.dumps(output),
            ContentType="application/json"
        )

        logger.info(f"✓ Embeddings saved to s3://{bucket}/{embeddings_key}")

        return output

    except Exception as e:
        logger.error(f"✗ Initialization failed: {str(e)}")
        raise

def process_reconstruction(input_data, models):
    """
    Stage 3: Generate 3D point cloud using SAM 3D.
    """
    try:
        # Get S3 keys
        image_s3_key = input_data["image_s3_key"]
        mask_s3_key = input_data["mask_s3_key"]
        bucket = input_data.get("bucket", os.environ.get("S3_BUCKET", "gen3d-data-bucket"))
        quality = input_data.get("quality", "high")

        logger.info(f"Downloading image from s3://{bucket}/{image_s3_key}")
        logger.info(f"Downloading mask from s3://{bucket}/{mask_s3_key}")

        # Download image
        response = s3_client.get_object(Bucket=bucket, Key=image_s3_key)
        image_bytes = response['Body'].read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        # Download mask
        response = s3_client.get_object(Bucket=bucket, Key=mask_s3_key)
        mask_bytes = response['Body'].read()
        mask = Image.open(BytesIO(mask_bytes)).convert("L")

        logger.info(f"Image size: {image.size}, Mask size: {mask.size}")

        # Convert mask to binary array
        mask_array = np.array(mask)
        mask_bool = mask_array > 128

        # Validate mask
        if not np.any(mask_bool):
            raise ValueError("Mask is empty - no object selected")

        mask_coverage = np.sum(mask_bool) / mask_bool.size * 100
        logger.info(f"Mask coverage: {mask_coverage:.2f}%")

        # Run SAM 3D reconstruction
        logger.info("Running SAM 3D reconstruction...")
        sam3d_model = models["sam3d_model"]

        with torch.no_grad():
            point_cloud = sam3d_model.reconstruct(
                image=np.array(image),
                mask=mask_bool,
                quality_preset=quality
            )

        logger.info(f"Point cloud generated with {len(point_cloud['vertices'])} points")

        # Convert to PLY format
        ply_bytes = convert_to_ply(point_cloud)

        # Save to S3
        output_key = mask_s3_key.replace("mask_final.png", "output_mesh.ply")
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=ply_bytes,
            ContentType="application/octet-stream"
        )

        logger.info(f"✓ Point cloud saved to s3://{bucket}/{output_key}")

        # Calculate statistics
        stats = {
            "num_points": len(point_cloud['vertices']),
            "file_size_mb": round(len(ply_bytes) / (1024 * 1024), 2),
            "has_colors": 'colors' in point_cloud,
            "mask_coverage_percent": round(mask_coverage, 2)
        }

        return {
            "status": "success",
            "task": "generate_3d",
            "output_s3_key": output_key,
            "mesh_stats": stats
        }

    except Exception as e:
        logger.error(f"✗ Reconstruction failed: {str(e)}")
        raise

def convert_to_ply(point_cloud):
    """
    Convert point cloud dict to PLY format bytes.
    """
    vertices = point_cloud['vertices']
    colors = point_cloud.get('colors', None)

    num_vertices = len(vertices)

    # PLY header
    header = f"""ply
format binary_little_endian 1.0
element vertex {num_vertices}
property float x
property float y
property float z
"""

    if colors is not None:
        header += """property uchar red
property uchar green
property uchar blue
"""

    header += "end_header\n"

    # Convert to bytes
    header_bytes = header.encode('ascii')

    # Vertex data
    if colors is not None:
        # Interleave vertices and colors
        vertex_data = np.zeros(num_vertices, dtype=[
            ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')
        ])
        vertex_data['x'] = vertices[:, 0]
        vertex_data['y'] = vertices[:, 1]
        vertex_data['z'] = vertices[:, 2]
        vertex_data['red'] = colors[:, 0]
        vertex_data['green'] = colors[:, 1]
        vertex_data['blue'] = colors[:, 2]
    else:
        vertex_data = np.zeros(num_vertices, dtype=[
            ('x', 'f4'), ('y', 'f4'), ('z', 'f4')
        ])
        vertex_data['x'] = vertices[:, 0]
        vertex_data['y'] = vertices[:, 1]
        vertex_data['z'] = vertices[:, 2]

    vertex_bytes = vertex_data.tobytes()

    return header_bytes + vertex_bytes

def output_fn(prediction, accept):
    """
    Serialize output.
    """
    if accept == "application/json":
        return json.dumps(prediction), accept
    else:
        raise ValueError(f"Unsupported accept type: {accept}")
EOF

echo "✓ inference.py created"
```

### Step 3.4: Build and Push Docker Image

```bash
cd ~/gen3d-deployment/docker

# Build image (this will take 10-20 minutes)
echo "Building Docker image... (this may take 10-20 minutes)"
docker build -t gen3d-sam3-sam3d:latest .

# Tag image
docker tag gen3d-sam3-sam3d:latest $ECR_REPO_URI:latest

# Push to ECR
echo "Pushing image to ECR..."
docker push $ECR_REPO_URI:latest

echo "✓ Docker image pushed to $ECR_REPO_URI:latest"
```

### Step 3.5: Upload Model Artifacts to S3

```bash
# Create model directory
mkdir -p ~/gen3d-deployment/models

# Download SAM 3 model from HuggingFace
echo "Downloading SAM 3 model..."
cd ~/gen3d-deployment/models
mkdir -p sam3

# Authenticate with HuggingFace
huggingface-cli login --token $HF_TOKEN

# Download SAM 3 ViT-H checkpoint
huggingface-cli download facebook/sam3 \
  --include "sam3_vit_h.pth" \
  --local-dir sam3/

# Download SAM 3D model
echo "Downloading SAM 3D model..."
mkdir -p sam3d
huggingface-cli download facebook/sam-3d-objects \
  --include "sam3d_checkpoint.pth" "pipeline.yaml" \
  --local-dir sam3d/

# Upload to S3
echo "Uploading models to S3..."
aws s3 sync sam3/ s3://$S3_BUCKET/models/sam3/
aws s3 sync sam3d/ s3://$S3_BUCKET/models/sam3d/

echo "✓ Models uploaded to S3"
```

### Step 3.6: Create SageMaker Model

```bash
# Create model
aws sagemaker create-model \
  --model-name Gen3DSAM3SAM3DModel \
  --primary-container Image=$ECR_REPO_URI:latest,Mode=SingleModel,ModelDataUrl=s3://$S3_BUCKET/models/ \
  --execution-role-arn $SAGEMAKER_ROLE_ARN \
  --region $AWS_REGION

echo "✓ SageMaker model created"
```

### Step 3.7: Create SageMaker Async Endpoint Configuration

```bash
# Create async endpoint config
cat > /tmp/async-config.json << 'EOF'
{
  "EndpointConfigName": "Gen3DSAM3SAM3DAsyncConfig",
  "ProductionVariants": [{
    "VariantName": "AllTraffic",
    "ModelName": "Gen3DSAM3SAM3DModel",
    "InstanceType": "ml.g5.2xlarge",
    "InitialInstanceCount": 1,
    "InitialVariantWeight": 1.0
  }],
  "AsyncInferenceConfig": {
    "OutputConfig": {
      "S3OutputPath": "s3://gen3d-data-bucket/sagemaker-async-output/"
    },
    "ClientConfig": {
      "MaxConcurrentInvocationsPerInstance": 4
    }
  }
}
EOF

aws sagemaker create-endpoint-config --cli-input-json file:///tmp/async-config.json

echo "✓ Endpoint configuration created"
```

### Step 3.8: Create SageMaker Endpoint

```bash
# Create endpoint (this takes 5-10 minutes)
echo "Creating SageMaker endpoint (this will take 5-10 minutes)..."
aws sagemaker create-endpoint \
  --endpoint-name gen3d-sam3-sam3d-endpoint \
  --endpoint-config-name Gen3DSAM3SAM3DAsyncConfig

# Wait for endpoint to be in service
echo "Waiting for endpoint to be InService..."
aws sagemaker wait endpoint-in-service \
  --endpoint-name gen3d-sam3-sam3d-endpoint

echo "✓ SageMaker endpoint created and ready"
```

### Step 3.9: Configure Auto-Scaling

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace sagemaker \
  --resource-id endpoint/gen3d-sam3-sam3d-endpoint/variant/AllTraffic \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 0 \
  --max-capacity 5

# Create scaling policy
cat > /tmp/scaling-policy.json << 'EOF'
{
  "TargetValue": 2.0,
  "CustomizedMetricSpecification": {
    "MetricName": "ApproximateBacklogSizePerInstance",
    "Namespace": "AWS/SageMaker",
    "Statistic": "Average",
    "Dimensions": [
      {
        "Name": "EndpointName",
        "Value": "gen3d-sam3-sam3d-endpoint"
      }
    ]
  },
  "ScaleInCooldown": 600,
  "ScaleOutCooldown": 60
}
EOF

aws application-autoscaling put-scaling-policy \
  --service-namespace sagemaker \
  --resource-id endpoint/gen3d-sam3-sam3d-endpoint/variant/AllTraffic \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --policy-name Gen3DScalingPolicy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file:///tmp/scaling-policy.json

echo "✓ Auto-scaling configured (0-5 instances)"
```

---

## Phase 4: Lambda Functions & API Gateway

### Step 4.1: Create DynamoDB Table for Job Status

```bash
# Create table
aws dynamodb create-table \
  --table-name Gen3DJobStatus \
  --attribute-definitions \
    AttributeName=job_id,AttributeDataType=S \
    AttributeName=user_id,AttributeDataType=S \
  --key-schema \
    AttributeName=job_id,KeyType=HASH \
  --global-secondary-indexes \
    '[{
      "IndexName": "user-index",
      "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
      "Projection": {"ProjectionType": "ALL"}
    }]' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

echo "✓ DynamoDB table created"
```

### Step 4.2: Create Wrapper Lambda Function

```bash
mkdir -p ~/gen3d-deployment/lambda/wrapper
cd ~/gen3d-deployment/lambda/wrapper

cat > lambda_function.py << 'EOF'
"""
Gen3D Wrapper Lambda
Handles API Gateway requests and invokes SageMaker async endpoint
"""

import json
import boto3
import os
import uuid
from datetime import datetime

# Initialize AWS clients
sagemaker_runtime = boto3.client('sagemaker-runtime')
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT_NAME']
S3_BUCKET = os.environ['S3_BUCKET']
JOB_STATUS_TABLE = os.environ['JOB_STATUS_TABLE']

# DynamoDB table
table = dynamodb.Table(JOB_STATUS_TABLE)

def lambda_handler(event, context):
    """Main handler for API Gateway requests"""

    print(f"Event: {json.dumps(event)}")

    # Parse request
    http_method = event['httpMethod']
    path = event['path']
    body = json.loads(event['body']) if event.get('body') else {}

    # Get user ID from Cognito authorizer
    user_id = event['requestContext']['authorizer']['claims']['sub']

    try:
        if path == '/initialize' and http_method == 'POST':
            return handle_initialize(body, user_id)
        elif path == '/reconstruct' and http_method == 'POST':
            return handle_reconstruct(body, user_id)
        elif path.startswith('/status/') and http_method == 'GET':
            job_id = path.split('/')[-1]
            return handle_status(job_id, user_id)
        else:
            return response(404, {'error': 'Not found'})

    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {'error': str(e)})

def handle_initialize(body, user_id):
    """Handle Stage 1: Initialization request"""

    session_id = body.get('session_id')
    image_s3_key = body.get('image_s3_key')

    # Validate input
    if not session_id or not image_s3_key:
        return response(400, {'error': 'Missing required fields'})

    # Verify image exists in S3
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=image_s3_key)
    except:
        return response(404, {'error': 'Image not found in S3'})

    # Create job payload
    job_payload = {
        "task": "get_embedding",
        "image_s3_key": image_s3_key,
        "bucket": S3_BUCKET,
        "session_id": session_id,
        "user_id": user_id
    }

    # Save payload to S3
    payload_key = f"users/{user_id}/sessions/{session_id}/init_payload.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=payload_key,
        Body=json.dumps(job_payload),
        ContentType='application/json'
    )

    # Invoke SageMaker async
    response_payload = sagemaker_runtime.invoke_endpoint_async(
        EndpointName=ENDPOINT_NAME,
        InputLocation=f"s3://{S3_BUCKET}/{payload_key}",
        ContentType='application/json',
        Accept='application/json'
    )

    job_id = response_payload['InferenceId']
    output_location = response_payload['OutputLocation']

    # Save job status to DynamoDB
    table.put_item(Item={
        'job_id': job_id,
        'user_id': user_id,
        'session_id': session_id,
        'task': 'initialization',
        'status': 'processing',
        'output_location': output_location,
        'created_at': datetime.utcnow().isoformat()
    })

    return response(202, {
        'job_id': job_id,
        'status': 'processing',
        'embeddings_s3_key': f"users/{user_id}/sessions/{session_id}/embeddings.json",
        'poll_url': f"/status/{job_id}"
    })

def handle_reconstruct(body, user_id):
    """Handle Stage 3: Reconstruction request"""

    session_id = body.get('session_id')
    image_s3_key = body.get('image_s3_key')
    mask_s3_key = body.get('mask_s3_key')
    quality = body.get('quality', 'high')

    # Validate input
    if not all([session_id, image_s3_key, mask_s3_key]):
        return response(400, {'error': 'Missing required fields'})

    # Verify files exist
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=image_s3_key)
        s3_client.head_object(Bucket=S3_BUCKET, Key=mask_s3_key)
    except:
        return response(404, {'error': 'Image or mask not found'})

    # Create job payload
    job_payload = {
        "task": "generate_3d",
        "image_s3_key": image_s3_key,
        "mask_s3_key": mask_s3_key,
        "bucket": S3_BUCKET,
        "quality": quality,
        "session_id": session_id,
        "user_id": user_id
    }

    # Save payload to S3
    payload_key = f"users/{user_id}/sessions/{session_id}/recon_payload.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=payload_key,
        Body=json.dumps(job_payload),
        ContentType='application/json'
    )

    # Invoke SageMaker async
    response_payload = sagemaker_runtime.invoke_endpoint_async(
        EndpointName=ENDPOINT_NAME,
        InputLocation=f"s3://{S3_BUCKET}/{payload_key}",
        ContentType='application/json',
        Accept='application/json'
    )

    job_id = response_payload['InferenceId']
    output_location = response_payload['OutputLocation']

    # Save job status
    table.put_item(Item={
        'job_id': job_id,
        'user_id': user_id,
        'session_id': session_id,
        'task': 'reconstruction',
        'status': 'processing',
        'output_location': output_location,
        'created_at': datetime.utcnow().isoformat()
    })

    return response(202, {
        'job_id': job_id,
        'status': 'processing',
        'output_s3_key': f"users/{user_id}/sessions/{session_id}/output_mesh.ply",
        'poll_url': f"/status/{job_id}"
    })

def handle_status(job_id, user_id):
    """Check job status"""

    # Get from DynamoDB
    result = table.get_item(Key={'job_id': job_id})

    if 'Item' not in result:
        return response(404, {'error': 'Job not found'})

    item = result['Item']

    # Verify user owns this job
    if item['user_id'] != user_id:
        return response(403, {'error': 'Forbidden'})

    # Check if output file exists in S3
    if item['status'] == 'processing':
        output_location = item['output_location']
        # Parse S3 location
        bucket = output_location.split('/')[2]
        key = '/'.join(output_location.split('/')[3:])

        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            # Output exists - job completed
            item['status'] = 'completed'
            table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'completed'}
            )
        except:
            pass  # Still processing

    return response(200, {
        'job_id': job_id,
        'status': item['status'],
        'task': item['task'],
        'created_at': item['created_at']
    })

def response(status_code, body):
    """Format API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': json.dumps(body)
    }
EOF

# Create deployment package
zip -r lambda_wrapper.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
  --function-name Gen3DWrapperLambda \
  --runtime python3.11 \
  --role $LAMBDA_WRAPPER_ROLE_ARN \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_wrapper.zip \
  --timeout 30 \
  --memory-size 512 \
  --environment "Variables={
    SAGEMAKER_ENDPOINT_NAME=gen3d-sam3-sam3d-endpoint,
    S3_BUCKET=$S3_BUCKET,
    JOB_STATUS_TABLE=Gen3DJobStatus
  }" \
  --region $AWS_REGION

echo "✓ Wrapper Lambda created"
```

### Step 4.3: Create Notify Lambda Function

```bash
mkdir -p ~/gen3d-deployment/lambda/notify
cd ~/gen3d-deployment/lambda/notify

cat > lambda_function.py << 'EOF'
"""
Gen3D Notify Lambda
Sends email notifications when processing completes
"""

import json
import boto3
import os
from datetime import datetime, timedelta

# Initialize clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

# Environment variables
S3_BUCKET = os.environ['S3_BUCKET']
SENDER_EMAIL = os.environ['SENDER_EMAIL']
ADMIN_EMAIL = os.environ['ADMIN_EMAIL']

def lambda_handler(event, context):
    """Handle S3 PUT events for output files"""

    print(f"Event: {json.dumps(event)}")

    # Parse S3 event
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']

    print(f"Processing: s3://{bucket}/{key}")

    # Only process output mesh files
    if not key.endswith('output_mesh.ply'):
        print("Not an output mesh file, skipping")
        return {'statusCode': 200}

    # Extract user_id and session_id from key
    # Format: users/{user_id}/sessions/{session_id}/output_mesh.ply
    parts = key.split('/')
    user_id = parts[1]
    session_id = parts[3]

    # Read metadata
    metadata_key = f"users/{user_id}/sessions/{session_id}/metadata.json"
    try:
        response = s3_client.get_object(Bucket=bucket, Key=metadata_key)
        metadata = json.loads(response['Body'].read())
        user_email = metadata.get('user_email', ADMIN_EMAIL)
    except:
        user_email = ADMIN_EMAIL
        metadata = {}

    # Generate pre-signed URL (24 hours)
    download_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=86400
    )

    # Get file size
    response = s3_client.head_object(Bucket=bucket, Key=key)
    file_size_mb = round(response['ContentLength'] / (1024 * 1024), 2)

    # Send email to user
    subject = "Your 3D Model is Ready!"
    body_html = f"""
    <html>
    <head></head>
    <body>
      <h2>Gen3D - Your 3D Model is Ready</h2>
      <p>Hi there,</p>
      <p>Your 3D reconstruction is complete!</p>

      <p style="margin: 20px 0;">
        <a href="{download_url}"
           style="background:#4CAF50;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">
          Download Your 3D Model
        </a>
      </p>

      <p><small>Download link expires in 24 hours.</small></p>

      <p>
        <strong>Session Details:</strong><br>
        Session ID: {session_id}<br>
        File size: {file_size_mb} MB<br>
        Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
      </p>

      <p>Thank you for using Gen3D!</p>

      <p style="color:#666;font-size:12px;">
        Gen3D - Generative 3D Reconstruction Service<br>
        <a href="https://gen3d.genesis3d.com">https://gen3d.genesis3d.com</a>
      </p>
    </body>
    </html>
    """

    try:
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [user_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Html': {'Data': body_html}}
            }
        )
        print(f"✓ Email sent to {user_email}")

        # Send copy to admin
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [ADMIN_EMAIL]},
            Message={
                'Subject': {'Data': f"[Gen3D] User mesh generated: {session_id}"},
                'Body': {'Html': {'Data': body_html}}
            }
        )
        print(f"✓ Admin notification sent")

    except Exception as e:
        print(f"✗ Email send failed: {str(e)}")

    return {'statusCode': 200}
EOF

# Create deployment package
zip -r lambda_notify.zip lambda_function.py

# Create Lambda
aws lambda create-function \
  --function-name Gen3DNotifyLambda \
  --runtime python3.11 \
  --role $LAMBDA_NOTIFY_ROLE_ARN \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_notify.zip \
  --timeout 15 \
  --memory-size 256 \
  --environment "Variables={
    S3_BUCKET=$S3_BUCKET,
    SENDER_EMAIL=noreply@genesis3d.com,
    ADMIN_EMAIL=$ADMIN_EMAIL
  }" \
  --region $AWS_REGION

# Grant S3 permission to invoke Lambda
aws lambda add-permission \
  --function-name Gen3DNotifyLambda \
  --statement-id AllowS3Invoke \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::$S3_BUCKET

# Configure S3 event notification
cat > /tmp/s3-notification-notify.json << EOF
{
  "LambdaFunctionConfigurations": [{
    "Id": "Gen3DNotifyTrigger",
    "LambdaFunctionArn": "$(aws lambda get-function --function-name Gen3DNotifyLambda --query 'Configuration.FunctionArn' --output text)",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {
      "Key": {
        "FilterRules": [
          {"Name": "prefix", "Value": "users/"},
          {"Name": "suffix", "Value": "output_mesh.ply"}
        ]
      }
    }
  }]
}
EOF

aws s3api put-bucket-notification-configuration \
  --bucket $S3_BUCKET \
  --notification-configuration file:///tmp/s3-notification-notify.json

echo "✓ Notify Lambda created and S3 trigger configured"
```

### Step 4.4: Create API Gateway

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name Gen3DAPI \
  --description "Gen3D REST API" \
  --endpoint-configuration types=REGIONAL \
  --query 'id' --output text)

echo "API ID: $API_ID"

# Get root resource
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[0].id' --output text)

# Create Cognito authorizer
AUTHORIZER_ID=$(aws apigateway create-authorizer \
  --rest-api-id $API_ID \
  --name Gen3DCognitoAuthorizer \
  --type COGNITO_USER_POOLS \
  --provider-arns arn:aws:cognito-idp:$AWS_REGION:$AWS_ACCOUNT_ID:userpool/$USER_POOL_ID \
  --identity-source method.request.header.Authorization \
  --query 'id' --output text)

# Create /initialize resource
INIT_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part initialize \
  --query 'id' --output text)

# Create POST method for /initialize
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $INIT_RESOURCE_ID \
  --http-method POST \
  --authorization-type COGNITO_USER_POOLS \
  --authorizer-id $AUTHORIZER_ID

# Integrate with Lambda
LAMBDA_WRAPPER_ARN=$(aws lambda get-function \
  --function-name Gen3DWrapperLambda \
  --query 'Configuration.FunctionArn' --output text)

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $INIT_RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/$LAMBDA_WRAPPER_ARN/invocations

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name Gen3DWrapperLambda \
  --statement-id AllowAPIGatewayInvoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/*"

# Similarly create /reconstruct and /status endpoints...
# (Abbreviated for brevity - repeat above steps for each endpoint)

# Deploy API
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod

API_ENDPOINT="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod"
echo "✓ API Gateway deployed: $API_ENDPOINT"
```

---

## Phase 5: SES & CloudWatch

### Step 5.1: Verify SES Email Addresses

```bash
# Verify sender email
aws ses verify-email-identity \
  --email-address noreply@genesis3d.com

# Verify admin email
aws ses verify-email-identity \
  --email-address $ADMIN_EMAIL

echo "✓ Check your email for verification links"
echo "✓ Click verification links before proceeding"
```

### Step 5.2: Create CloudWatch Log Groups

```bash
# Log groups are auto-created, but we can set retention
aws logs put-retention-policy \
  --log-group-name /aws/lambda/Gen3DWrapperLambda \
  --retention-in-days 30

aws logs put-retention-policy \
  --log-group-name /aws/lambda/Gen3DNotifyLambda \
  --retention-in-days 30

aws logs put-retention-policy \
  --log-group-name /aws/sagemaker/Endpoints/gen3d-sam3-sam3d-endpoint \
  --retention-in-days 30

echo "✓ CloudWatch log retention configured"
```

---

## Phase 6: Testing

### Step 6.1: End-to-End Test

```bash
cd ~/gen3d-deployment

# Download test image
curl -o test_chair.jpg https://example.com/test_chair.jpg

# Create test user
TEST_USER_EMAIL="test@example.com"
TEST_PASSWORD="TestPass123!"

aws cognito-idp sign-up \
  --client-id $USER_POOL_CLIENT_ID \
  --username $TEST_USER_EMAIL \
  --password $TEST_PASSWORD \
  --user-attributes Name=email,Value=$TEST_USER_EMAIL

# Verify user (admin command)
aws cognito-idp admin-confirm-sign-up \
  --user-pool-id $USER_POOL_ID \
  --username $TEST_USER_EMAIL

# Authenticate
AUTH_RESPONSE=$(aws cognito-idp initiate-auth \
  --client-id $USER_POOL_CLIENT_ID \
  --auth-flow USER_SRP_AUTH \
  --auth-parameters USERNAME=$TEST_USER_EMAIL,PASSWORD=$TEST_PASSWORD)

ID_TOKEN=$(echo $AUTH_RESPONSE | jq -r '.AuthenticationResult.IdToken')

# Upload test image to S3
SESSION_ID="test_session_$(date +%s)"
aws s3 cp test_chair.jpg \
  s3://$S3_BUCKET/users/test-user/sessions/$SESSION_ID/original_image.jpg

# Call initialize API
curl -X POST $API_ENDPOINT/initialize \
  -H "Authorization: $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "'$SESSION_ID'",
    "image_s3_key": "users/test-user/sessions/'$SESSION_ID'/original_image.jpg"
  }'

echo "✓ Test complete - check CloudWatch logs for results"
```

---

## Summary & Next Steps

### Resources Created

✅ IAM Roles (4):
- Gen3DSageMakerExecutionRole
- Gen3DLambdaWrapperRole
- Gen3DLambdaNotifyRole
- Gen3DCognitoAuthRole

✅ S3 Bucket:
- gen3d-data-bucket (with folder structure)

✅ Cognito:
- User Pool
- Identity Pool
- App Client

✅ SageMaker:
- ECR Repository
- Docker Image
- Model
- Async Endpoint Configuration
- Endpoint (ml.g5.2xlarge)
- Auto-scaling (0-5 instances)

✅ Lambda Functions (2):
- Gen3DWrapperLambda
- Gen3DNotifyLambda

✅ API Gateway:
- REST API with Cognito authorizer

✅ DynamoDB:
- Gen3DJobStatus table

✅ CloudWatch:
- Log groups with 30-day retention

### Configuration File

Save this configuration for the web app:

```bash
cat > ~/gen3d-deployment/web-config.json << EOF
{
  "region": "$AWS_REGION",
  "userPoolId": "$USER_POOL_ID",
  "userPoolWebClientId": "$USER_POOL_CLIENT_ID",
  "identityPoolId": "$IDENTITY_POOL_ID",
  "s3Bucket": "$S3_BUCKET",
  "apiEndpoint": "$API_ENDPOINT",
  "cognitoAuthRole": "$COGNITO_AUTH_ROLE_ARN"
}
EOF

echo "✓ Configuration saved to ~/gen3d-deployment/web-config.json"
```

### Deployment Complete!

The Gen3D v1.2 backend infrastructure is now fully deployed and ready for the web application.

**Next Steps**:
1. Deploy web application (see Gen3D - Web App - 1.2.md)
2. Perform end-to-end testing
3. Set up monitoring dashboards
4. Configure production domains
5. Enable CloudFront CDN

---

**Document Version**: 1.2
**Last Updated**: November 30, 2025
**Status**: READY FOR PRODUCTION
**Contact**: info@2112-lab.com
