# Gen3D SageMaker Deployment - Implementation Plan for Fixes

**Date**: 2025-12-03
**Status**: READY FOR EXECUTION
**Estimated Time**: 90-120 minutes
**Prerequisites**: EC2 instance i-042ca5d5485788c84 running, AWS credentials configured

---

## Executive Summary

This document provides step-by-step instructions to fix the critical SAM3/SAM3D model loading issues in the Gen3D SageMaker deployment. All root causes have been identified, and fixed files have been created.

**What We Fixed**:
1. Added SAM3 and SAM3D package installations to Dockerfile
2. Enhanced inference.py with comprehensive logging and automatic checkpoint detection
3. Removed mock data fallback (fail explicitly instead)
4. Added support for multiple checkpoint formats (.pt, .pth, .safetensors, .ckpt)

---

## Files Created

### 1. Fixed Dockerfile
**Location**: `deployment/04-sagemaker/Dockerfile.fixed`

**Key Changes**:
- Added SAM3 installation (tries PyPI, falls back to GitHub)
- Added SAM3D installation (from GitHub repository)
- Added safetensors library
- Includes fallback to segment-anything if sam3 fails

### 2. Fixed Inference Script
**Location**: `deployment/04-sagemaker/code/inference.fixed.py`

**Key Changes**:
- Enhanced logging (80+ additional log statements)
- Automatic checkpoint file detection
- Directory structure logging for debugging
- Support for multiple checkpoint formats
- Explicit error messages (no more mock data)
- Alternative import paths for SAM packages

### 3. Diagnostic Report
**Location**: `DIAGNOSTIC_REPORT_SAM3_SAM3D.md`

**Contents**:
- Complete test results from EC2
- Root cause analysis
- Model file inventory
- Impact assessment

---

## Implementation Steps

### Phase 1: Prepare Fixed Files on EC2 (15 mins)

**Step 1.1**: Upload fixed Dockerfile to EC2

```bash
# From local machine
export AWS_PROFILE=genesis3d
export AWS_REGION=us-east-1

# Upload to S3 as intermediary
aws s3 cp "deployment/04-sagemaker/Dockerfile.fixed" \
  s3://gen3d-data-bucket/temp/Dockerfile

# Copy from S3 to EC2
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["aws s3 cp s3://gen3d-data-bucket/temp/Dockerfile /root/sagemaker-build/Dockerfile"]' \
  --query 'Command.CommandId' \
  --output text)

# Wait and check result
sleep 5
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84
```

**Step 1.2**: Upload fixed inference.py to EC2

```bash
# Upload to S3
aws s3 cp "deployment/04-sagemaker/code/inference.fixed.py" \
  s3://gen3d-data-bucket/temp/inference.py

# Copy from S3 to EC2
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["aws s3 cp s3://gen3d-data-bucket/temp/inference.py /root/sagemaker-build/code/inference.py"]' \
  --query 'Command.CommandId' \
  --output text)

# Wait and check result
sleep 5
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84
```

**Step 1.3**: Verify files are in place

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /root/sagemaker-build && ls -lh Dockerfile code/inference.py"]' \
  --query 'Command.CommandId' \
  --output text)

sleep 3
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text
```

**Expected Output**: Both files listed with recent timestamps

---

### Phase 2: Rebuild Container on EC2 (20-30 mins)

**Step 2.1**: Clean up old test containers

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker stop gen3d-test 2>/dev/null || true && sudo docker rm gen3d-test 2>/dev/null || true"]' \
  --query 'Command.CommandId' \
  --output text)
```

**Step 2.2**: Start Docker build

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /root/sagemaker-build && sudo docker build --tag gen3d-sagemaker:fixed-v2.0 --file Dockerfile --progress=plain . 2>&1 | tee build-fixed-v2.0.log"]' \
  --query 'Command.CommandId' \
  --output text)

echo "Build started with command ID: $COMMAND_ID"
echo "This will take 20-30 minutes..."
```

**Step 2.3**: Monitor build progress

```bash
# Check every 2 minutes
for i in {1..15}; do
  echo "=== Check $i at $(date +%H:%M:%S) ==="
  aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id i-042ca5d5485788c84 \
    --query 'Status' \
    --output text

  # If completed, show output
  STATUS=$(aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id i-042ca5d5485788c84 \
    --query 'Status' \
    --output text)

  if [ "$STATUS" == "Success" ] || [ "$STATUS" == "Failed" ]; then
    echo "Build completed with status: $STATUS"
    aws ssm get-command-invocation \
      --command-id $COMMAND_ID \
      --instance-id i-042ca5d5485788c84 \
      --query 'StandardOutputContent' \
      --output text | tail -50
    break
  fi

  sleep 120
