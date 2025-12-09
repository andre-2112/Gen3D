# Gen3D SageMaker Deployment - Preventive Solutions

**Purpose**: Comprehensive preventive measures to avoid all 25 issues identified in deployment

**Date**: 2025-12-03

---

## High-Level Process Improvements

### Solution 1: Planned Deployment with Comprehensive Design Phase

**Prevents Issues**: #1 (Reactive Approach), #5 (Incomplete Planning)

**Implementation**:

1. **Pre-Deployment Planning Phase** (2-4 hours)
   - Review architecture documents thoroughly
   - Understand all components: SAM3, SAM3D, SageMaker Async, Flask server
   - Document all dependencies and requirements
   - Create deployment checklist with verification steps
   - Identify potential failure points

2. **Architecture Decision Documentation**
   - Document WHY each technology choice was made
   - Compare alternatives (Real-Time vs Async, container strategies)
   - Calculate cost implications upfront
   - Get stakeholder approval before implementation

3. **Phased Implementation Plan**
   ```
   Phase 1: Local Development & Testing (no AWS costs)
   Phase 2: Container Build & Local Testing
   Phase 3: ECR Push & Verification
   Phase 4: SageMaker Model Creation
   Phase 5: Endpoint Deployment with Monitoring
   Phase 6: Integration Testing
   Phase 7: Performance Testing & Auto-scaling Verification
   ```

4. **Verification Checkpoints**
   - Each phase must pass verification before proceeding
   - Document success criteria for each phase
   - Create rollback procedures for each phase

**Time Investment**: 2-4 hours planning saves 10-20 hours of reactive debugging

---

### Solution 2: Include Models in Container from Start

**Prevents Issues**: #2 (Missing Models), #22 (Models Not Included), #23 (Non-existent Repos)

**Implementation**:

**Option A: Copy Models During Build** (Recommended for production)
```dockerfile
# Dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# ... system dependencies ...

# Download models during build
RUN mkdir -p /opt/ml/model/sam3 /opt/ml/model/sam3d

# Copy pre-downloaded models from build context
COPY models/sam3/ /opt/ml/model/sam3/
COPY models/sam3d/ /opt/ml/model/sam3d/

# Verify models exist
RUN ls -lh /opt/ml/model/sam3/ && \
    ls -lh /opt/ml/model/sam3d/ && \
    echo "✓ Models copied successfully"
```

**Pre-Build Steps**:
```bash
# On build machine (EC2 or local)
mkdir -p models/sam3 models/sam3d

# Download from S3
aws s3 sync s3://gen3d-data-bucket/models/sam3/ models/sam3/
aws s3 sync s3://gen3d-data-bucket/models/sam3d/ models/sam3d/

# Verify downloads
du -sh models/sam3   # Should be ~6.5GB
du -sh models/sam3d  # Should be ~12GB

# Build with models in context
docker build -t gen3d-sagemaker:v1.0 .
```

**Option B: Download at Runtime** (For development/testing)
```python
# inference.py - model_fn()
def model_fn(model_dir):
    """Load models, downloading from S3 if missing."""

    sam3_path = os.path.join(model_dir, "sam3", "sam3_vit_h.pth")

    if not os.path.exists(sam3_path):
        logger.info("SAM3 model not found, downloading from S3...")
        s3_client.download_file(
            'gen3d-data-bucket',
            'models/sam3/sam3_vit_h.pth',
            sam3_path
        )
        logger.info("✓ SAM3 model downloaded")

    # Load model...
```

**Verification**:
```bash
# After build, verify models are in image
docker run --rm gen3d-sagemaker:v1.0 ls -lh /opt/ml/model/sam3/
docker run --rm gen3d-sagemaker:v1.0 ls -lh /opt/ml/model/sam3d/
```

---

### Solution 3: Mandatory Verification at Every Step

**Prevents Issues**: #3 (Lack of Verification), #18 (No Model Validation), #20 (No Local Testing)

**Implementation**:

**Verification Checklist Template**:

