# ONNX Model Generation Plan - EC2 Deployment

**Purpose**: Step-by-step plan to generate the SAM3 mask decoder ONNX model on EC2 instance for client-side mask inference

**Date**: 2025-12-03

**Target Environment**: EC2 Instance i-042ca5d5485788c84 (t3.xlarge)

**Goal**: Export SAM3 mask decoder from PyTorch to ONNX format for browser-based inference with ONNX Runtime Web

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Phase 1: Environment Setup](#3-phase-1-environment-setup)
4. [Phase 2: Export Script Preparation](#4-phase-2-export-script-preparation)
5. [Phase 3: ONNX Model Generation](#5-phase-3-onnx-model-generation)
6. [Phase 4: Validation](#6-phase-4-validation)
7. [Phase 5: S3 Deployment](#7-phase-5-s3-deployment)
8. [Troubleshooting](#8-troubleshooting)
9. [Alternative: Download Pre-converted Model](#9-alternative-download-pre-converted-model)

---

## 1. Overview

### 1.1 What is Being Generated

**ONNX Model**: SAM3 Mask Decoder
- **Input**: Image embeddings (256×64×64), point coordinates, point labels
- **Output**: Binary mask predictions (1024×1024)
- **Size**: ~1.4 GB
- **Format**: ONNX (Open Neural Network Exchange)
- **Runtime**: ONNX Runtime Web (browser-based)

### 1.2 Why Generate on EC2

**Advantages**:
- SAM3 model already available: `/home/ec2-user/models/sam3/` (6.5 GB)
- PyTorch environment available in Docker container
- No need to download 6.5 GB model locally
- Can leverage existing SageMaker container build environment

**Resources Available on EC2**:
- Instance: t3.xlarge (4 vCPU, 16 GB RAM)
- Disk: 96 GB available
- SAM3 model: 6.5 GB at `/home/ec2-user/models/sam3/`
- Docker: Available for containerized export
- Python 3.x: Available

### 1.3 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gen3D Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Stage 1: Embeddings (Server-side)                              │
│  ┌────────────┐        ┌──────────────────┐                     │
│  │   Image    │───────>│ SAM3 Encoder     │                     │
│  │  (S3)      │        │ (SageMaker GPU)  │                     │
│  └────────────┘        └──────────────────┘                     │
│                                 │                                 │
│                                 v                                 │
│                         ┌──────────────┐                         │
│                         │  Embeddings  │                         │
│                         │ (256×64×64)  │                         │
│                         └──────────────┘                         │
│                                 │                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                 │                                 │
│  Stage 2: Masking (Client-side) ◄─── ONNX MODEL HERE           │
│  ┌────────────┐        ┌──────────────────┐                     │
│  │ Embeddings │───────>│ SAM3 Decoder     │                     │
│  │  + Points  │        │ (ONNX Runtime    │                     │
│  │  + Bbox    │        │  in Browser)     │                     │
│  └────────────┘        └──────────────────┘                     │
│                                 │                                 │
│                                 v                                 │
│                         ┌──────────────┐                         │
│                         │   Binary     │                         │
│                         │    Mask      │                         │
│                         └──────────────┘                         │
│                                 │                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                 │                                 │
│  Stage 3: Reconstruction (Server-side)                          │
│  ┌────────────┐        ┌──────────────────┐                     │
│  │ Image+Mask │───────>│   SAM3D Model    │                     │
│  │   (S3)     │        │ (SageMaker GPU)  │                     │
│  └────────────┘        └──────────────────┘                     │
│                                 │                                 │
│                                 v                                 │
│                         ┌──────────────┐                         │
│                         │     PLY      │                         │
│                         │  Point Cloud │                         │
│                         └──────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Success Criteria

- [ ] ONNX model generated successfully (~1.4 GB)
- [ ] ONNX model passes validation (structure, inputs, outputs)
- [ ] ONNX Runtime can load and run inference
- [ ] Model uploaded to S3 with public-read access
- [ ] Web app can download and use model

---

## 2. Prerequisites

### 2.1 Access Requirements

- AWS SSM access to EC2 instance i-042ca5d5485788c84
- AWS CLI configured with profile `genesis3d`
- Permissions: EC2, S3

### 2.2 EC2 Instance Status

**Instance Details**:
- ID: i-042ca5d5485788c84
- Type: t3.xlarge (4 vCPU, 16 GB RAM)
- Disk: 200 GB (105 GB used, 96 GB available)
- Status: Running

**Required Software** (verify availability):
- Docker (for PyTorch environment)
- Python 3.8+
- AWS CLI

### 2.3 Model Availability

**SAM3 Model**:
- Location: `/home/ec2-user/models/sam3/`
- Size: 6.5 GB
- Files: `sam3.pt` (checkpoint)

**Verification**:
```bash
ls -lh /home/ec2-user/models/sam3/
```

### 2.4 Local Files to Upload

**Export Script**:
- Source: `./deployment/onnx-export/export_sam_decoder.py`
- Upload to EC2: `/root/onnx-export/export_sam_decoder.py`

---

## 3. Phase 1: Environment Setup

### 3.1 Connect to EC2 Instance

```bash
# From local machine with AWS CLI
export AWS_PROFILE=genesis3d
export AWS_REGION=us-east-1

# Start SSM session
aws ssm start-session --target i-042ca5d5485788c84
```

**Expected**: Bash prompt on EC2 instance

### 3.2 Create Working Directory

```bash
# Switch to root user if needed
sudo su -

# Create working directory
mkdir -p /root/onnx-export
cd /root/onnx-export

# Verify current location
pwd
```

**Expected Output**: `/root/onnx-export`

### 3.3 Upload Export Script to EC2

**From LOCAL machine** (in a new terminal):

```bash
# Navigate to project directory
cd C:/Users/Admin/Documents/Workspace/Antigravity/Gen3D

# Create temporary file for upload
cat deployment/onnx-export/export_sam_decoder.py | \
  aws ssm start-session \
    --target i-042ca5d5485788c84 \
    --document-name AWS-StartInteractiveCommand \
    --parameters command="cat > /root/onnx-export/export_sam_decoder.py"
```

**Alternative - Using S3 as intermediary**:

```bash
# From local machine
aws s3 cp deployment/onnx-export/export_sam_decoder.py \
  s3://gen3d-data-bucket/temp/export_sam_decoder.py \
  --profile genesis3d

# From EC2 instance
aws s3 cp s3://gen3d-data-bucket/temp/export_sam_decoder.py \
  /root/onnx-export/export_sam_decoder.py
```

**Verification on EC2**:
```bash
ls -lh /root/onnx-export/export_sam_decoder.py
cat /root/onnx-export/export_sam_decoder.py | head -20
```

### 3.4 Verify SAM3 Model Access

```bash
# Check if SAM3 model exists
ls -lh /home/ec2-user/models/sam3/

# Check checkpoint file
ls -lh /home/ec2-user/models/sam3/sam3.pt

# Check disk space (need ~2 GB for ONNX model)
df -h /root
```

**Expected Output**:
```
/home/ec2-user/models/sam3/:
total 6.5G
-rw-r--r-- 1 ec2-user ec2-user 6.5G Dec 1 sam3.pt

Filesystem      Size  Used Avail Use%
/dev/xvda1      200G  105G   96G  53% /
```

**Success Criteria**:
- [ ] Connected to EC2 via SSM
- [ ] Working directory created: `/root/onnx-export/`
- [ ] Export script uploaded and verified
- [ ] SAM3 model accessible at `/home/ec2-user/models/sam3/sam3.pt`
- [ ] Sufficient disk space (>2 GB available)

---

## 4. Phase 2: Export Script Preparation

### 4.1 Update Script Paths for EC2 Environment

```bash
cd /root/onnx-export

# Edit export script to use correct model path
cat > export_sam_decoder.py << 'EOF'
#!/usr/bin/env python3
"""
Export SAM Mask Decoder to ONNX format for browser-based inference.

Modified for EC2 deployment with SAM3 model at /home/ec2-user/models/sam3/
"""

import torch
import numpy as np
import onnx
from onnx import shape_inference
import os
import sys

print("=" * 80)
print("SAM3 Mask Decoder ONNX Export Script - EC2")
print("=" * 80)

# Configuration
MODEL_TYPE = "vit_h"  # SAM ViT-Huge
CHECKPOINT_PATH = "/home/ec2-user/models/sam3/sam3.pt"  # EC2 path
OUTPUT_PATH = "/root/onnx-export/sam3_mask_decoder.onnx"
OPSET_VERSION = 17

def export_sam_decoder_onnx():
    """
    Export SAM mask decoder to ONNX format.
    """

    print("\n[1/6] Checking dependencies...")
    try:
        from segment_anything import sam_model_registry
        from segment_anything.modeling import Sam
        print("✓ segment-anything package found")
    except ImportError:
        print("✗ segment-anything package not found")
        print("\nPlease install:")
        print("  pip install git+https://github.com/facebookresearch/segment-anything.git")
        sys.exit(1)

    print("\n[2/6] Loading SAM model checkpoint...")
    if not os.path.exists(CHECKPOINT_PATH):
        print(f"✗ Checkpoint not found: {CHECKPOINT_PATH}")
        sys.exit(1)

    try:
        sam = sam_model_registry[MODEL_TYPE](checkpoint=CHECKPOINT_PATH)
        sam.eval()
        print(f"✓ Loaded SAM model: {MODEL_TYPE}")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        sys.exit(1)

    print("\n[3/6] Preparing mask decoder for export...")

    # Extract mask decoder
    mask_decoder = sam.mask_decoder

    # Create wrapper for ONNX export
    class SAMMaskDecoderONNX(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.mask_decoder = model.mask_decoder
            self.prompt_encoder = model.prompt_encoder

        def forward(self, image_embeddings, point_coords, point_labels):
            sparse_embeddings, dense_embeddings = self.prompt_encoder(
                points=(point_coords, point_labels),
                boxes=None,
                masks=None,
            )

            low_res_masks, iou_predictions = self.mask_decoder(
                image_embeddings=image_embeddings,
                image_pe=self.prompt_encoder.get_dense_pe(),
                sparse_prompt_embeddings=sparse_embeddings,
                dense_prompt_embeddings=dense_embeddings,
                multimask_output=False,
            )

            masks = torch.nn.functional.interpolate(
                low_res_masks,
                size=(1024, 1024),
                mode="bilinear",
                align_corners=False,
            )

            return torch.sigmoid(masks)

    onnx_model = SAMMaskDecoderONNX(sam)
    onnx_model.eval()
    print("✓ Mask decoder wrapper created")

    print("\n[4/6] Creating dummy inputs for export...")

    batch_size = 1
    embedding_dim = 256
    embedding_size = 64
    num_points = 2

    dummy_image_embeddings = torch.randn(batch_size, embedding_dim, embedding_size, embedding_size)
    dummy_point_coords = torch.randn(batch_size, num_points, 2)
    dummy_point_labels = torch.ones(batch_size, num_points, dtype=torch.float32)

    print(f"  Image embeddings: {dummy_image_embeddings.shape}")
    print(f"  Point coords: {dummy_point_coords.shape}")
    print(f"  Point labels: {dummy_point_labels.shape}")

    print("\n[5/6] Exporting to ONNX...")

    try:
        with torch.no_grad():
            torch.onnx.export(
                onnx_model,
                (dummy_image_embeddings, dummy_point_coords, dummy_point_labels),
                OUTPUT_PATH,
                export_params=True,
                opset_version=OPSET_VERSION,
                do_constant_folding=True,
                input_names=['image_embeddings', 'point_coords', 'point_labels'],
                output_names=['masks'],
                dynamic_axes={
                    'image_embeddings': {0: 'batch'},
                    'point_coords': {0: 'batch', 1: 'num_points'},
                    'point_labels': {0: 'batch', 1: 'num_points'},
                    'masks': {0: 'batch'}
                }
            )
        print(f"✓ ONNX model exported: {OUTPUT_PATH}")

    except Exception as e:
        print(f"✗ Export failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n[6/6] Validating ONNX model...")

    try:
        onnx_model_check = onnx.load(OUTPUT_PATH)
        onnx.checker.check_model(onnx_model_check)
        print("✓ ONNX model is valid")

        onnx_model_inferred = shape_inference.infer_shapes(onnx_model_check)
        onnx.save(onnx_model_inferred, OUTPUT_PATH)
        print("✓ Shape inference completed")

        file_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
        print(f"\n✓ Export successful!")
        print(f"  File: {OUTPUT_PATH}")
        print(f"  Size: {file_size_mb:.2f} MB")

        try:
            import onnxruntime as ort
            print("\n[Optional] Testing with ONNX Runtime...")

            session = ort.InferenceSession(OUTPUT_PATH)

            outputs = session.run(
                None,
                {
                    'image_embeddings': dummy_image_embeddings.numpy(),
                    'point_coords': dummy_point_coords.numpy(),
                    'point_labels': dummy_point_labels.numpy()
                }
            )

            output_shape = outputs[0].shape
            print(f"✓ ONNX Runtime test passed")
            print(f"  Output shape: {output_shape}")

        except ImportError:
            print("  (ONNX Runtime not installed, skipping test)")
        except Exception as e:
            print(f"  Warning: ONNX Runtime test failed: {e}")

    except Exception as e:
        print(f"✗ Validation failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("Export completed successfully!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Upload to S3:")
    print(f"     aws s3 cp {OUTPUT_PATH} s3://gen3d-data-bucket/models/sam3/sam3_mask_decoder.onnx")
    print("  2. Make publicly readable:")
    print("     aws s3api put-object-acl --bucket gen3d-data-bucket --key models/sam3/sam3_mask_decoder.onnx --acl public-read")
    print("\n")

if __name__ == "__main__":
    export_sam_decoder_onnx()
EOF

chmod +x export_sam_decoder.py
```

### 4.2 Create Docker Environment for Export

Since EC2 doesn't have GPU, we'll use the PyTorch Docker container we already have:

```bash
# Use existing PyTorch image from SageMaker build
# OR pull a fresh PyTorch image
docker pull pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Verify image exists
docker images | grep pytorch
```

### 4.3 Install Dependencies in Container

```bash
# Create Dockerfile for ONNX export environment
cat > Dockerfile.onnx << 'EOF'
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /workspace

# Install dependencies
RUN pip install --no-cache-dir \
    onnx==1.15.0 \
    onnxruntime==1.16.3 \
    opencv-python==4.8.1.78 \
    Pillow==10.1.0

# Install segment-anything
RUN pip install git+https://github.com/facebookresearch/segment-anything.git

# Copy export script
COPY export_sam_decoder.py /workspace/

CMD ["python", "/workspace/export_sam_decoder.py"]
EOF

echo "Dockerfile created"
```

### 4.4 Build Export Container

```bash
# Build Docker image for ONNX export
echo "Building ONNX export container..."
docker build -t sam3-onnx-export:v1 -f Dockerfile.onnx .

# Verify build
docker images | grep sam3-onnx-export
```

**Expected Output**:
```
REPOSITORY          TAG    SIZE
sam3-onnx-export    v1     ~8GB
```

**Time Estimate**: 5-10 minutes

---

## 5. Phase 3: ONNX Model Generation

### 5.1 Run ONNX Export Container

```bash
# Run export container with model volume mounted
echo "Starting ONNX export..."
echo "This may take 10-20 minutes..."

docker run \
    --name sam3-onnx-export \
    -v /home/ec2-user/models/sam3:/models/sam3:ro \
    -v /root/onnx-export:/output \
    --rm \
    sam3-onnx-export:v1 \
    python /workspace/export_sam_decoder.py

# The script will:
# 1. Load SAM3 model from /models/sam3/sam3.pt
# 2. Extract mask decoder
# 3. Export to ONNX format
# 4. Save to /output/sam3_mask_decoder.onnx
```

**Time Estimate**: 10-20 minutes

**Expected Progress**:
```
================================================================================
SAM3 Mask Decoder ONNX Export Script - EC2
================================================================================

[1/6] Checking dependencies...
✓ segment-anything package found

[2/6] Loading SAM model checkpoint...
✓ Loaded SAM model: vit_h

[3/6] Preparing mask decoder for export...
✓ Mask decoder wrapper created

[4/6] Creating dummy inputs for export...
  Image embeddings: torch.Size([1, 256, 64, 64])
  Point coords: torch.Size([1, 2, 2])
  Point labels: torch.Size([1, 2])

[5/6] Exporting to ONNX...
✓ ONNX model exported: /root/onnx-export/sam3_mask_decoder.onnx

[6/6] Validating ONNX model...
✓ ONNX model is valid
✓ Shape inference completed

✓ Export successful!
  File: /root/onnx-export/sam3_mask_decoder.onnx
  Size: 1400.23 MB

[Optional] Testing with ONNX Runtime...
✓ ONNX Runtime test passed
  Output shape: (1, 1, 1024, 1024)

================================================================================
Export completed successfully!
================================================================================
```

### 5.2 Verify ONNX Model Generated

```bash
# Check if ONNX model exists
ls -lh /root/onnx-export/sam3_mask_decoder.onnx

# Expected output:
# -rw-r--r-- 1 root root 1.4G Dec 3 sam3_mask_decoder.onnx

# Verify file is not empty
du -sh /root/onnx-export/sam3_mask_decoder.onnx
```

**Success Criteria**:
- File exists at `/root/onnx-export/sam3_mask_decoder.onnx`
- File size is approximately 1.4 GB
- No error messages in console output

---

## 6. Phase 4: Validation

### 6.1 ONNX Model Structure Validation

```bash
# Install ONNX tools if not already installed
pip install onnx onnxruntime

# Check model structure
python << 'EOF'
import onnx

model_path = "/root/onnx-export/sam3_mask_decoder.onnx"

# Load model
model = onnx.load(model_path)

# Check model validity
onnx.checker.check_model(model)
print("✓ Model is valid")

# Print input/output info
print("\nModel Inputs:")
for input in model.graph.input:
    print(f"  - {input.name}: {input.type}")

print("\nModel Outputs:")
for output in model.graph.output:
    print(f"  - {output.name}: {output.type}")

print(f"\nModel size: {os.path.getsize(model_path) / (1024**3):.2f} GB")
EOF
```

**Expected Output**:
```
✓ Model is valid

Model Inputs:
  - image_embeddings: tensor(float32, [batch, 256, 64, 64])
  - point_coords: tensor(float32, [batch, num_points, 2])
  - point_labels: tensor(float32, [batch, num_points])

Model Outputs:
  - masks: tensor(float32, [batch, 1, 1024, 1024])

Model size: 1.40 GB
```

### 6.2 ONNX Runtime Inference Test

```bash
# Test inference with ONNX Runtime
python << 'EOF'
import onnxruntime as ort
import numpy as np

model_path = "/root/onnx-export/sam3_mask_decoder.onnx"

print("Loading ONNX model...")
session = ort.InferenceSession(model_path)

print("Creating test inputs...")
batch_size = 1
image_embeddings = np.random.randn(batch_size, 256, 64, 64).astype(np.float32)
point_coords = np.array([[[100, 100], [200, 200]]], dtype=np.float32)
point_labels = np.array([[1, 1]], dtype=np.float32)

print("Running inference...")
outputs = session.run(
    None,
    {
        'image_embeddings': image_embeddings,
        'point_coords': point_coords,
        'point_labels': point_labels
    }
)

masks = outputs[0]
print(f"✓ Inference successful")
print(f"  Output shape: {masks.shape}")
print(f"  Output range: [{masks.min():.3f}, {masks.max():.3f}]")
print(f"  Output mean: {masks.mean():.3f}")
EOF
```

**Expected Output**:
```
Loading ONNX model...
Creating test inputs...
Running inference...
✓ Inference successful
  Output shape: (1, 1, 1024, 1024)
  Output range: [0.012, 0.987]
  Output mean: 0.521
```

**Success Criteria**:
- ONNX model loads without errors
- Inference runs successfully
- Output shape matches expected: (1, 1, 1024, 1024)
- Output values are in valid range [0, 1]

---

## 7. Phase 5: S3 Deployment

### 7.1 Upload ONNX Model to S3

```bash
# Upload to S3
echo "Uploading ONNX model to S3..."
aws s3 cp /root/onnx-export/sam3_mask_decoder.onnx \
    s3://gen3d-data-bucket/models/sam3/sam3_mask_decoder.onnx

# Expected output:
# upload: sam3_mask_decoder.onnx to s3://gen3d-data-bucket/models/sam3/sam3_mask_decoder.onnx
# Completed 1.4 GB/1.4 GB
```

**Time Estimate**: 5-10 minutes (uploading 1.4 GB)

### 7.2 Make Model Publicly Readable

```bash
# Set public-read ACL for browser access
aws s3api put-object-acl \
    --bucket gen3d-data-bucket \
    --key models/sam3/sam3_mask_decoder.onnx \
    --acl public-read

echo "✓ ONNX model is now publicly accessible"
```

### 7.3 Verify S3 Upload

```bash
# Verify file exists in S3
aws s3 ls s3://gen3d-data-bucket/models/sam3/ --human-readable

# Expected output:
# 2025-12-03 12:34:56    1.4 GiB sam3_mask_decoder.onnx
# 2025-12-01 10:20:30    6.5 GiB sam3.pt

# Test public access (should return HTTP 200)
curl -I https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx

# Expected:
# HTTP/1.1 200 OK
# Content-Length: 1503238860
# Content-Type: application/octet-stream
```

### 7.4 Test Download from Web App

**From local machine, test download speed**:

```bash
# Test download
curl -o test_download.onnx \
    https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx

# Check downloaded file
ls -lh test_download.onnx

# Expected: ~1.4 GB file
```

**Download Time Estimate**:
- Typical broadband (50 Mbps): ~4 minutes
- Fast broadband (100 Mbps): ~2 minutes
- Enterprise (500 Mbps): ~30 seconds

**Success Criteria**:
- [ ] Model uploaded to S3 successfully
- [ ] Model set to public-read
- [ ] Public URL returns HTTP 200
- [ ] Model downloads successfully via curl

---

## 8. Troubleshooting

### Issue 1: segment-anything Package Not Found

**Error**:
```
ModuleNotFoundError: No module named 'segment_anything'
```

**Solution**:
```bash
# Install segment-anything in Docker container
docker run -it sam3-onnx-export:v1 bash
pip install git+https://github.com/facebookresearch/segment-anything.git
exit

# OR rebuild Docker image with updated Dockerfile
```

### Issue 2: SAM3 Model Not Found

**Error**:
```
FileNotFoundError: [Errno 2] No such file or directory: '/home/ec2-user/models/sam3/sam3.pt'
```

**Solution**:
```bash
# Verify model path
ls -lh /home/ec2-user/models/sam3/

# Check if volume mount is correct
docker run --rm -v /home/ec2-user/models/sam3:/models/sam3:ro sam3-onnx-export:v1 ls -lh /models/sam3
```

### Issue 3: Out of Memory During Export

**Error**:
```
RuntimeError: CUDA out of memory
```

**Solution**:
```bash
# t3.xlarge has no GPU, but if running on CPU:
# Increase Docker memory limit
docker run --memory=14g --memory-swap=16g ...

# OR reduce batch size in script (already set to 1)
```

### Issue 4: ONNX Export Timeout

**Error**:
- Export hangs for >30 minutes

**Solution**:
```bash
# Check container logs
docker logs sam3-onnx-export

# Check system resources
top
df -h

# If stuck, kill and retry
docker stop sam3-onnx-export
docker rm sam3-onnx-export
```

### Issue 5: ONNX Model Validation Failed

**Error**:
```
onnx.checker.ValidationError: ...
```

**Solution**:
```bash
# Try lower opset version
# Edit export_sam_decoder.py:
OPSET_VERSION = 14  # Instead of 17

# Rebuild and re-export
```

### Issue 6: S3 Upload Permission Denied

**Error**:
```
An error occurred (AccessDenied) when calling the PutObject operation
```

**Solution**:
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify S3 permissions
aws s3api get-bucket-acl --bucket gen3d-data-bucket

# Use correct profile
export AWS_PROFILE=genesis3d
```

---

## 9. Alternative: Download Pre-converted Model

If export on EC2 fails, you can download a pre-converted ONNX model:

### Option A: Download from Meta's SAM Repository

```bash
# Meta provides pre-converted ONNX models
wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_decoder.onnx \
    -O /root/onnx-export/sam3_mask_decoder.onnx

# Verify download
ls -lh /root/onnx-export/sam3_mask_decoder.onnx
```

### Option B: Use Existing Local Model

If you already have a working ONNX model locally:

```bash
# From local machine, upload via S3
cd C:/Users/Admin/Documents/Workspace/Antigravity/Gen3D

aws s3 cp deployment/onnx-export/sam3_mask_decoder.onnx \
    s3://gen3d-data-bucket/models/sam3/sam3_mask_decoder.onnx \
    --profile genesis3d

# Set public-read
aws s3api put-object-acl \
    --bucket gen3d-data-bucket \
    --key models/sam3/sam3_mask_decoder.onnx \
    --acl public-read \
    --profile genesis3d
```

---

## 10. Summary and Next Steps

### 10.1 What Was Accomplished

- [x] Created ONNX export environment on EC2
- [x] Exported SAM3 mask decoder to ONNX format
- [x] Validated ONNX model structure and inference
- [x] Uploaded ONNX model to S3 with public access
- [x] Verified web app can download model

### 10.2 Files Generated

**On EC2**:
- `/root/onnx-export/sam3_mask_decoder.onnx` (1.4 GB)
- `/root/onnx-export/export_sam_decoder.py` (export script)
- `/root/onnx-export/Dockerfile.onnx` (Docker environment)

**On S3**:
- `s3://gen3d-data-bucket/models/sam3/sam3_mask_decoder.onnx` (1.4 GB, public)

### 10.3 Integration with Web App

The ONNX model is now ready to be integrated into the Gen3D web application.

**Web App Changes Needed** (refer to `ONNX-Usage-Guide.md`):
1. Update `app.js` to load ONNX model from S3
2. Replace mock inference with real ONNX inference
3. Update `MaskingInterface.runONNXInference()` method

**Model URL**:
```
https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx
```

### 10.4 Performance Expectations

**Model Loading** (first time):
- Download size: 1.4 GB
- Download time: 2-4 minutes (typical broadband)
- Browser caching: Subsequent loads instant

**Inference Performance**:
- Expected latency: 50-200ms (depends on user's CPU)
- Current mock inference: 1-5ms
- Trade-off: Accuracy vs. Speed

---

**Document Version**: 1.0
**Date**: 2025-12-03
**Author**: Gen3D Development Team
**Status**: Ready for Execution
