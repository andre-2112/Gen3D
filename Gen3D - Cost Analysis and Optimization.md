# Gen3D - Cost Analysis and Optimization Guide

## 🚨 CRITICAL COST ISSUE IDENTIFIED

The original cost estimate of **$544/month** assumes the SageMaker endpoint runs **24/7**, which is **WRONG** for an async inference architecture!

---

## Current (Incorrect) Cost Breakdown

### Original Estimate: $544.13/month

| Service | Cost | % of Total | Issue |
|---------|------|------------|-------|
| **SageMaker** | **$537.28** | **98.7%** | 🔴 Assumes 24/7 runtime! |
| Lambda | $0.04 | 0.01% | ✅ Correct |
| S3 | $2.31 | 0.4% | ✅ Reasonable |
| ECR | $1.00 | 0.2% | ✅ Correct |
| CloudWatch | $2.50 | 0.5% | ✅ Reasonable |
| SES | $1.00 | 0.2% | ✅ Correct |

**Problem**: 98.7% of costs come from SageMaker running continuously!

---

## ❌ Why Current Approach is Wrong

### Issue: SageMaker Endpoint Always Running

```
Current Setup:
┌─────────────────────────────────────────┐
│  SageMaker Endpoint (ml.g4dn.xlarge)   │
│  Status: ALWAYS RUNNING                 │
│  Cost: $0.736/hour × 730 hours         │
│  = $537/month                           │
└─────────────────────────────────────────┘
```

**Problems**:
1. ❌ Endpoint runs even when no requests (idle 90%+ of time)
2. ❌ Paying for GPU that's not being used
3. ❌ This is NOT how async inference should work
4. ❌ Defeats the purpose of "async" architecture

### How Async SHOULD Work

```
Optimized Setup:
┌─────────────────────────────────────────┐
│  SageMaker Async Endpoint               │
│  Status: SCALES TO ZERO when idle       │
│  Cost: Only pay for actual processing   │
│  = ~$10-50/month (depending on usage)   │
└─────────────────────────────────────────┘
```

---

## ✅ CORRECTED Cost Analysis

### Realistic Usage Scenario

**Assumptions**:
- 100 images processed per month (realistic for initial deployment)
- Each inference takes 60 seconds (1 minute)
- Total processing time: 100 minutes = 1.67 hours/month

### Option 1: SageMaker Async with Auto-Scaling to Zero

#### Configuration:
```json
{
  "AutoScalingConfig": {
    "MinCapacity": 0,  // Scale to zero!
    "MaxCapacity": 1,
    "ScaleDownDelay": 300  // 5 minutes
  }
}
```

#### Cost Breakdown:

| Service | Calculation | Monthly Cost |
|---------|-------------|--------------|
| **SageMaker Compute** | $0.736/hour × 1.67 hours | **$1.23** |
| **SageMaker Idle Time** | $0.736/hour × ~2 hours (startup/shutdown) | **$1.47** |
| Lambda (Extract) | $0.20/million requests × 100 | $0.00002 |
| Lambda (Notify) | $0.20/million requests × 100 | $0.00002 |
| S3 Storage | $0.023/GB × 10 GB | $0.23 |
| S3 Requests | $0.0004/1000 × 200 | $0.0001 |
| ECR Storage | $0.10/GB × 10 GB | $1.00 |
| CloudWatch Logs | $0.50/GB × 0.5 GB | $0.25 |
| SES Emails | $0.10/1000 × 100 | $0.01 |

**Total: ~$4.19/month** (100 images/month)

**Savings: 99.2% ($540 saved!)**

---

### Option 2: SageMaker Serverless Inference (RECOMMENDED)

SageMaker Serverless is **perfect** for Gen3D's use case!

#### Why Serverless is Better:

✅ **No idle costs** - Pay only for inference time
✅ **Automatic scaling** - Handles 0 to 100+ concurrent requests
✅ **No cold starts** - AWS keeps model warm
✅ **Memory-based pricing** - Choose 1GB-6GB RAM