done
```

**Step 2.4**: Verify image built

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker images | grep fixed-v2.0"]' \
  --query 'Command.CommandId' \
  --output text)

sleep 3
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text
```

**Expected Output**:
```
gen3d-sagemaker  fixed-v2.0  [IMAGE_ID]  [timestamp]  ~27-28GB
```

**Success Criteria**:
- Image size is 27-28 GB (models included)
- Build completed without errors
- No "failed" messages in build log

---

### Phase 3: Local Container Testing (10 mins)

**Step 3.1**: Start test container and capture startup logs

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /root/sagemaker-build && sudo docker run -d --name gen3d-test-v2 -p 8080:8080 --env MODEL_DIR=/opt/ml/model gen3d-sagemaker:fixed-v2.0 && sleep 15 && sudo docker logs gen3d-test-v2 2>&1"]' \
  --query 'Command.CommandId' \
  --output text)

sleep 20
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text > container-startup-logs-v2.txt

cat container-startup-logs-v2.txt
```

**Step 3.2**: Analyze startup logs

Look for these KEY INDICATORS:

✓ **SUCCESS indicators**:
```
✓ SAM3 library imported successfully
✓ Found SAM3 checkpoint: /opt/ml/model/sam3/sam3.pt
✓✓✓ SAM3 LOADED SUCCESSFULLY!
✓ SAM3D library imported successfully
✓ Found SAM3D checkpoint: /opt/ml/model/sam3d/checkpoints/...
✓✓✓ SAM3D LOADED SUCCESSFULLY!
MODEL LOADING COMPLETE
SAM3 loaded: True
SAM3D loaded: True
```

✗ **FAILURE indicators** (need to fix):
```
✗✗✗ SAM3 IMPORT ERROR - PACKAGE NOT INSTALLED
No module named 'sam3'
✗✗✗ SAM3D IMPORT ERROR - PACKAGE NOT INSTALLED
No module named 'sam3d'
SAM3 loaded: False
SAM3D loaded: False
```

**Step 3.3**: Check container status

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker ps | grep gen3d-test-v2"]' \
  --query 'Command.CommandId' \
  --output text)

sleep 3
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text
```

**Expected**: Container shows "Up" status

---

### Phase 4: Model Loading Verification (5 mins)

**Step 4.1**: Get detailed model loading logs

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker logs gen3d-test-v2 2>&1 | grep -A 5 \"SAM3 LOADED\\|SAM3D LOADED\\|MODEL LOADING COMPLETE\""]' \
  --query 'Command.CommandId' \
  --output text)

sleep 3
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text
```

**Step 4.2**: Check for errors

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker logs gen3d-test-v2 2>&1 | grep -i \"ERROR\\|CRITICAL\" | head -20"]' \
  --query 'Command.CommandId' \
  --output text)

sleep 3
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id i-042ca5d5485788c84 \
  --query 'StandardOutputContent' \
  --output text
```

**Expected**: No CRITICAL errors, maybe warnings about CPU vs GPU

---

### Phase 5: Decision Point - If Models Don't Load

**If SAM3/SAM3D packages still fail to install** (imports still fail):

This means the packages don't exist on PyPI or GitHub as expected. You have two options:

#### Option A: Use Original Segment Anything (SAM v1)

The Dockerfile already has a fallback to install `segment-anything`. This is Facebook's original SAM model.

**Action**: Update inference.py to use SAM instead of SAM3:

```python
# In model_fn(), SAM3 loading section
try:
    from segment_anything import sam_model_registry, SamPredictor
    # Use sam_model_registry["vit_h"] as before
    # This should work with the fallback installation
except ImportError:
    logger.error("Could not import segment_anything")
```

#### Option B: Skip SAM Installation, Use Only Checkpoint Files

If SAM packages don't exist, create a minimal loader that just loads the PyTorch checkpoint:

```python
# Minimal SAM3 loader (no package needed)
import torch

checkpoint = torch.load("/opt/ml/model/sam3/sam3.pt", map_location=device)
# Use checkpoint directly
```

**Decision needed at this point** - check which option works

---

### Phase 6: ECR Push (If Tests Pass) (15 mins)

**Only proceed if Phase 3-4 tests showed models loading successfully**

