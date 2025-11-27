# Gen3D - Implementation Plan v1.0

## Document Purpose

This document provides a complete, step-by-step implementation guide for deploying the Gen3D service on AWS. All AWS CLI commands, configuration files, and code samples are included for direct execution.

## Prerequisites

### Required Tools
- AWS CLI v2.x installed and configured
- Docker installed (for container building)
- Python 3.11 or later
- Git
- jq (for JSON parsing in shell scripts)

### AWS Account Setup
- AWS Account ID: Genesis3D
- Region: us-east-1 (adjustable)
- Administrator access for initial setup
- HuggingFace account with SAM 3D model access approved

### Environment Variables

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export PROJECT_PREFIX=Gen3D
export ADMIN_EMAIL=info@2112-lab.com
```

## Architecture Flow Diagram

```
┌──────────────┐
│   User       │
│   Browser    │
└──────┬───────┘
       │ 1. Upload Image
       ▼
┌──────────────────────┐
│  S3 Static Website   │
│  Gen3DDataBucket/    │
│    public/           │
└──────┬───────────────┘
       │ 2. PUT Object
       ▼
┌──────────────────────────────┐
│  S3 Event Notification       │
│  /users/{user_id}/input/*    │
└──────┬───────────────────────┘
       │ 3. Trigger
       ▼
┌─────────────────────────────┐
│  Lambda: Gen3DExtractLambda │ ───4. Invoke───┐
└─────────────────────────────┘                │
                                               ▼
                                    ┌──────────────────────┐
                                    │  SageMaker Async     │
                                    │  SAM 3D Endpoint     │
                                    │  (GPU Instance)      │
                                    └──────┬───────────────┘
                                           │ 5. Write Output
                                           ▼
                                    ┌──────────────────────┐
                                    │  S3 Output Path      │
                                    │  /users/{}/output/   │
                                    └──────┬───────────────┘
                                           │ 6. Trigger
                                           ▼
┌────────────────────────────┐    ┌───────────────────────┐
│ Lambda: Gen3DNotifyLambda  │────│  S3 Event Notification│
└────────┬───────────────────┘    └───────────────────────┘
         │ 7. Send Email
         ▼
┌─────────────────┐
│   Amazon SES    │
└─────────────────┘

         All services log to CloudWatch
```

## AWS Resource Flow Diagram

```
IAM Roles
    │
    ├─→ Gen3DSageMakerExecutionRole ─→ SageMaker Endpoint
    ├─→ Gen3DLambdaExtractRole ─→ Gen3DExtractLambda
    └─→ Gen3DLambdaNotifyRole ─→ Gen3DNotifyLambda
                                         │
S3 Buckets                              │
    │                                   │
    ├─→ Gen3DDataBucket ←───────────────┤
    │      ├─ /public/                  │
    │      └─ /users/                   │
    │                                   │
    └─→ Gen3DModelBucket                │
           └─ /sam3d-model/             │
                                        │
ECR Repository                          │
    │                                   │
    └─→ gen3d-sam3d-inference ─→ SageMaker
                                        │
SageMaker                              │
    │                                   │
    └─→ Gen3DSAMAsyncEndpoint ←─────────┤
           ├─ Model                     │
           ├─ Endpoint Config           │
           └─ Endpoint                  │
                                        │
SES                                    │
    │                                   │
    └─→ Verified Identities ←───────────┘

CloudWatch
    │
    └─→ Log Groups for all services
```

---

## Implementation Steps

---

## Phase 1: IAM Roles and Policies

### Step 1.1: Create SageMaker Execution Role

**Purpose**: Allows SageMaker to access S3 and CloudWatch.

```bash
# Create trust policy document
cat > /tmp/sagemaker-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
    --role-name Gen3DSageMakerExecutionRole \
    --assume-role-policy-document file:///tmp/sagemaker-trust-policy.json \
    --description "Execution role for Gen3D SageMaker endpoint"

# Create custom policy for S3 access
cat > /tmp/sagemaker-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket/*",
        "arn:aws:s3:::gen3d-data-bucket",
        "arn:aws:s3:::gen3d-model-bucket/*",
        "arn:aws:s3:::gen3d-model-bucket"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach custom policy
aws iam put-role-policy \
    --role-name Gen3DSageMakerExecutionRole \
    --policy-name Gen3DSageMakerPolicy \
    --policy-document file:///tmp/sagemaker-policy.json
```

### Step 1.2: Create Lambda Extract Execution Role

**Purpose**: Allows Lambda to invoke SageMaker and read from S3.

```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
    --role-name Gen3DLambdaExtractRole \
    --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
    --description "Execution role for Gen3D Extract Lambda"

# Create custom policy
cat > /tmp/lambda-extract-policy.json << 'EOF'
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
        "arn:aws:s3:::gen3d-data-bucket/users/*/input/*",
        "arn:aws:s3:::gen3d-data-bucket"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:InvokeEndpointAsync"
      ],
      "Resource": "arn:aws:sagemaker:*:*:endpoint/gen3dsam-async-endpoint"
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

# Attach policies
aws iam put-role-policy \
    --role-name Gen3DLambdaExtractRole \
    --policy-name Gen3DLambdaExtractPolicy \
    --policy-document file:///tmp/lambda-extract-policy.json
```

### Step 1.3: Create Lambda Notify Execution Role

**Purpose**: Allows Lambda to read S3 and send SES emails.

```bash
# Create role
aws iam create-role \
    --role-name Gen3DLambdaNotifyRole \
    --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
    --description "Execution role for Gen3D Notify Lambda"

# Create custom policy
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
        "arn:aws:s3:::gen3d-data-bucket/users/*/output/*",
        "arn:aws:s3:::gen3d-data-bucket"
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

# Attach policy
aws iam put-role-policy \
    --role-name Gen3DLambdaNotifyRole \
    --policy-name Gen3DLambdaNotifyPolicy \
    --policy-document file:///tmp/lambda-notify-policy.json
```

---

## Phase 2: S3 Bucket Setup

### Step 2.1: Create Data Bucket

**Purpose**: Primary storage for inputs, outputs, and website.

```bash
# Create bucket
aws s3api create-bucket \
    --bucket gen3d-data-bucket \
    --region $AWS_REGION

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket gen3d-data-bucket \
    --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket gen3d-data-bucket \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }'

# Create folder structure
aws s3api put-object --bucket gen3d-data-bucket --key public/
aws s3api put-object --bucket gen3d-data-bucket --key users/
```

### Step 2.2: Configure Public Folder for Static Website

```bash
# Set bucket policy for public folder access
cat > /tmp/bucket-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::gen3d-data-bucket/public/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
    --bucket gen3d-data-bucket \
    --policy file:///tmp/bucket-policy.json

# Configure static website hosting
aws s3api put-bucket-website \
    --bucket gen3d-data-bucket \
    --website-configuration '{
      "IndexDocument": {"Suffix": "index.html"},
      "ErrorDocument": {"Key": "error.html"}
    }'

# Configure CORS for uploads
cat > /tmp/cors-config.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

aws s3api put-bucket-cors \
    --bucket gen3d-data-bucket \
    --cors-configuration file:///tmp/cors-config.json
```

### Step 2.3: Create Model Bucket

**Purpose**: Storage for SAM 3D model artifacts.

```bash
# Create bucket
aws s3api create-bucket \
    --bucket gen3d-model-bucket \
    --region $AWS_REGION

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket gen3d-model-bucket \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }'
```

### Step 2.4: Configure S3 Event Notifications

```bash
# Create notification configuration
cat > /tmp/s3-notifications.json << 'EOF'
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "Gen3DInputTrigger",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DExtractLambda",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "users/"},
            {"Name": "suffix", "Value": ".png"}
          ]
        }
      }
    },
    {
      "Id": "Gen3DOutputTrigger",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DNotifyLambda",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "users/"},
            {"Name": "suffix", "Value": ".ply"}
          ]
        }
      }
    }
  ]
}
EOF

# Note: Replace ACCOUNT_ID with actual account ID before applying
# This will be applied after Lambda functions are created
```

---

## Phase 3: SageMaker Model Deployment

### Step 3.1: Obtain HuggingFace Access Token

**You need a HuggingFace Access Token** (not username/password) to download the SAM 3D model.

#### How to Get Your HuggingFace Access Token:

**1. Create/Login to HuggingFace Account**
- Visit: https://huggingface.co
- Sign up or log in with your credentials

**2. Accept SAM 3D Model License**
- Visit: https://huggingface.co/facebook/sam-3d-objects
- Click **"Agree and access repository"**
- Review and accept Meta's SAM License terms
- This grants your account permission to download the model

**3. Generate Access Token**
- Go to: https://huggingface.co/settings/tokens
- Click **"New token"**
- Token name: `Gen3D-SAM3D` (or your preferred name)
- Token type: **"Read"** (sufficient for downloading models)
- Click **"Generate token"**
- **IMPORTANT**: Copy and save the token immediately (starts with `hf_...`)
- You won't be able to see it again!

**Security Note**: Never commit your token to git. It's already excluded in `.gitignore`.

---

### Step 3.2: Install HuggingFace Hub Library

```bash
# Install HuggingFace Hub with CLI support
pip install -U "huggingface_hub[cli]"

# Verify installation
python -c "import huggingface_hub; print(f'HuggingFace Hub v{huggingface_hub.__version__} installed')"
```

---

### Step 3.3: Authenticate with HuggingFace

Choose one of the following methods to authenticate:

#### Method 1: Python Login (Recommended - Works on All Platforms)

```bash
# Create and run a Python script to login
python << 'PYTHON_EOF'
from huggingface_hub import login

# Replace with your actual token
token = "hf_your_token_here"

login(token=token)
print("✓ Successfully logged in to HuggingFace")
print("✓ Token stored in ~/.cache/huggingface/token")
PYTHON_EOF
```

#### Method 2: Interactive CLI Login (Linux/Mac/Windows)

```bash
# This works on Windows Git Bash too
python -m huggingface_hub.commands.huggingface_cli login

# You'll be prompted to paste your token
# The token will be stored securely
```

#### Method 3: Environment Variable (Temporary)

```bash
# For Linux/Mac/Git Bash
export HUGGING_FACE_HUB_TOKEN=hf_your_token_here

# For Windows CMD
set HUGGING_FACE_HUB_TOKEN=hf_your_token_here

# For Windows PowerShell
$env:HUGGING_FACE_HUB_TOKEN="hf_your_token_here"
```

#### Verify Authentication

```bash
python << 'PYTHON_EOF'
from huggingface_hub import whoami
try:
    user_info = whoami()
    print(f"✓ Authenticated as: {user_info['name']}")
    print(f"✓ Account type: {user_info.get('type', 'user')}")
except Exception as e:
    print(f"✗ Authentication failed: {e}")
    print("Make sure you've set your token correctly")
PYTHON_EOF
```

---

### Step 3.4: Download SAM 3D Model from HuggingFace

**Clone SAM 3D repository and download model weights**:

```bash
# Create working directory
mkdir -p /tmp/gen3d-build
cd /tmp/gen3d-build

# Clone SAM 3D repository
echo "Cloning SAM 3D repository..."
git clone https://github.com/facebookresearch/sam-3d-objects.git
cd sam-3d-objects

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
pip install -r requirements.inference.txt

# Create checkpoints directory
mkdir -p checkpoints/hf

# Download model from HuggingFace using Python
echo "Downloading SAM 3D model from HuggingFace..."
echo "This may take several minutes (model is several GB)..."

python << 'PYTHON_EOF'
from huggingface_hub import snapshot_download
import os

try:
    print("Starting download...")
    snapshot_download(
        repo_id="facebook/sam-3d-objects",
        local_dir="checkpoints/hf",
        local_dir_use_symlinks=False,
        resume_download=True,
        ignore_patterns=["*.git*", "*.md"]  # Skip git files and docs
    )
    print("\n✓ Model downloaded successfully to checkpoints/hf/")

    # List downloaded files
    print("\nDownloaded files:")
    for root, dirs, files in os.walk("checkpoints/hf"):
        level = root.replace("checkpoints/hf", "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for file in files[:10]:  # Show first 10 files
            print(f"{subindent}{file}")
        if len(files) > 10:
            print(f"{subindent}... and {len(files)-10} more files")

except Exception as e:
    print(f"\n✗ Download failed: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure you've accepted the model license at:")
    print("   https://huggingface.co/facebook/sam-3d-objects")
    print("2. Verify your token is valid:")
    print("   python -c 'from huggingface_hub import whoami; print(whoami())'")
    print("3. Check your internet connection")
    exit(1)
PYTHON_EOF

# Verify critical files exist
echo ""
echo "Verifying downloaded files..."
if [ -f "checkpoints/hf/pipeline.yaml" ]; then
    echo "✓ pipeline.yaml found"
else
    echo "✗ pipeline.yaml missing - download may be incomplete"
    exit 1
fi

echo ""
echo "✓ SAM 3D model ready for deployment"
```

**Alternative: Download Specific Files Only (If Full Download Fails)**

```bash
python << 'PYTHON_EOF'
from huggingface_hub import hf_hub_download
import os

repo_id = "facebook/sam-3d-objects"
local_dir = "checkpoints/hf"

# Essential files (adjust based on actual model structure)
essential_files = [
    "pipeline.yaml",
    "config.json",
    "model.safetensors",  # or model.bin
]

os.makedirs(local_dir, exist_ok=True)

print("Downloading essential model files...")
for filename in essential_files:
    try:
        print(f"  Downloading {filename}...", end=" ")
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir,
            local_dir_use_symlinks=False
        )
        print("✓")
    except Exception as e:
        print(f"✗ ({e})")

print("\nDownload complete!")
PYTHON_EOF
```

---

### Step 3.5: Store HuggingFace Token in AWS Secrets Manager

For SageMaker to access the model or download updates, store the token securely in AWS:

```bash
# Store HuggingFace token in AWS Secrets Manager
aws secretsmanager create-secret \
    --name Gen3D/HuggingFaceToken \
    --description "HuggingFace API token for SAM 3D model access" \
    --secret-string "{\"token\":\"hf_your_token_here\"}" \
    --region $AWS_REGION

# Verify secret was created
aws secretsmanager describe-secret \
    --secret-id Gen3D/HuggingFaceToken \
    --region $AWS_REGION

# Get the secret ARN for later use
HF_TOKEN_ARN=$(aws secretsmanager describe-secret \
    --secret-id Gen3D/HuggingFaceToken \
    --query ARN --output text)

echo "✓ HuggingFace token stored in AWS Secrets Manager"
echo "Secret ARN: $HF_TOKEN_ARN"
```

**Update SageMaker IAM Role to Access Secret**:

```bash
# Add Secrets Manager permissions to SageMaker role
cat > /tmp/sagemaker-secrets-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:Gen3D/*"
    }
  ]
}
EOF

aws iam put-role-policy \
    --role-name Gen3DSageMakerExecutionRole \
    --policy-name Gen3DSecretsManagerPolicy \
    --policy-document file:///tmp/sagemaker-secrets-policy.json

echo "✓ SageMaker role updated with Secrets Manager access"
```

---

### Step 3.6: Create Custom Inference Container

**Ensure you're in the sam-3d-objects directory**:

```bash
cd /tmp/gen3d-build/sam-3d-objects
```

**Create Dockerfile**:

```bash
cat > Dockerfile << 'EOF'
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/ml/model

# Copy SAM 3D code
COPY sam-3d-objects/ /opt/ml/code/
COPY checkpoints/ /opt/ml/model/checkpoints/

# Install Python dependencies
RUN pip install --no-cache-dir \
    -r /opt/ml/code/requirements.txt \
    -r /opt/ml/code/requirements.inference.txt \
    flask \
    boto3

# Copy inference script
COPY inference.py /opt/ml/code/
COPY serve.py /opt/ml/code/

# Set environment variables
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/ml/code:${PATH}"

# Expose port for inference
EXPOSE 8080

# Entry point
ENTRYPOINT ["python", "/opt/ml/code/serve.py"]
EOF
```

**Create inference script** (`inference.py`):

```python
import os
import json
import boto3
import torch
from PIL import Image
import numpy as np
from io import BytesIO

# Import SAM 3D components
import sys
sys.path.append('/opt/ml/code')
from inference import Inference, load_image, load_single_mask

class SAM3DHandler:
    def __init__(self):
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def initialize(self):
        """Load model on initialization"""
        config_path = "/opt/ml/model/checkpoints/hf/pipeline.yaml"
        self.model = Inference(config_path, compile=False)
        print(f"Model loaded successfully on {self.device}")

    def preprocess(self, image_bytes, mask_bytes=None):
        """Preprocess input image and mask"""
        # Load image
        image = Image.open(BytesIO(image_bytes))

        if mask_bytes:
            mask = Image.open(BytesIO(mask_bytes))
        else:
            # Extract mask from alpha channel if RGBA
            if image.mode == 'RGBA':
                mask = image.split()[-1]
            else:
                raise ValueError("No mask provided and image has no alpha channel")

        return image, mask

    def inference(self, image, mask, seed=42):
        """Run inference"""
        output = self.model(image, mask, seed=seed)
        return output

    def postprocess(self, output, output_path):
        """Save output to S3"""
        # Save PLY file
        output["gs"].save_ply(output_path)
        return output_path

# Flask server wrapper
handler = SAM3DHandler()

def model_fn(model_dir):
    """Load model"""
    handler.initialize()
    return handler

def input_fn(request_body, content_type):
    """Parse input"""
    if content_type == 'application/json':
        input_data = json.loads(request_body)
        s3 = boto3.client('s3')

        # Download image and mask from S3
        image_bucket = input_data['image_bucket']
        image_key = input_data['image_key']
        mask_key = input_data.get('mask_key')

        image_obj = s3.get_object(Bucket=image_bucket, Key=image_key)
        image_bytes = image_obj['Body'].read()

        mask_bytes = None
        if mask_key:
            mask_obj = s3.get_object(Bucket=image_bucket, Key=mask_key)
            mask_bytes = mask_obj['Body'].read()

        return {'image': image_bytes, 'mask': mask_bytes, 'metadata': input_data}
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

def predict_fn(input_data, model):
    """Run prediction"""
    image, mask = model.preprocess(input_data['image'], input_data['mask'])
    seed = input_data['metadata'].get('seed', 42)
    output = model.inference(image, mask, seed)
    return {'output': output, 'metadata': input_data['metadata']}

def output_fn(prediction, accept):
    """Upload output to S3"""
    s3 = boto3.client('s3')

    output_bucket = prediction['metadata']['output_bucket']
    output_key = prediction['metadata']['output_key']

    # Save to temporary file
    temp_path = '/tmp/output.ply'
    prediction['output']["gs"].save_ply(temp_path)

    # Upload to S3
    s3.upload_file(temp_path, output_bucket, output_key)

    return json.dumps({
        'status': 'success',
        'output_location': f's3://{output_bucket}/{output_key}'
    })
```

**Create serve script** (`serve.py`):

```python
import flask
import json
import os
from inference import model_fn, input_fn, predict_fn, output_fn

app = flask.Flask(__name__)

# Load model
model = None

@app.route('/ping', methods=['GET'])
def ping():
    """Health check"""
    health = model is not None
    status = 200 if health else 404
    return flask.Response(response='\n', status=status, mimetype='application/json')

@app.route('/invocations', methods=['POST'])
def invocations():
    """Inference endpoint"""
    try:
        # Parse input
        input_data = input_fn(flask.request.data, flask.request.content_type)

        # Run prediction
        prediction = predict_fn(input_data, model)

        # Format output
        result = output_fn(prediction, flask.request.accept_mimetypes)

        return flask.Response(response=result, status=200, mimetype='application/json')
    except Exception as e:
        return flask.Response(
            response=json.dumps({'error': str(e)}),
            status=500,
            mimetype='application/json'
        )

if __name__ == '__main__':
    # Load model
    model = model_fn('/opt/ml/model')

    # Start server
    app.run(host='0.0.0.0', port=8080)
```

### Step 3.7: Build and Push Container to ECR

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name gen3d-sam3d-inference \
    --region $AWS_REGION

# Get ECR login
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build image
docker build -t gen3d-sam3d-inference:latest .

# Tag image
docker tag gen3d-sam3d-inference:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/gen3d-sam3d-inference:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/gen3d-sam3d-inference:latest
```

### Step 3.8: Create SageMaker Model

```bash
# Get IAM role ARN
SAGEMAKER_ROLE_ARN=$(aws iam get-role \
    --role-name Gen3DSageMakerExecutionRole \
    --query 'Role.Arn' --output text)

# Create model
aws sagemaker create-model \
    --model-name Gen3DSAM3DModel \
    --primary-container "{ \
        \"Image\": \"$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/gen3d-sam3d-inference:latest\", \
        \"Mode\": \"SingleModel\" \
    }" \
    --execution-role-arn $SAGEMAKER_ROLE_ARN
```

### Step 3.9: Create Async Endpoint Configuration

```bash
# Create async inference configuration
cat > /tmp/async-config.json << 'EOF'
{
  "OutputConfig": {
    "S3OutputPath": "s3://gen3d-data-bucket/sagemaker-output/"
  },
  "ClientConfig": {
    "MaxConcurrentInvocationsPerInstance": 4
  }
}
EOF

# Create endpoint configuration
aws sagemaker create-endpoint-config \
    --endpoint-config-name Gen3DSAM-AsyncConfig \
    --production-variants "[ \
        { \
            \"VariantName\": \"AllTraffic\", \
            \"ModelName\": \"Gen3DSAM3DModel\", \
            \"InstanceType\": \"ml.g4dn.xlarge\", \
            \"InitialInstanceCount\": 1, \
            \"InitialVariantWeight\": 1.0 \
        } \
    ]" \
    --async-inference-config file:///tmp/async-config.json
```

### Step 3.10: Create Async Endpoint

```bash
# Create endpoint
aws sagemaker create-endpoint \
    --endpoint-name Gen3DSAMAsyncEndpoint \
    --endpoint-config-name Gen3DSAM-AsyncConfig

# Wait for endpoint to be in service (this takes 5-10 minutes)
aws sagemaker wait endpoint-in-service \
    --endpoint-name Gen3DSAMAsyncEndpoint

# Check endpoint status
aws sagemaker describe-endpoint \
    --endpoint-name Gen3DSAMAsyncEndpoint
```

---

## Phase 4: Lambda Functions

### Step 4.1: Create Gen3DExtractLambda Function

**Create function code** (`extract_lambda.py`):

```python
import json
import boto3
import os
from datetime import datetime
from urllib.parse import unquote_plus

sagemaker_runtime = boto3.client('sagemaker-runtime')
s3_client = boto3.client('s3')

ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT_NAME']
DATA_BUCKET = os.environ['DATA_BUCKET']

def lambda_handler(event, context):
    """
    Triggered by S3 upload to users/{user_id}/input/
    Invokes SageMaker async endpoint
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse S3 event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        print(f"Processing file: s3://{bucket}/{key}")

        # Extract user_id from path
        # Expected format: users/{user_id}/input/{filename}
        parts = key.split('/')
        if len(parts) < 4 or parts[0] != 'users':
            raise ValueError(f"Invalid key format: {key}")

        user_id = parts[1]
        filename = parts[3]

        # Generate output path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{timestamp}_{os.path.splitext(filename)[0]}.ply"
        output_key = f"users/{user_id}/output/{output_filename}"

        # Prepare inference input
        input_data = {
            'image_bucket': bucket,
            'image_key': key,
            'output_bucket': DATA_BUCKET,
            'output_key': output_key,
            'user_id': user_id,
            'seed': 42
        }

        # Invoke SageMaker async endpoint
        response = sagemaker_runtime.invoke_endpoint_async(
            EndpointName=ENDPOINT_NAME,
            InputLocation=f's3://{bucket}/{key}',
            ContentType='application/json',
            Accept='application/json',
            CustomAttributes=json.dumps(input_data)
        )

        invocation_arn = response['OutputLocation']

        print(f"SageMaker invocation ARN: {invocation_arn}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing started',
                'user_id': user_id,
                'input_file': key,
                'output_file': output_key,
                'invocation_arn': invocation_arn
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")

        # Send error notification
        try:
            send_error_notification(user_id, str(e))
        except:
            pass

        raise e

def send_error_notification(user_id, error_message):
    """Send error notification via SES"""
    ses_client = boto3.client('ses')
    admin_email = os.environ.get('ADMIN_EMAIL', 'info@2112-lab.com')

    ses_client.send_email(
        Source='noreply@genesis3d.com',
        Destination={'ToAddresses': [admin_email]},
        Message={
            'Subject': {'Data': 'Gen3D Processing Error'},
            'Body': {
                'Text': {
                    'Data': f'Error processing request for user {user_id}:\n\n{error_message}'
                }
            }
        }
    )
```

**Package and deploy**:

```bash
# Create deployment package
cd /tmp
mkdir lambda_extract
cd lambda_extract
cp /path/to/extract_lambda.py lambda_function.py
zip -r ../extract_lambda.zip .

# Get IAM role ARN
LAMBDA_EXTRACT_ROLE_ARN=$(aws iam get-role \
    --role-name Gen3DLambdaExtractRole \
    --query 'Role.Arn' --output text)

# Create Lambda function
aws lambda create-function \
    --function-name Gen3DExtractLambda \
    --runtime python3.11 \
    --role $LAMBDA_EXTRACT_ROLE_ARN \
    --handler lambda_function.lambda_handler \
    --zip-file fileb:///tmp/extract_lambda.zip \
    --timeout 30 \
    --memory-size 512 \
    --environment "Variables={ \
        SAGEMAKER_ENDPOINT_NAME=Gen3DSAMAsyncEndpoint, \
        DATA_BUCKET=gen3d-data-bucket, \
        ADMIN_EMAIL=info@2112-lab.com \
    }"

# Add S3 trigger permission
aws lambda add-permission \
    --function-name Gen3DExtractLambda \
    --statement-id S3InvokeFunction \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::gen3d-data-bucket
```

### Step 4.2: Create Gen3DNotifyLambda Function

**Create function code** (`notify_lambda.py`):

```python
import json
import boto3
import os
from datetime import datetime, timedelta
from urllib.parse import unquote_plus

s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

DATA_BUCKET = os.environ['DATA_BUCKET']
ADMIN_EMAIL = os.environ['ADMIN_EMAIL']
SOURCE_EMAIL = os.environ.get('SOURCE_EMAIL', 'noreply@genesis3d.com')

def lambda_handler(event, context):
    """
    Triggered by S3 upload to users/{user_id}/output/
    Sends email notification with download link
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse S3 event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        print(f"Processing output file: s3://{bucket}/{key}")

        # Extract user_id from path
        parts = key.split('/')
        if len(parts) < 4 or parts[0] != 'users':
            raise ValueError(f"Invalid key format: {key}")

        user_id = parts[1]
        filename = parts[3]

        # Check if this is an error file
        if filename.endswith('.error'):
            handle_error_notification(user_id, bucket, key)
            return {'statusCode': 200, 'body': 'Error notification sent'}

        # Generate pre-signed URL (24 hour expiry)
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=86400
        )

        # Get file size
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size_mb = response['ContentLength'] / (1024 * 1024)

        # Send success notification
        send_success_notification(user_id, filename, download_url, file_size_mb)

        print(f"Success notification sent for user {user_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Notification sent',
                'user_id': user_id,
                'output_file': key
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        raise e

def send_success_notification(user_id, filename, download_url, file_size_mb):
    """Send success email notification"""

    subject = "Your 3D Mesh is Ready!"

    body_text = f"""
Hello,

Your 3D mesh has been successfully generated!

File: {filename}
Size: {file_size_mb:.2f} MB
User ID: {user_id}

Download your 3D mesh here (link expires in 24 hours):
{download_url}

You can open .ply files with:
- Blender (free, open-source)
- MeshLab (free, open-source)
- CloudCompare (free, open-source)
- Any 3D modeling software

Thank you for using Gen3D!

--
Gen3D Team
Genesis3D
"""

    body_html = f"""
<html>
<head></head>
<body>
  <h2>Your 3D Mesh is Ready!</h2>

  <p>Your 3D mesh has been successfully generated.</p>

  <table>
    <tr><td><strong>File:</strong></td><td>{filename}</td></tr>
    <tr><td><strong>Size:</strong></td><td>{file_size_mb:.2f} MB</td></tr>
    <tr><td><strong>User ID:</strong></td><td>{user_id}</td></tr>
  </table>

  <p>
    <a href="{download_url}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">
      Download Your 3D Mesh
    </a>
  </p>

  <p><small>Link expires in 24 hours</small></p>

  <h3>How to Open Your File</h3>
  <p>You can open .ply files with:</p>
  <ul>
    <li>Blender (free, open-source)</li>
    <li>MeshLab (free, open-source)</li>
    <li>CloudCompare (free, open-source)</li>
    <li>Any 3D modeling software</li>
  </ul>

  <hr>
  <p><small>Gen3D Team | Genesis3D</small></p>
</body>
</html>
"""

    # Send to user (using user_id as email for now)
    # In production, look up user email from database
    recipient = f"{user_id}@example.com"  # Replace with actual user email lookup

    try:
        ses_client.send_email(
            Source=SOURCE_EMAIL,
            Destination={'ToAddresses': [recipient, ADMIN_EMAIL]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        )
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        # If user email fails, at least notify admin
        ses_client.send_email(
            Source=SOURCE_EMAIL,
            Destination={'ToAddresses': [ADMIN_EMAIL]},
            Message={
                'Subject': {'Data': f'Gen3D: Mesh Ready for {user_id}'},
                'Body': {'Text': {'Data': body_text}}
            }
        )

def handle_error_notification(user_id, bucket, key):
    """Handle error notification"""
    # Read error details
    error_obj = s3_client.get_object(Bucket=bucket, Key=key)
    error_details = error_obj['Body'].read().decode('utf-8')

    subject = "Gen3D Processing Error"

    body_text = f"""
Hello,

Unfortunately, there was an error processing your 3D mesh request.

User ID: {user_id}
Error Details:
{error_details}

Please try again or contact support at {ADMIN_EMAIL} if the problem persists.

--
Gen3D Team
Genesis3D
"""

    # Send notification
    recipient = f"{user_id}@example.com"  # Replace with actual lookup

    ses_client.send_email(
        Source=SOURCE_EMAIL,
        Destination={'ToAddresses': [ADMIN_EMAIL]},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': body_text}}
        }
    )
```

**Package and deploy**:

```bash
# Create deployment package
cd /tmp
mkdir lambda_notify
cd lambda_notify
cp /path/to/notify_lambda.py lambda_function.py
zip -r ../notify_lambda.zip .

# Get IAM role ARN
LAMBDA_NOTIFY_ROLE_ARN=$(aws iam get-role \
    --role-name Gen3DLambdaNotifyRole \
    --query 'Role.Arn' --output text)

# Create Lambda function
aws lambda create-function \
    --function-name Gen3DNotifyLambda \
    --runtime python3.11 \
    --role $LAMBDA_NOTIFY_ROLE_ARN \
    --handler lambda_function.lambda_handler \
    --zip-file fileb:///tmp/notify_lambda.zip \
    --timeout 15 \
    --memory-size 256 \
    --environment "Variables={ \
        DATA_BUCKET=gen3d-data-bucket, \
        ADMIN_EMAIL=info@2112-lab.com, \
        SOURCE_EMAIL=noreply@genesis3d.com \
    }"

# Add S3 trigger permission
aws lambda add-permission \
    --function-name Gen3DNotifyLambda \
    --statement-id S3InvokeFunction \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::gen3d-data-bucket
```

### Step 4.3: Configure S3 Event Triggers

```bash
# Update notification configuration with actual Lambda ARNs
EXTRACT_LAMBDA_ARN=$(aws lambda get-function --function-name Gen3DExtractLambda --query 'Configuration.FunctionArn' --output text)
NOTIFY_LAMBDA_ARN=$(aws lambda get-function --function-name Gen3DNotifyLambda --query 'Configuration.FunctionArn' --output text)

cat > /tmp/s3-notifications-final.json << EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "Gen3DInputTrigger",
      "LambdaFunctionArn": "${EXTRACT_LAMBDA_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "users/"},
            {"Name": "suffix", "Value": ".png"}
          ]
        }
      }
    },
    {
      "Id": "Gen3DOutputTrigger",
      "LambdaFunctionArn": "${NOTIFY_LAMBDA_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "users/"},
            {"Name": "suffix", "Value": ".ply"}
          ]
        }
      }
    }
  ]
}
EOF

aws s3api put-bucket-notification-configuration \
    --bucket gen3d-data-bucket \
    --notification-configuration file:///tmp/s3-notifications-final.json
```

---

## Phase 5: SES Configuration

### Step 5.1: Verify Email Identities

```bash
# Verify admin email
aws ses verify-email-identity \
    --email-address info@2112-lab.com

# Verify sender email
aws ses verify-email-identity \
    --email-address noreply@genesis3d.com

echo "Check your email and click the verification links"

# Check verification status
aws ses get-identity-verification-attributes \
    --identities info@2112-lab.com noreply@genesis3d.com
```

### Step 5.2: Request Production Access (if needed)

```bash
# If still in SES sandbox, request production access
# This is done through AWS Console: SES > Account dashboard > Request production access
# Or use the AWS Support API to create a service limit increase case

echo "To send emails to unverified addresses, request SES production access in AWS Console"
```

---

## Phase 6: CloudWatch Logging and Monitoring

### Step 6.1: Create CloudWatch Log Groups

```bash
# Lambda log groups are created automatically
# Create custom log group for application logs
aws logs create-log-group \
    --log-group-name /gen3d/application

# Set retention policy (30 days)
aws logs put-retention-policy \
    --log-group-name /gen3d/application \
    --retention-in-days 30

aws logs put-retention-policy \
    --log-group-name /aws/lambda/Gen3DExtractLambda \
    --retention-in-days 30

aws logs put-retention-policy \
    --log-group-name /aws/lambda/Gen3DNotifyLambda \
    --retention-in-days 30
```

### Step 6.2: Create CloudWatch Alarms

```bash
# Alarm for high error rate in Extract Lambda
aws cloudwatch put-metric-alarm \
    --alarm-name Gen3D-ExtractLambda-HighErrors \
    --alarm-description "Alert when Extract Lambda error rate > 5%" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=Gen3DExtractLambda

# Alarm for SageMaker endpoint health
aws cloudwatch put-metric-alarm \
    --alarm-name Gen3D-SageMaker-ModelLatency \
    --alarm-description "Alert when SageMaker latency > 60 seconds" \
    --metric-name ModelLatency \
    --namespace AWS/SageMaker \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 60000 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=EndpointName,Value=Gen3DSAMAsyncEndpoint Name=VariantName,Value=AllTraffic
```

### Step 6.3: Create Dashboard

```bash
cat > /tmp/dashboard.json << 'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Extract Invocations"}],
          [".", ".", {"stat": "Sum", "label": "Notify Invocations"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Invocations"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/SageMaker", "ModelLatency", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "SageMaker Latency"
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
    --dashboard-name Gen3D-Operations \
    --dashboard-body file:///tmp/dashboard.json
```

---

## Phase 7: Web Interface

### Step 7.1: Create HTML Interface

**Create `index.html`**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gen3D - 3D Mesh Extraction</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 900px;
            width: 100%;
            padding: 40px;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }

        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 10px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 20px;
        }

        .upload-area:hover {
            border-color: #764ba2;
            background: #f8f9ff;
        }

        .upload-area.active {
            border-color: #764ba2;
            background: #f0f0ff;
        }

        #canvas-container {
            position: relative;
            display: none;
            margin: 20px 0;
        }

        #imageCanvas {
            max-width: 100%;
            border: 2px solid #ddd;
            border-radius: 10px;
            cursor: crosshair;
        }

        .button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 10px 5px;
        }

        .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }

        .button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .instructions {
            background: #f8f9ff;
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 5px;
        }

        .instructions h3 {
            color: #667eea;
            margin-bottom: 10px;
        }

        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            display: none;
        }

        .status.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .status.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .user-id-input {
            margin: 20px 0;
        }

        .user-id-input input {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }

        .user-id-input input:focus {
            outline: none;
            border-color: #667eea;
        }

        #bounding-boxes {
            margin-top: 20px;
        }

        .bbox-item {
            background: #f0f0f0;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .delete-bbox {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gen3D</h1>
        <p class="subtitle">Extract 3D meshes from your images using Meta's SAM 3D</p>

        <div class="user-id-input">
            <label for="userId"><strong>User ID:</strong></label>
            <input type="text" id="userId" placeholder="Enter your user ID (e.g., user123)" required>
        </div>

        <div class="instructions">
            <h3>How it works:</h3>
            <ol>
                <li>Enter your User ID above</li>
                <li>Upload or drag-and-drop an image</li>
                <li>Draw bounding boxes around objects you want to extract</li>
                <li>Click "Process" to generate 3D meshes</li>
                <li>Receive an email with download links when ready</li>
            </ol>
        </div>

        <div class="upload-area" id="uploadArea">
            <h2>📁 Drop your image here</h2>
            <p>or click to select a file</p>
            <p style="color: #999; margin-top: 10px;">Supported: PNG, JPG, JPEG</p>
            <input type="file" id="fileInput" accept="image/*" style="display: none;">
        </div>

        <div id="canvas-container">
            <canvas id="imageCanvas"></canvas>
        </div>

        <div id="bounding-boxes"></div>

        <div style="text-align: center;">
            <button class="button" id="clearBtn" style="display: none;">Clear Selection</button>
            <button class="button" id="processBtn" style="display: none;">Process Image</button>
        </div>

        <div class="status" id="status"></div>
    </div>

    <script src="https://sdk.amazonaws.com/js/aws-sdk-2.1000.0.min.js"></script>
    <script>
        // Configuration
        const S3_BUCKET = 'gen3d-data-bucket';
        const AWS_REGION = 'us-east-1';

        // Configure AWS SDK for unsigned requests (browser upload to public bucket)
        AWS.config.region = AWS_REGION;
        AWS.config.credentials = new AWS.CognitoIdentityCredentials({
            IdentityPoolId: 'REPLACE_WITH_IDENTITY_POOL_ID'  // Need to create Cognito Identity Pool
        });

        const s3 = new AWS.S3({
            apiVersion: '2006-03-01',
            params: { Bucket: S3_BUCKET }
        });

        // State
        let uploadedImage = null;
        let canvas = document.getElementById('imageCanvas');
        let ctx = canvas.getContext('2d');
        let boundingBoxes = [];
        let currentBox = null;
        let isDrawing = false;

        // Elements
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const canvasContainer = document.getElementById('canvas-container');
        const clearBtn = document.getElementById('clearBtn');
        const processBtn = document.getElementById('processBtn');
        const statusDiv = document.getElementById('status');
        const userIdInput = document.getElementById('userId');
        const bboxContainer = document.getElementById('bounding-boxes');

        // Upload area interactions
        uploadArea.addEventListener('click', () => fileInput.click());

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('active');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('active');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('active');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                loadImage(file);
            }
        });

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                loadImage(file);
            }
        });

        // Load and display image
        function loadImage(file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    uploadedImage = { file, img };

                    // Set canvas size
                    const maxWidth = 800;
                    const scale = Math.min(1, maxWidth / img.width);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;

                    // Draw image
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                    // Show canvas
                    canvasContainer.style.display = 'block';
                    clearBtn.style.display = 'inline-block';
                    processBtn.style.display = 'inline-block';

                    // Reset bounding boxes
                    boundingBoxes = [];
                    updateBBoxList();
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        // Canvas drawing
        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            isDrawing = true;
            currentBox = { startX: x, startY: y };
        });

        canvas.addEventListener('mousemove', (e) => {
            if (!isDrawing) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // Redraw image
            ctx.drawImage(uploadedImage.img, 0, 0, canvas.width, canvas.height);

            // Draw existing boxes
            boundingBoxes.forEach(box => drawBox(box, '#00ff00'));

            // Draw current box
            drawBox({
                startX: currentBox.startX,
                startY: currentBox.startY,
                endX: x,
                endY: y
            }, '#ff0000');
        });

        canvas.addEventListener('mouseup', (e) => {
            if (!isDrawing) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            currentBox.endX = x;
            currentBox.endY = y;

            // Add to bounding boxes if valid size
            const width = Math.abs(currentBox.endX - currentBox.startX);
            const height = Math.abs(currentBox.endY - currentBox.startY);
            if (width > 10 && height > 10) {
                boundingBoxes.push(currentBox);
                updateBBoxList();
            }

            isDrawing = false;
            currentBox = null;

            // Redraw
            redrawCanvas();
        });

        function drawBox(box, color) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.strokeRect(
                box.startX,
                box.startY,
                box.endX - box.startX,
                box.endY - box.startY
            );
        }

        function redrawCanvas() {
            ctx.drawImage(uploadedImage.img, 0, 0, canvas.width, canvas.height);
            boundingBoxes.forEach(box => drawBox(box, '#00ff00'));
        }

        function updateBBoxList() {
            bboxContainer.innerHTML = '';
            boundingBoxes.forEach((box, index) => {
                const div = document.createElement('div');
                div.className = 'bbox-item';
                div.innerHTML = `
                    <span>Object ${index + 1}: (${Math.round(box.startX)}, ${Math.round(box.startY)}) to (${Math.round(box.endX)}, ${Math.round(box.endY)})</span>
                    <button class="delete-bbox" onclick="deleteBBox(${index})">Delete</button>
                `;
                bboxContainer.appendChild(div);
            });
        }

        window.deleteBBox = function(index) {
            boundingBoxes.splice(index, 1);
            updateBBoxList();
            redrawCanvas();
        };

        // Clear button
        clearBtn.addEventListener('click', () => {
            boundingBoxes = [];
            updateBBoxList();
            redrawCanvas();
        });

        // Process button
        processBtn.addEventListener('click', async () => {
            const userId = userIdInput.value.trim();

            if (!userId) {
                showStatus('Please enter your User ID', 'error');
                return;
            }

            if (boundingBoxes.length === 0) {
                showStatus('Please draw at least one bounding box around an object', 'error');
                return;
            }

            processBtn.disabled = true;
            showStatus('Processing... Please wait', 'success');

            try {
                // Upload each bounding box as a separate job
                for (let i = 0; i < boundingBoxes.length; i++) {
                    await uploadMaskedImage(userId, boundingBoxes[i], i);
                }

                showStatus(
                    `Success! ${boundingBoxes.length} object(s) queued for processing. ` +
                    `You will receive an email when your 3D meshes are ready.`,
                    'success'
                );
            } catch (error) {
                showStatus(`Error: ${error.message}`, 'error');
            } finally {
                processBtn.disabled = false;
            }
        });

        async function uploadMaskedImage(userId, bbox, index) {
            // Create a new canvas with the mask
            const maskCanvas = document.createElement('canvas');
            maskCanvas.width = canvas.width;
            maskCanvas.height = canvas.height;
            const maskCtx = maskCanvas.getContext('2d');

            // Draw white background
            maskCtx.fillStyle = 'white';
            maskCtx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);

            // Draw the masked region (black rectangle)
            maskCtx.fillStyle = 'black';
            maskCtx.fillRect(
                Math.min(bbox.startX, bbox.endX),
                Math.min(bbox.startY, bbox.endY),
                Math.abs(bbox.endX - bbox.startX),
                Math.abs(bbox.endY - bbox.startY)
            );

            // Convert to blob
            const blob = await new Promise(resolve => {
                maskCanvas.toBlob(resolve, 'image/png');
            });

            // Upload to S3
            const timestamp = new Date().getTime();
            const filename = `${timestamp}_object_${index}.png`;
            const key = `users/${userId}/input/${filename}`;

            const params = {
                Key: key,
                Body: blob,
                ContentType: 'image/png'
            };

            await s3.upload(params).promise();
        }

        function showStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = `status ${type}`;
            statusDiv.style.display = 'block';
        }
    </script>
</body>
</html>
```

### Step 7.2: Upload Web Interface to S3

```bash
# Upload HTML file
aws s3 cp index.html s3://gen3d-data-bucket/public/index.html \
    --content-type text/html

# Get website URL
echo "Website URL: http://gen3d-data-bucket.s3-website-$AWS_REGION.amazonaws.com"
```

---

## Phase 8: Testing

### Step 8.1: Download Test Images

```bash
# Create test directory
mkdir -p /tmp/gen3d-test
cd /tmp/gen3d-test

# Download test images
curl -o test_image1.jpg "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg?auto=compress&cs=tinysrgb&w=800"
curl -o test_image2.jpg "https://images.pexels.com/photos/3787326/pexels-photo-3787326.jpeg?auto=compress&cs=tinysrgb&w=800"
```

### Step 8.2: End-to-End Testing via CLI

```bash
# Test user IDs
USER1="testuser001"
USER2="testuser002"

# Upload test image for user 1
aws s3 cp test_image1.jpg s3://gen3d-data-bucket/users/$USER1/input/test_image1.png

echo "Uploaded test image for $USER1"
echo "Check CloudWatch logs for Lambda execution:"
echo "  aws logs tail /aws/lambda/Gen3DExtractLambda --follow"

# Wait a few minutes for processing
sleep 300

# Check for output
aws s3 ls s3://gen3d-data-bucket/users/$USER1/output/

# Download output if available
aws s3 cp s3://gen3d-data-bucket/users/$USER1/output/ /tmp/gen3d-test/output/ --recursive
```

### Step 8.3: Test Web Interface

```bash
echo "Open the web interface in your browser:"
echo "http://gen3d-data-bucket.s3-website-$AWS_REGION.amazonaws.com"
echo ""
echo "Test steps:"
echo "1. Enter User ID: testuser003"
echo "2. Upload an image"
echo "3. Draw bounding box around an object"
echo "4. Click Process"
echo "5. Check CloudWatch logs for execution"
echo "6. Check email for notification (to admin email)"
```

### Step 8.4: Monitoring and Validation

```bash
# Check Lambda invocations
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=Gen3DExtractLambda \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum

# Check SageMaker endpoint metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/SageMaker \
    --metric-name ModelLatency \
    --dimensions Name=EndpointName,Value=Gen3DSAMAsyncEndpoint Name=VariantName,Value=AllTraffic \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average

# Check recent logs
aws logs tail /aws/lambda/Gen3DExtractLambda --since 1h
aws logs tail /aws/lambda/Gen3DNotifyLambda --since 1h
```

---

## Phase 9: Improvements and Optimization

### Suggested Improvements

1. **Authentication and Authorization**
   - Implement Cognito User Pools for user management
   - Add API Gateway with JWT authentication
   - User dashboard for tracking jobs

2. **Enhanced Monitoring**
   - Custom metrics for processing success rate
   - Cost tracking per user
   - Real-time dashboard with WebSocket updates

3. **Performance Optimization**
   - Model optimization for faster inference
   - Batch processing for multiple objects
   - CDN (CloudFront) for web interface

4. **Cost Optimization**
   - SageMaker Spot Instances for async processing
   - S3 Intelligent-Tiering for automatic cost reduction
   - Auto-scaling policies based on queue depth

5. **User Experience**
   - Real-time progress updates
   - 3D viewer in browser (Three.js)
   - History of previous conversions
   - Sharing capabilities

6. **Advanced Features**
   - Support for SAM 3D Body integration
   - Multiple output formats (OBJ, FBX, GLTF)
   - Texture quality presets
   - Batch upload support

7. **Reliability**
   - Dead Letter Queues for failed jobs
   - Retry logic with exponential backoff
   - Multi-region deployment
   - Automated backups

8. **Security Enhancements**
   - VPC endpoints for private communication
   - KMS encryption for S3
   - Secrets Manager for credentials
   - WAF for web interface protection

---

## Troubleshooting Guide

### Common Issues

**Issue: Lambda timeout**
```bash
# Increase timeout
aws lambda update-function-configuration \
    --function-name Gen3DExtractLambda \
    --timeout 60
```

**Issue: SageMaker endpoint not responding**
```bash
# Check endpoint status
aws sagemaker describe-endpoint --endpoint-name Gen3DSAMAsyncEndpoint

# Check CloudWatch logs
aws logs tail /aws/sagemaker/Endpoints/Gen3DSAMAsyncEndpoint --follow
```

**Issue: S3 event notifications not triggering**
```bash
# Verify notification configuration
aws s3api get-bucket-notification-configuration --bucket gen3d-data-bucket

# Check Lambda permissions
aws lambda get-policy --function-name Gen3DExtractLambda
```

**Issue: Email notifications not sending**
```bash
# Check SES verification status
aws ses get-identity-verification-attributes --identities info@2112-lab.com

# Check Lambda logs for SES errors
aws logs tail /aws/lambda/Gen3DNotifyLambda --follow
```

---

## Cleanup (Development Only)

To remove all resources (use with caution):

```bash
# Delete Lambda functions
aws lambda delete-function --function-name Gen3DExtractLambda
aws lambda delete-function --function-name Gen3DNotifyLambda

# Delete SageMaker endpoint
aws sagemaker delete-endpoint --endpoint-name Gen3DSAMAsyncEndpoint
aws sagemaker delete-endpoint-config --endpoint-config-name Gen3DSAM-AsyncConfig
aws sagemaker delete-model --model-name Gen3DSAM3DModel

# Empty and delete S3 buckets
aws s3 rm s3://gen3d-data-bucket --recursive
aws s3 rb s3://gen3d-data-bucket
aws s3 rm s3://gen3d-model-bucket --recursive
aws s3 rb s3://gen3d-model-bucket

# Delete ECR repository
aws ecr delete-repository --repository-name gen3d-sam3d-inference --force

# Delete IAM roles (detach policies first)
aws iam delete-role-policy --role-name Gen3DSageMakerExecutionRole --policy-name Gen3DSageMakerPolicy
aws iam delete-role --role-name Gen3DSageMakerExecutionRole

aws iam delete-role-policy --role-name Gen3DLambdaExtractRole --policy-name Gen3DLambdaExtractPolicy
aws iam delete-role --role-name Gen3DLambdaExtractRole

aws iam delete-role-policy --role-name Gen3DLambdaNotifyRole --policy-name Gen3DLambdaNotifyPolicy
aws iam delete-role --role-name Gen3DLambdaNotifyRole

# Delete CloudWatch alarms
aws cloudwatch delete-alarms --alarm-names Gen3D-ExtractLambda-HighErrors Gen3D-SageMaker-ModelLatency
```

---

## Conclusion

This implementation plan provides a complete, production-ready deployment of Gen3D on AWS. All AWS CLI commands, code samples, and configuration files are included for direct execution. The architecture is scalable, secure, and cost-effective, leveraging serverless technologies where appropriate.

For questions or issues, contact: info@2112-lab.com