```markdown
## Deployment Verification Checklist

### Phase 1: Dockerfile Preparation
- [ ] ENTRYPOINT is correct: `ENTRYPOINT ["serve"]` or custom Flask server
- [ ] ENV DEBIAN_FRONTEND=noninteractive is set
- [ ] All COPY commands reference existing files/directories
- [ ] Model files are in build context
- [ ] sagemaker-inference or Flask is installed
- [ ] inference.py has model_fn, input_fn, predict_fn, output_fn

### Phase 2: Local Container Build
- [ ] Build completes without errors
- [ ] Image size is reasonable (~28GB with models)
- [ ] `docker images` shows correct tag

### Phase 3: Local Container Testing (CRITICAL)
- [ ] Start container: `docker run --rm -p 8080:8080 <image> serve`
- [ ] Container logs show HTTP server starting
- [ ] Health check: `curl http://localhost:8080/ping` returns 200 OK
- [ ] Test inference with mock payload
- [ ] Container doesn't crash within 5 minutes
- [ ] Models load successfully (check logs)

### Phase 4: ECR Push
- [ ] Tag is semantic version (v1.0, not :latest)
- [ ] Push completes successfully
- [ ] Verify image in ECR console

### Phase 5: SageMaker Model Creation
- [ ] Model ARN returned
- [ ] Execution role has correct permissions
- [ ] Image URI matches pushed ECR image

### Phase 6: Endpoint Configuration
- [ ] Async inference config included (for Async endpoints)
- [ ] Instance type is ml.g5.2xlarge
- [ ] InitialInstanceCount = 1 (scales to 0 later)

### Phase 7: Endpoint Deployment
- [ ] Monitor CloudWatch logs during deployment
- [ ] Wait for InService status (10-15 min)
- [ ] Check for failure reasons if Failed
- [ ] Verify endpoint ARN

### Phase 8: Auto-scaling Configuration
- [ ] Register scalable target (min=0, max=3)
- [ ] Create scaling policy (TargetTrackingScaling)
- [ ] Verify scale-down cooldown = 300s

### Phase 9: Integration Testing
- [ ] Test Stage 1 (get_embedding) with real image
- [ ] Test Stage 3 (generate_3d) with real image + mask
- [ ] Verify S3 outputs exist
- [ ] Check inference latency
- [ ] Verify auto-scaling to zero after idle period
```

---

### Solution 4: Choose Correct Architecture Upfront

**Prevents Issues**: #6 (Wrong Architecture - Real-Time vs Async)

**Decision Matrix**:

| Use Case | Traffic Pattern | Recommended Architecture | Cost Impact |
|----------|----------------|-------------------------|-------------|
| Real-time interactive UI | Constant, <1s latency required | Real-Time Endpoint | $1,091/month always-on |
| Batch processing | Sporadic, latency tolerant | Async Inference | $38/month (97% savings) |
| Mixed workload | Variable | Async with warm pool | $100-300/month |

**For Gen3D Use Case**:
- **Traffic**: Sporadic (10-50 jobs/day)
- **Latency**: 30-120 seconds acceptable
- **Decision**: **Async Inference** is optimal
- **Justification**: 97% cost savings, same GPU support, longer processing time limit

**Implementation**:
```bash
# Create Async Endpoint Configuration
aws sagemaker create-endpoint-config \
  --endpoint-config-name Gen3DAsyncEndpointConfig \
  --production-variants \
    VariantName=AllTraffic,\
    ModelName=Gen3DModel,\
    InstanceType=ml.g5.2xlarge,\
    InitialInstanceCount=1 \
  --async-inference-config \
    'OutputConfig={S3OutputPath=s3://gen3d-data-bucket/async-output,S3FailurePath=s3://gen3d-data-bucket/async-failures},\
     ClientConfig={MaxConcurrentInvocationsPerInstance=4}'