**Step 6.1**: Tag for ECR

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker tag gen3d-sagemaker:fixed-v2.0 211050572089.dkr.ecr.us-east-1.amazonaws.com/gen3d-sagemaker:v2.0"]' \
  --query 'Command.CommandId' \
  --output text)
```

**Step 6.2**: Login to ECR and push

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids i-042ca5d5485788c84 \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["aws ecr get-login-password --region us-east-1 | sudo docker login --username AWS --password-stdin 211050572089.dkr.ecr.us-east-1.amazonaws.com && sudo docker push 211050572089.dkr.ecr.us-east-1.amazonaws.com/gen3d-sagemaker:v2.0"]' \
  --query 'Command.CommandId' \
  --output text)

echo "Push started with command ID: $COMMAND_ID"
echo "This will take 10-15 minutes for ~28GB image..."
```

**Step 6.3**: Monitor push progress

```bash
# Check every minute
for i in {1..20}; do
  echo "=== Check $i at $(date +%H:%M:%S) ==="
  STATUS=$(aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id i-042ca5d5485788c84 \
    --query 'Status' \
    --output text)

  echo "Status: $STATUS"

  if [ "$STATUS" == "Success" ] || [ "$STATUS" == "Failed" ]; then
    break
  fi

  sleep 60
done
```

**Step 6.4**: Verify in ECR

```bash
aws ecr describe-images \
  --repository-name gen3d-sagemaker \
  --image-ids imageTag=v2.0 \
  --query 'imageDetails[0].{Tag:imageTags[0],Size:imageSizeInBytes,Pushed:imagePushedAt}' \
  --output json
```

**Expected**: Image v2.0 exists, size ~27-28 GB

---

### Phase 7: SageMaker Deployment (20 mins)

**Step 7.1**: Delete old endpoint (if exists)

```bash
aws sagemaker delete-endpoint --endpoint-name Gen3DAsyncEndpointV1 2>/dev/null || true
sleep 30
```

**Step 7.2**: Create new model

```bash
aws sagemaker create-model \
  --model-name Gen3DModelV2 \
  --primary-container Image=211050572089.dkr.ecr.us-east-1.amazonaws.com/gen3d-sagemaker:v2.0 \
  --execution-role-arn arn:aws:iam::211050572089:role/Gen3DSageMakerRole \
  --output json
```

**Step 7.3**: Create endpoint config

```bash
aws sagemaker create-endpoint-config \
  --endpoint-config-name Gen3DAsyncEndpointConfigV2 \
  --production-variants \
    VariantName=AllTraffic,ModelName=Gen3DModelV2,InstanceType=ml.g5.2xlarge,InitialInstanceCount=1 \
  --async-inference-config '{
    "OutputConfig": {
      "S3OutputPath": "s3://gen3d-data-bucket/async-output",
      "S3FailurePath": "s3://gen3d-data-bucket/async-failures"
    },
    "ClientConfig": {
      "MaxConcurrentInvocationsPerInstance": 4
    }
  }' \
  --output json
```

**Step 7.4**: Create endpoint

```bash
echo "Creating endpoint at $(date)"

aws sagemaker create-endpoint \
  --endpoint-name Gen3DAsyncEndpointV2 \
  --endpoint-config-name Gen3DAsyncEndpointConfigV2 \
  --output json

echo "Monitoring deployment (10-15 minutes)..."
```

**Step 7.5**: Monitor endpoint deployment

```bash
for i in {1..30}; do
  echo "=== Check $i at $(date +%H:%M:%S) ==="

  STATUS=$(aws sagemaker describe-endpoint \
    --endpoint-name Gen3DAsyncEndpointV2 \
    --query 'EndpointStatus' \
    --output text 2>&1)

  echo "Status: $STATUS"

  if [ "$STATUS" == "InService" ]; then
    echo ""
    echo "✓✓✓ SUCCESS! Endpoint is InService!"
    break
  elif [ "$STATUS" == "Failed" ]; then
    echo ""
    echo "✗✗✗ FAILED! Endpoint deployment failed."
    echo "Failure reason:"
    aws sagemaker describe-endpoint \
      --endpoint-name Gen3DAsyncEndpointV2 \
      --query 'FailureReason' \
      --output text
    exit 1
  fi

  sleep 30
done
```

---

### Phase 8: CloudWatch Log Verification (5 mins)

**CRITICAL**: Even if endpoint is InService, check if models actually loaded

**Step 8.1**: Get CloudWatch log stream

```bash
LOG_GROUP="/aws/sagemaker/Endpoints/Gen3DAsyncEndpointV2"

# Wait for logs to appear
sleep 60

# Get latest log stream
LATEST_STREAM=$(aws logs describe-log-streams \
  --log-group-name $LOG_GROUP \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text)

echo "Latest log stream: $LATEST_STREAM"
```