#### Configuration:
```python
ServerlessConfig={
    'MemorySizeInMB': 4096,  # 4GB RAM
    'MaxConcurrency': 5       # Max parallel requests
}
```

#### Cost Breakdown (Serverless):

| Component | Rate | Usage | Monthly Cost |
|-----------|------|-------|--------------|
| **Inference Duration** | $0.0000133/second per GB | 100 images × 60s × 4GB | **$3.19** |
| Lambda | As above | 100 invocations | $0.00004 |
| S3 | As above | 10 GB + requests | $0.23 |
| ECR | As above | 10 GB | $1.00 |
| CloudWatch | As above | 0.5 GB | $0.25 |
| SES | As above | 100 emails | $0.01 |

**Total: ~$4.68/month** (100 images/month)

**Savings: 99.1% ($540 saved!)**

---

### Option 3: On-Demand Endpoint with Lambda Start/Stop

Keep endpoint stopped until needed, start via Lambda.

#### How it Works:
```
1. User uploads image → S3
2. Lambda checks: Is endpoint running?
3. If NO → Start endpoint (takes 5 minutes)
4. Wait for endpoint to be ready
5. Invoke inference
6. After 10 minutes idle → Stop endpoint
```

#### Cost Breakdown:

| Service | Monthly Cost |
|---------|--------------|
| **SageMaker** (only when running) | ~$2.50 |
| Lambda (with longer execution) | $0.05 |
| S3 | $0.23 |
| ECR | $1.00 |
| CloudWatch | $0.25 |
| SES | $0.01 |

**Total: ~$4.04/month**

**Downside**: 5-minute wait time for first request after idle
**Upside**: Lowest cost

---

## 📊 Cost Comparison by Usage Level

### Monthly Cost by Number of Images Processed:

| Images/Month | 24/7 Endpoint | Serverless | Auto-Scale-to-0 | Savings |
|--------------|---------------|------------|-----------------|---------|
| 10 | $537.28 | $1.50 | $0.80 | 99.7% |
| 50 | $537.28 | $3.25 | $2.10 | 99.6% |
| **100** | **$537.28** | **$4.68** | **$4.19** | **99.2%** |
| 500 | $537.28 | $18.50 | $15.40 | 97.1% |
| 1,000 | $537.28 | $35.00 | $29.80 | 94.5% |
| 5,000 | $537.28 | $165.00 | $145.00 | 73.0% |
| 10,000 | $537.28 | $320.00 | $285.00 | 46.9% |

**Break-even point**: ~8,000 images/month (after that, 24/7 endpoint becomes competitive)

---

## 🎯 RECOMMENDED ARCHITECTURE

### For Most Users: SageMaker Serverless

**Perfect for**:
- ✅ Low to medium volume (< 5,000 images/month)
- ✅ Sporadic usage patterns
- ✅ Minimal operational overhead
- ✅ No capacity planning needed
- ✅ No cold start concerns

**Implementation**:
```python
# Replace Step 3.9 in Implementation Plan

import boto3

sagemaker = boto3.client('sagemaker')

# Create serverless endpoint config
sagemaker.create_endpoint_config(
    EndpointConfigName='Gen3DSAM-ServerlessConfig',
    ProductionVariants=[{
        'VariantName': 'AllTraffic',
        'ModelName': 'Gen3DSAM3DModel',
        'ServerlessConfig': {
            'MemorySizeInMB': 4096,  # 4GB
            'MaxConcurrency': 5,     # Max parallel requests
            'ProvisionedConcurrency': 1  # Optional: keep 1 warm
        }
    }]
)

# Create endpoint
sagemaker.create_endpoint(
    EndpointName='Gen3DSAMServerlessEndpoint',
    EndpointConfigName='Gen3DSAM-ServerlessConfig'
)
```

**Cost**: ~$5-10/month for typical usage

---

### For High Volume: Auto-Scaling with Scale-to-Zero

**Perfect for**:
- ✅ Predictable high volume (>5,000 images/month)
- ✅ Batch processing windows
- ✅ Need consistent performance
- ✅ Want to optimize costs