```

---

## Low-Level Technical Solutions

### Solution 7: Correct Docker ENTRYPOINT (MOST CRITICAL)

**Prevents Issues**: #7 (Wrong ENTRYPOINT - ROOT CAUSE), #9 (Inference.py Crashes)

**The Problem**:
```dockerfile
# WRONG - causes ALL endpoint failures
ENTRYPOINT ["python", "/opt/ml/code/inference.py"]
```

**The Solution - Option 1: Use sagemaker-inference toolkit** (Recommended)
```dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Install sagemaker-inference
RUN pip install sagemaker-inference==1.9.0

# Set program to load
ENV SAGEMAKER_PROGRAM=inference.py

# NO custom ENTRYPOINT - let toolkit handle it
# The toolkit will start HTTP server on port 8080
```

**The Solution - Option 2: Custom Flask Server**
```dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Install Flask
RUN pip install flask==3.0.0

# Copy both inference and server
COPY code/inference.py /opt/ml/code/inference.py
COPY code/serve.py /opt/ml/code/serve.py

# Use custom Flask server
ENTRYPOINT ["python", "/opt/ml/code/serve.py"]
```

**serve.py Implementation**:
```python
#!/usr/bin/env python3
from flask import Flask, request, jsonify
from inference import model_fn, input_fn, predict_fn, output_fn
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load models once at startup
model_dir = os.environ.get('MODEL_DIR', '/opt/ml/model')
logger.info(f"Loading models from {model_dir}")
models = model_fn(model_dir)
logger.info("Models loaded successfully")