**Step 8.2**: Check for model loading success

```bash
aws logs filter-log-events \
  --log-group-name $LOG_GROUP \
  --log-stream-names $LATEST_STREAM \
  --filter-pattern "SAM3 LOADED\\|SAM3D LOADED\\|MODEL LOADING COMPLETE" \
  --query 'events[*].message' \
  --output text
```

**Expected Output**:
```
✓✓✓ SAM3 LOADED SUCCESSFULLY!
✓✓✓ SAM3D LOADED SUCCESSFULLY!
MODEL LOADING COMPLETE
SAM3 loaded: True
SAM3D loaded: True
```

**Step 8.3**: Check for errors

```bash
aws logs filter-log-events \
  --log-group-name $LOG_GROUP \
  --log-stream-names $LATEST_STREAM \
  --filter-pattern "ERROR\\|CRITICAL" \
  --query 'events[*].message' \
  --output text | head -20
```

**Expected**: No CRITICAL errors about import failures

---

### Phase 9: End-to-End Testing (10 mins)

**Step 9.1**: Upload test image to S3

```bash
# Create a simple test image
echo "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mNk+M9Qz0AEYBxVSF+FAAD4AQMBGQdDkQAAAABJRU5ErkJggg==" | base64 -d > test-image.png

aws s3 cp test-image.png s3://gen3d-data-bucket/test-data/test-image.png
```

**Step 9.2**: Create test payload

```bash
cat > test-payload-v2.json << 'EOF'
{
  "task": "get_embedding",
  "image_s3_key": "test-data/test-image.png",
  "bucket": "gen3d-data-bucket",
  "session_id": "test-v2-001",
  "user_id": "admin-test"
}
EOF

# Upload payload
aws s3 cp test-payload-v2.json s3://gen3d-data-bucket/async-input/test-payload-v2.json
```

**Step 9.3**: Invoke async endpoint

```bash
RESPONSE=$(aws sagemaker-runtime invoke-endpoint-async \
  --endpoint-name Gen3DAsyncEndpointV2 \
  --input-location s3://gen3d-data-bucket/async-input/test-payload-v2.json \
  --content-type "application/json" \
  --output json)

echo "$RESPONSE"

# Extract output location
OUTPUT_LOCATION=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['OutputLocation'])")
echo "Output will be at: $OUTPUT_LOCATION"
```

**Step 9.4**: Wait for and check result

```bash
echo "Waiting for inference to complete (max 2 minutes)..."

for i in {1..24}; do
  # Check output location
  if aws s3 ls "$OUTPUT_LOCATION" 2>/dev/null; then
    echo "✓ Response received!"
    aws s3 cp "$OUTPUT_LOCATION" - | python3 -m json.tool
    break
  fi

  # Check failure location
  FAILURE_LOCATION="${OUTPUT_LOCATION/async-output/async-failures}"
  FAILURE_LOCATION="${FAILURE_LOCATION/.out/-error.out}"

  if aws s3 ls "$FAILURE_LOCATION" 2>/dev/null; then
    echo "✗ Inference failed!"
    aws s3 cp "$FAILURE_LOCATION" - | python3 -m json.tool
    exit 1
  fi

  echo "  Waiting... ($i/24)"
  sleep 5
done
```

**Step 9.5**: Analyze result

**SUCCESS indicators**:
```json
{
  "status": "success",
  "task": "get_embedding",
  "output_s3_key": "test-data/embeddings.json",
  "embedding_size_mb": 1.2
}
```

**FAILURE indicators**:
```json
{
  "status": "failed",
  "error": "SAM3 model not loaded...",
  "note": "Model loading failed during container startup..."
}
```

---

## Success Criteria Checklist

Before declaring deployment successful, verify ALL of these:

- [ ] Container builds without errors (Phase 2)
- [ ] Container starts and stays running (Phase 3)
- [ ] Flask server listening on port 8080 (Phase 3)
- [ ] SAM3 package imported successfully (Phase 4)
- [ ] SAM3D package imported successfully (Phase 4)
- [ ] SAM3 checkpoint file found and loaded (Phase 4)
- [ ] SAM3D checkpoint file found and loaded (Phase 4)
- [ ] No "No module named" errors in logs (Phase 4)
- [ ] Image pushed to ECR successfully (Phase 6)
- [ ] SageMaker endpoint reaches InService (Phase 7)
- [ ] CloudWatch logs show models loaded (Phase 8)
- [ ] Test inference returns real data (not mock) (Phase 9)
- [ ] No error files in S3 failure location (Phase 9)