**Implementation**:
```python
# Add auto-scaling configuration to Step 3.9

import boto3

# After creating endpoint, configure auto-scaling
autoscaling = boto3.client('application-autoscaling')

# Register scalable target
autoscaling.register_scalable_target(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/Gen3DSAMAsyncEndpoint/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    MinCapacity=0,  # Scale to zero!
    MaxCapacity=3   # Scale up to 3 instances
)

# Create scaling policy
autoscaling.put_scaling_policy(
    PolicyName='Gen3DSAMScalingPolicy',
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/Gen3DSAMAsyncEndpoint/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 5.0,  # Target 5 invocations per instance
        'CustomizedMetricSpecification': {
            'MetricName': 'ApproximateBacklogSizePerInstance',
            'Namespace': 'AWS/SageMaker',
            'Statistic': 'Average',
        },
        'ScaleInCooldown': 600,   # 10 minutes before scaling down
        'ScaleOutCooldown': 300   # 5 minutes before scaling up
    }
)
```

**Cost**: ~$4-50/month depending on volume

---

## 💡 Additional Cost Optimization Strategies

### 1. Use Spot Instances (70% Savings)

**For**: ml.g4dn.xlarge instances

```python
ProductionVariants=[{
    'VariantName': 'AllTraffic',
    'ModelName': 'Gen3DSAM3DModel',
    'InstanceType': 'ml.g4dn.xlarge',
    'InitialInstanceCount': 1,
    'ManagedInstanceScaling': {
        'Status': 'ENABLED',
        'MinInstanceCount': 0,
        'MaxInstanceCount': 2
    },
    # Enable Spot instances
    'EnableManagedSpotTraining': True,
    'MaxRuntimeInSeconds': 3600
}]
```

**Savings**: ~70% on compute costs
**Risk**: Possible interruption (rare for inference workloads)

---

### 2. Optimize Model Size

**Current**: Full SAM 3D model (~8GB)
**Optimized**: Quantized or pruned model (~2-4GB)

**Methods**:
- INT8 quantization (PyTorch)
- Model pruning
- Knowledge distillation

**Benefits**:
- Smaller instance size needed
- Faster loading time
- Lower memory costs (for serverless)

**Implementation**:
```python
# After Phase 3A local testing, add model optimization

import torch
from torch.quantization import quantize_dynamic

# Load model
model = load_sam3d_model("checkpoints/hf/pipeline.yaml")

# Quantize to INT8
quantized_model = quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)

# Test quantized model (Phase 3A)
# If accuracy is acceptable, use quantized version

# Save quantized model
torch.save(quantized_model.state_dict(), "checkpoints/quantized/model.pth")
```

**Savings**: 30-50% on inference costs

---

### 3. Use Cheaper Instance Types

**Current**: ml.g4dn.xlarge (GPU)
**Consider**: ml.g4dn.2xlarge or ml.g5.xlarge

| Instance | vCPU | GPU | RAM | Cost/Hour | Use Case |
|----------|------|-----|-----|-----------|----------|
| ml.g4dn.xlarge | 4 | 1×T4 (16GB) | 16GB | $0.736 | Current |
| ml.g4dn.2xlarge | 8 | 1×T4 (16GB) | 32GB | $0.94 | Batch processing |
| ml.g5.xlarge | 4 | 1×A10G (24GB) | 16GB | $1.408 | Better performance |
| **ml.g4dn.xlarge (Spot)** | 4 | 1×T4 (16GB) | 16GB | **$0.22** | **Recommended** |

**Recommendation**: Use ml.g4dn.xlarge with Spot pricing

---

### 4. Implement Request Batching

Process multiple images in one inference call:

**Without Batching**:
```
100 images × 60 seconds = 100 minutes compute time
```

**With Batching (5 images per batch)**:
```
20 batches × 90 seconds = 30 minutes compute time
Savings: 70%
```