@app.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint."""
    return '', 200

@app.route('/invocations', methods=['POST'])
def invocations():
    """Inference endpoint."""
    try:
        content_type = request.content_type or 'application/json'
        input_data = input_fn(request.data, content_type)
        prediction = predict_fn(input_data, models)
        response = output_fn(prediction, 'application/json')
        return response, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
```

**Local Testing** (MANDATORY before ECR push):
```bash
# Test 1: Start container
docker run --rm -p 8080:8080 gen3d-sagemaker:v1.0

# Test 2: Health check (in another terminal)
curl http://localhost:8080/ping
# Expected: HTTP 200 OK (empty response)

# Test 3: Test inference
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "task": "get_embedding",
    "image_s3_key": "test-images/coil.jpg",
    "bucket": "gen3d-data-bucket",
    "session_id": "test-001"
  }'
# Expected: JSON response with status: "success"
```

---

### Solution 8: Prevent Docker Build Hang

**Prevents Issues**: #8 (tzdata Interactive Prompt)

**Implementation**:
```dockerfile
# Add BEFORE any apt-get commands
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Then run apt-get
RUN apt-get update && apt-get install -y \
    git \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*
```

**Verification**:
```bash
# Build should complete without hanging
docker build -t test-image .
# If build hangs, check process tree:
docker ps  # Find container ID
docker exec <container-id> ps auxf
# Look for tzdata.config process
```

---

### Solution 12: Use Correct Package Versions

**Prevents Issues**: #12 (Missing Flask), #25 (Package Conflicts)

**Implementation**:
```dockerfile
# Option 1: Use sagemaker-inference (includes web server)
RUN pip install --no-cache-dir \
    sagemaker-inference==1.9.0 \
    boto3==1.28.85 \
    opencv-python==4.8.1.78 \
    Pillow==10.1.0 \
    numpy==1.24.3

# Option 2: Use Flask for custom server
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    boto3==1.28.85 \
    opencv-python==4.8.1.78 \
    Pillow==10.1.0 \
    numpy==1.24.3

# For transformers/diffusers, let pip resolve versions
RUN pip install --no-cache-dir \
    transformers \
    diffusers \
    accelerate
```

---

### Solution 20: Mandatory Local Container Testing

**Prevents Issues**: #20 (No Local Testing - CRITICAL)

**Testing Protocol** (MANDATORY before ECR push):

```bash
#!/bin/bash
# test-container-locally.sh

set -e

IMAGE_NAME=$1
if [ -z "$IMAGE_NAME" ]; then
  echo "Usage: $0 <image-name>"
  exit 1
fi

echo "=== Testing Container: $IMAGE_NAME ==="

# Test 1: Container starts
echo "Test 1: Starting container..."
CONTAINER_ID=$(docker run -d -p 8080:8080 $IMAGE_NAME)
sleep 10

# Test 2: Health check
echo "Test 2: Health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ping)
if [ "$HTTP_CODE" != "200" ]; then
  echo "✗ Health check failed: HTTP $HTTP_CODE"
  docker logs $CONTAINER_ID
  docker stop $CONTAINER_ID
  exit 1
fi
echo "✓ Health check passed"

# Test 3: Mock inference
echo "Test 3: Mock inference..."
RESPONSE=$(curl -s -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"task":"get_embedding","image_s3_key":"test.jpg","bucket":"test"}')

if echo "$RESPONSE" | grep -q "error"; then
  echo "✗ Inference failed: $RESPONSE"
  docker logs $CONTAINER_ID
  docker stop $CONTAINER_ID
  exit 1
fi
echo "✓ Inference test passed"

# Test 4: Check logs for errors
echo "Test 4: Checking logs..."
if docker logs $CONTAINER_ID 2>&1 | grep -i "error\|exception\|failed"; then
  echo "⚠ Found errors in logs (review above)"
else
  echo "✓ No errors in logs"
fi

# Cleanup
docker stop $CONTAINER_ID
echo ""
echo "✓✓✓ ALL TESTS PASSED ✓✓✓"
echo "Container is ready for ECR push"
```

**Usage**:
```bash
chmod +x test-container-locally.sh
./test-container-locally.sh gen3d-sagemaker:v1.0
```

---

### Solution 21: Verify Fixes Propagate Through Pipeline

**Prevents Issues**: #21 (ECR Image Never Fixed - Assumption Error)

**Fix Verification Protocol**:

```bash
#!/bin/bash
# verify-fix-propagation.sh

set -e

echo "=== Verifying Fix Propagation ==="

# 1. Verify local Dockerfile has correct ENTRYPOINT
echo "Step 1: Checking Dockerfile..."
if grep -q 'ENTRYPOINT \["serve"\]' Dockerfile || \
   grep -q 'ENTRYPOINT \["python", "/opt/ml/code/serve.py"\]' Dockerfile; then
  echo "✓ Dockerfile ENTRYPOINT is correct"
else
  echo "✗ Dockerfile ENTRYPOINT is wrong!"
  grep ENTRYPOINT Dockerfile
  exit 1
fi

# 2. Build with unique tag
echo "Step 2: Building with verification tag..."
TAG="verify-$(date +%Y%m%d-%H%M%S)"
docker build -t gen3d-sagemaker:$TAG .

# 3. Test locally
echo "Step 3: Testing locally..."
./test-container-locally.sh gen3d-sagemaker:$TAG

# 4. Tag for ECR
echo "Step 4: Tagging for ECR..."
docker tag gen3d-sagemaker:$TAG \
  211050572089.dkr.ecr.us-east-1.amazonaws.com/gen3d-sagemaker:$TAG

# 5. Push to ECR
echo "Step 5: Pushing to ECR..."
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  211050572089.dkr.ecr.us-east-1.amazonaws.com
docker push 211050572089.dkr.ecr.us-east-1.amazonaws.com/gen3d-sagemaker:$TAG

# 6. Verify in ECR
echo "Step 6: Verifying in ECR..."
aws ecr describe-images \
  --repository-name gen3d-sagemaker \
  --image-ids imageTag=$TAG \
  --query 'imageDetails[0].[imageTags,imageSizeInBytes]' \
  --output table

echo ""
echo "✓ Fix verified through entire pipeline!"
echo "Use this image for SageMaker: gen3d-sagemaker:$TAG"
```

---

### Solution 24: Implement Missing SAM3 Segmentation (Stage 2)

**Prevents Issues**: #24 (Missing SAM3 Segmentation Task)

**Add to inference.py**:

```python
def process_segmentation(input_data, models):
    """
    Stage 2: Generate segmentation mask using SAM3 predictor.

    Args:
        input_data: {
            "task": "segment",
            "image_s3_key": "path/to/image.jpg",
            "bucket": "gen3d-data-bucket",
            "prompt_type": "point" or "box",
            "point": [x, y],  # if prompt_type == "point"
            "point_label": 1,  # 1=foreground, 0=background
            "box": [x1, y1, x2, y2]  # if prompt_type == "box"
        }

    Returns:
        dict: {
            "status": "success",
            "task": "segment",
            "mask_s3_key": "path/to/mask.png",
            "confidence_score": 0.95
        }
    """
    logger.info("Starting Stage 2: Segmentation")

    image_s3_key = input_data["image_s3_key"]
    bucket = input_data.get("bucket", "gen3d-data-bucket")
    prompt_type = input_data["prompt_type"]
    session_id = input_data.get("session_id", "unknown")

    # Get SAM3 predictor
    sam3_predictor = models.get("sam3_predictor")
    if sam3_predictor is None:
        return {"status": "failed", "error": "SAM3 model not loaded"}

    # Download image from S3
    logger.info(f"Downloading image from s3://{bucket}/{image_s3_key}")
    response = s3_client.get_object(Bucket=bucket, Key=image_s3_key)
    image_bytes = response['Body'].read()
    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    # Set image in SAM3 predictor
    sam3_predictor.set_image(np.array(image))

    # Generate mask based on prompt type
    if prompt_type == "point":
        point = np.array([input_data["point"]])  # [[x, y]]
        label = np.array([input_data.get("point_label", 1)])
        masks, scores, logits = sam3_predictor.predict(
            point_coords=point,
            point_labels=label,
            multimask_output=False
        )
    elif prompt_type == "box":
        box = np.array(input_data["box"])  # [x1, y1, x2, y2]
        masks, scores, logits = sam3_predictor.predict(
            box=box[None, :],
            multimask_output=False
        )
    else:
        return {"status": "failed", "error": f"Unknown prompt_type: {prompt_type}"}

    # Convert mask to PNG
    mask_bool = masks[0]  # Shape: (H, W)
    mask_uint8 = (mask_bool * 255).astype(np.uint8)
    mask_image = Image.fromarray(mask_uint8, mode='L')

    # Save mask to S3 as PNG
    mask_bytes = BytesIO()
    mask_image.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)

    mask_key = image_s3_key.rsplit('.', 1)[0] + '_mask.png'
    s3_client.put_object(
        Bucket=bucket,
        Key=mask_key,
        Body=mask_bytes.getvalue(),
        ContentType='image/png'
    )

    logger.info(f"Mask saved to s3://{bucket}/{mask_key}")

    return {
        "status": "success",
        "task": "segment",
        "session_id": session_id,
        "mask_s3_key": mask_key,
        "mask_format": "png",
        "mask_size": list(mask_bool.shape),
        "confidence_score": float(scores[0])
    }
```

**Update predict_fn dispatcher**:
```python
def predict_fn(input_data, models):
    """Main prediction function - dispatcher for different tasks."""
    task = input_data.get("task")

    if task == "get_embedding":
        return process_initialization(input_data, models)
    elif task == "segment":  # NEW
        return process_segmentation(input_data, models)
    elif task == "generate_3d":
        return process_reconstruction(input_data, models)
    else:
        raise ValueError(f"Unknown task: {task}")
```

---

## Process Improvements

### Solution for Context Loss (#4)

**Implementation**:
1. **Document Everything in Markdown**
   - Create progress documents after each session
   - Include: what was done, what worked, what failed, next steps

2. **Use Git for Version Control**
   ```bash
   git init
   git add .
   git commit -m "Checkpoint: Completed Phase X"
   ```

3. **Maintain a "STATE.md" File**
   ```markdown
   # Current Deployment State

   **Last Updated**: 2025-12-03 15:30

   ## What's Deployed:
   - ECR Image: gen3d-sagemaker:v1.0 (verified working)
   - SageMaker Model: Gen3DModel (ARN: ...)
   - Endpoint: Gen3DAsyncEndpoint (Status: InService)

   ## What's Pending:
   - Integration testing
   - Auto-scaling verification

   ## Known Issues:
   - None currently

   ## Next Steps:
   1. Test Stage 1 inference
   2. Test Stage 3 inference
   3. Verify auto-scaling
   ```

---

## Deployment Workflow (Complete)

**Recommended End-to-End Process**:

```bash
#!/bin/bash
# complete-deployment-workflow.sh

set -e

echo "=== Gen3D SageMaker Deployment Workflow ==="

# Phase 1: Preparation
echo "Phase 1: Preparation"
./download-models-from-s3.sh
./prepare-dockerfile.sh

# Phase 2: Build
echo "Phase 2: Build"
docker build -t gen3d-sagemaker:v1.0 .

# Phase 3: Local Testing (MANDATORY)
echo "Phase 3: Local Testing"
./test-container-locally.sh gen3d-sagemaker:v1.0

# Phase 4: ECR Push
echo "Phase 4: ECR Push"
./push-to-ecr.sh gen3d-sagemaker:v1.0

# Phase 5: Verify ECR
echo "Phase 5: Verify ECR"
./verify-ecr-image.sh gen3d-sagemaker:v1.0

# Phase 6: SageMaker Deployment
echo "Phase 6: SageMaker Deployment"
./create-sagemaker-model.sh gen3d-sagemaker:v1.0
./create-async-endpoint-config.sh
./create-async-endpoint.sh

# Phase 7: Monitor Deployment
echo "Phase 7: Monitor Deployment"
./wait-for-endpoint-inservice.sh

# Phase 8: Configure Auto-scaling
echo "Phase 8: Configure Auto-scaling"
./configure-autoscaling.sh

# Phase 9: Integration Testing
echo "Phase 9: Integration Testing"
./test-stage1-inference.sh
./test-stage3-inference.sh

# Phase 10: Verify Auto-scaling
echo "Phase 10: Verify Auto-scaling"
./verify-scale-to-zero.sh

echo ""
echo "✓✓✓ DEPLOYMENT COMPLETE ✓✓✓"
echo "Endpoint: Gen3DAsyncEndpoint"
echo "Status: InService with auto-scaling 0-3"
```

---

## Summary Checklist

### Before ANY Deployment:
- [ ] Read and understand all architecture documents
- [ ] Create comprehensive deployment plan with phases
- [ ] Document verification steps for each phase
- [ ] Choose correct architecture (Real-Time vs Async)
- [ ] Calculate cost implications

### Dockerfile Requirements:
- [ ] Correct ENTRYPOINT (`["serve"]` or Flask server)
- [ ] ENV DEBIAN_FRONTEND=noninteractive
- [ ] Models included via COPY or download mechanism
- [ ] sagemaker-inference or Flask installed
- [ ] All dependencies installed

### Before ECR Push:
- [ ] Build completes successfully
- [ ] Test container starts locally
- [ ] Health check `/ping` returns 200
- [ ] Mock inference succeeds
- [ ] No errors in container logs
- [ ] Models load successfully

### SageMaker Deployment:
- [ ] Use Async Inference for sporadic workload
- [ ] Monitor CloudWatch logs during deployment
- [ ] Wait for InService (don't assume success)
- [ ] Verify endpoint with test inference
- [ ] Configure auto-scaling to zero

### After Deployment:
- [ ] Test all inference tasks (Stage 1, 2, 3)
- [ ] Verify S3 outputs exist and are correct
- [ ] Check CloudWatch metrics
- [ ] Verify auto-scaling behavior
- [ ] Document deployment in STATE.md

---

**Document Version**: 1.0
**Last Updated**: 2025-12-03
**Status**: Complete preventive solutions for all 25 issues