**Current Target**: 13/13 checks must pass

---

## Troubleshooting Guide

### Problem: SAM3/SAM3D packages still fail to import

**Symptoms**: Logs show "No module named 'sam3'" or "No module named 'sam3d'"

**Solutions**:
1. Check build logs for package installation errors
2. Try installing segment-anything instead (already in Dockerfile as fallback)
3. Use direct PyTorch checkpoint loading (bypass package entirely)
4. Consult SAM documentation for correct package names

### Problem: Checkpoints not found

**Symptoms**: "No SAM3 checkpoint found" or "No SAM3D checkpoint found"

**Solutions**:
1. Check logs for actual file paths being searched
2. Verify models were copied during build
3. Use the auto-detection feature in fixed inference.py
4. Check if checkpoint files have different names

### Problem: Container builds but models fail on GPU

**Symptoms**: Works on CPU (EC2 t3.xlarge) but fails on GPU (ml.g5.2xlarge)

**Solutions**:
1. Check CUDA compatibility
2. Verify PyTorch CUDA version matches
3. Check model loading uses .to(device) correctly
4. Review GPU memory requirements

### Problem: Endpoint deployment fails

**Symptoms**: SageMaker endpoint status goes to "Failed"

**Solutions**:
1. Check failure reason: `aws sagemaker describe-endpoint --endpoint-name Gen3DAsyncEndpointV2 --query 'FailureReason'`
2. Review CloudWatch logs for startup errors
3. Verify IAM role permissions
4. Check if ECR image is accessible

---

## Rollback Procedures

### If Local Tests Fail (Phase 3-5)

**Action**: Don't proceed to ECR push
1. Review container logs
2. Fix issues in Dockerfile or inference.py
3. Rebuild and retest locally
4. Only push to ECR after local tests pass

### If SageMaker Deployment Fails (Phase 7)

**Action**: Delete failed endpoint and revert

```bash
# Delete failed endpoint
aws sagemaker delete-endpoint --endpoint-name Gen3DAsyncEndpointV2

# Delete failed model
aws sagemaker delete-model --model-name Gen3DModelV2

# Delete endpoint config
aws sagemaker delete-endpoint-config --endpoint-config-name Gen3DAsyncEndpointConfigV2

# Use previous working version (if any)
# Or go back to local testing
```

### If End-to-End Tests Fail (Phase 9)

**Action**: Diagnose via CloudWatch logs

```bash
# Get all logs from endpoint
aws logs tail /aws/sagemaker/Endpoints/Gen3DAsyncEndpointV2 \
  --since 30m \
  --format short

# Look for specific errors
aws logs filter-log-events \
  --log-group-name /aws/sagemaker/Endpoints/Gen3DAsyncEndpointV2 \
  --filter-pattern "ERROR\\|Exception\\|Failed" \
  --start-time $(date -u -d '30 minutes ago' +%s)000
```

---

## Expected Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 1. Prepare files | 15 mins | 15 mins |
| 2. Rebuild container | 20-30 mins | 45 mins |
| 3. Local testing | 10 mins | 55 mins |
| 4. Model verification | 5 mins | 60 mins |
| 5. Decision point | 5-10 mins | 70 mins |
| 6. ECR push | 15 mins | 85 mins |
| 7. SageMaker deploy | 20 mins | 105 mins |
| 8. Log verification | 5 mins | 110 mins |
| 9. End-to-end test | 10 mins | 120 mins |

**Total**: 90-120 minutes (assuming no major issues)

---

## Next Steps After Successful Deployment

1. **Configure Auto-Scaling**: Set min=0, max=3 for cost savings
2. **Set Up Monitoring**: CloudWatch alarms for failures
3. **Create Test Suite**: Automated tests for both tasks
4. **Document API**: Update documentation with working examples
5. **Stop EC2 Instance**: Save ~$121/month

---

## Document Status

**Status**: READY FOR EXECUTION
**Created**: 2025-12-03
**Version**: 1.0
**Last Updated**: 2025-12-03

---

**Sources Referenced**:
- [SAM3 on PyPI](https://pypi.org/project/sam3/)
- [SAM3 on GitHub](https://github.com/facebookresearch/sam3)
- [SAM 3D Objects on GitHub](https://github.com/facebookresearch/sam-3d-objects)
- [SAM 3D Body on GitHub](https://github.com/facebookresearch/sam-3d-body)