**Implementation**:
```python
# Modify sagemaker_handler.py to accept multiple images

def predict_fn(input_data, model):
    # Check if batch request
    if 'images' in input_data:  # Batch
        outputs = []
        for img, mask in zip(input_data['images'], input_data['masks']):
            output = model.inference(img, mask)
            outputs.append(output)
        return {'outputs': outputs, 'metadata': input_data['metadata']}
    else:  # Single image
        # Original code
        pass
```

**Savings**: 50-70% on compute time

---

### 5. Use S3 Intelligent-Tiering

Automatically move old files to cheaper storage:

```bash
aws s3api put-bucket-lifecycle-configuration \
    --bucket gen3d-data-bucket \
    --lifecycle-configuration file://lifecycle.json
```

**lifecycle.json**:
```json
{
  "Rules": [{
    "Id": "Move-to-IA-then-Glacier",
    "Status": "Enabled",
    "Transitions": [
      {
        "Days": 30,
        "StorageClass": "STANDARD_IA"
      },
      {
        "Days": 90,
        "StorageClass": "GLACIER"
      }
    ],
    "Expiration": {
      "Days": 365
    }
  }]
}
```

**Savings**: ~68% on storage costs for old files

---

### 6. Optimize CloudWatch Logs

**Current**: Indefinite retention
**Optimized**: 30-day retention for logs

```bash
aws logs put-retention-policy \
    --log-group-name /aws/lambda/Gen3DExtractLambda \
    --retention-in-days 30

aws logs put-retention-policy \
    --log-group-name /aws/lambda/Gen3DNotifyLambda \
    --retention-in-days 30
```

**Savings**: ~70% on CloudWatch costs

---

### 7. Use SES in Bulk

For high email volume:

**Current**: $0.10 per 1,000 emails
**Optimized**:
- First 62,000 emails FREE (if sent from EC2)
- After that: $0.10 per 1,000

**No change needed**, just be aware of free tier.

---

## 📋 Complete Optimized Cost Breakdown

### Recommended: Serverless + All Optimizations

**Assumptions**: 100 images/month

| Service | Optimization | Original | Optimized | Savings |
|---------|--------------|----------|-----------|---------|
| SageMaker | Serverless | $537.28 | $3.19 | 99.4% |
| Lambda | (already optimized) | $0.04 | $0.04 | 0% |
| S3 | Intelligent-Tiering | $2.31 | $0.73 | 68% |
| ECR | (no optimization) | $1.00 | $1.00 | 0% |
| CloudWatch | 30-day retention | $2.50 | $0.75 | 70% |
| SES | (already free tier) | $1.00 | $0.00 | 100% |
| **TOTAL** | | **$544.13** | **$5.71** | **98.9%** |

**Monthly Cost**: ~$6 (vs $544 = 99% savings!)

---

## 🚀 Implementation: How to Switch to Optimized Architecture

### Step 1: Update Implementation Plan Step 3.9

**Replace the endpoint configuration with serverless**:

```bash
# File: Gen3D - Implementation Plan - 1.1.md
# Section: Step 3.9

# OLD (Don't use):
aws sagemaker create-endpoint-config \
    --endpoint-config-name Gen3DSAM-AsyncConfig \
    --production-variants '[{"VariantName":"AllTraffic","ModelName":"Gen3DSAM3DModel","InstanceType":"ml.g4dn.xlarge","InitialInstanceCount":1}]'

# NEW (Use this):
aws sagemaker create-endpoint-config \
    --endpoint-config-name Gen3DSAM-ServerlessConfig \
    --production-variants '[{
        "VariantName":"AllTraffic",
        "ModelName":"Gen3DSAM3DModel",
        "ServerlessConfig":{
            "MemorySizeInMB":4096,
            "MaxConcurrency":5
        }
    }]'
```

### Step 2: Add Auto-Scaling (Alternative to Serverless)

If you prefer traditional instances with scale-to-zero:

```bash
# After creating endpoint, add auto-scaling
cat > /tmp/autoscaling-config.json << 'EOF'
{
  "TargetValue": 5.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
  },
  "ScaleInCooldown": 600,
  "ScaleOutCooldown": 300
}
EOF

aws application-autoscaling register-scalable-target \
    --service-namespace sagemaker \
    --resource-id endpoint/Gen3DSAMAsyncEndpoint/variant/AllTraffic \
    --scalable-dimension sagemaker:variant:DesiredInstanceCount \
    --min-capacity 0 \
    --max-capacity 2

aws application-autoscaling put-scaling-policy \
    --policy-name Gen3DSAMScalingPolicy \
    --service-namespace sagemaker \
    --resource-id endpoint/Gen3DSAMAsyncEndpoint/variant/AllTraffic \
    --scalable-dimension sagemaker:variant:DesiredInstanceCount \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration file:///tmp/autoscaling-config.json
```

### Step 3: Update Lambda Environment Variables

```bash
# Update endpoint name if using serverless
aws lambda update-function-configuration \
    --function-name Gen3DExtractLambda \
    --environment "Variables={
        SAGEMAKER_ENDPOINT_NAME=Gen3DSAMServerlessEndpoint,
        DATA_BUCKET=gen3d-data-bucket,
        ADMIN_EMAIL=info@2112-lab.com
    }"
```

### Step 4: Implement S3 Lifecycle

```bash
# Apply the lifecycle policy from optimization #5
aws s3api put-bucket-lifecycle-configuration \
    --bucket gen3d-data-bucket \
    --lifecycle-configuration file:///tmp/lifecycle.json
```

### Step 5: Update CloudWatch Retention

```bash
# Set 30-day retention for all log groups
for log_group in "/aws/lambda/Gen3DExtractLambda" "/aws/lambda/Gen3DNotifyLambda" "/gen3d/application"; do
    aws logs put-retention-policy \
        --log-group-name $log_group \
        --retention-in-days 30
done
```

---

## 📊 Cost Monitoring and Alerts

### Set Up Cost Alerts

```bash
aws budgets create-budget \
    --account-id $AWS_ACCOUNT_ID \
    --budget file://budget.json
```

**budget.json**:
```json
{
  "BudgetName": "Gen3D-Monthly-Budget",
  "BudgetLimit": {
    "Amount": "20",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {
    "TagKeyValue": ["Project$Gen3D"]
  }
}
```

### Create CloudWatch Dashboard for Costs

Monitor costs in real-time through CloudWatch.

---

## 🎯 Decision Matrix

### Which Option Should You Choose?

| Scenario | Recommended | Expected Cost |
|----------|-------------|---------------|
| Just starting, <100 images/month | **Serverless** | $5-10/month |
| Growing, 100-1000 images/month | **Serverless** | $10-40/month |
| Established, 1000-5000 images/month | **Auto-Scale-to-0** | $30-150/month |
| High volume, >5000 images/month | **24/7 with Auto-Scale** | $150-400/month |
| Enterprise, >10000 images/month | **24/7 Reserved Instances** | $300-500/month |

---

## Summary

### Key Takeaways:

1. ✅ **Original estimate was WRONG** - Assumed 24/7 operation
2. ✅ **Serverless is PERFECT** for Gen3D use case
3. ✅ **99% cost savings** possible with proper configuration
4. ✅ **$5-10/month** realistic for typical usage
5. ✅ **No functionality loss** - same performance, lower cost

### Action Items:

1. ✅ Use SageMaker Serverless (Step 3.9 in Implementation Plan)
2. ✅ Enable S3 Intelligent-Tiering
3. ✅ Set CloudWatch log retention to 30 days
4. ✅ Monitor costs with CloudWatch and AWS Budgets
5. ✅ Consider model optimization for further savings

### Updated Cost Estimate:

| Usage Level | Monthly Cost | Annual Cost |
|-------------|--------------|-------------|
| Low (100 images) | $6 | $72 |
| Medium (1000 images) | $35 | $420 |
| High (5000 images) | $165 | $1,980 |

**vs Original**: $544/month ($6,528/year)

---

*Document Version: 1.0*
*Created: 2025-11-27*
*Purpose: Critical cost correction for Gen3D deployment*
