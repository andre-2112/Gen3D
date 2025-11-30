# Gen3D Implementation Plan - Critical Revisions Needed

## Analysis Date: 2025-11-27

## Executive Summary

After thorough review, the Implementation Plan is missing several critical steps needed to successfully perform inference with SAM 3D and obtain 3D mesh outputs. The plan jumps directly to AWS deployment without local validation, which is a major risk.

---

## CRITICAL MISSING STEPS

### 1. Local Model Testing (BEFORE AWS Deployment)

**Issue**: Phase 3 downloads the model and immediately builds a Docker container for AWS, with NO local testing.

**Required New Phase**: **Phase 3A - Local Model Validation**

#### Step 3A.1: Verify SAM 3D Model Installation

```bash
# Test model loading locally
cd /tmp/gen3d-build/sam-3d-objects

python << 'PYTHON_EOF'
import sys
sys.path.append('.')
from inference import Inference

# Try to load the model
config_path = "checkpoints/hf/pipeline.yaml"
print("Loading SAM 3D model...")
model = Inference(config_path, compile=False)
print("✓ Model loaded successfully!")
print(f"Model type: {type(model)}")
PYTHON_EOF
```

#### Step 3A.2: Test Inference with Sample Image

```bash
# Download a test image
mkdir -p test_data
cd test_data
curl -o test_chair.jpg "https://images.pexels.com/photos/116910/pexels-photo-116910.jpeg?auto=compress&cs=tinysrgb&w=400"

# Create a simple mask (entire image)
python << 'PYTHON_EOF'
from PIL import Image
import numpy as np

# Load image
img = Image.open("test_chair.jpg")
width, height = img.size

# Create binary mask (1 = object, 0 = background)
# For testing, mask the center region
mask = np.zeros((height, width), dtype=np.uint8)
mask[height//4:3*height//4, width//4:3*width//4] = 1

# Save mask
mask_img = Image.fromarray(mask * 255)
mask_img.save("test_mask.png")
print(f"✓ Created test mask: {width}x{height}")
PYTHON_EOF
```

#### Step 3A.3: Run Local Inference

```bash
cd /tmp/gen3d-build/sam-3d-objects

python << 'PYTHON_EOF'
import sys
sys.path.append('.')
from inference import Inference
from PIL import Image
import torch

print("Loading model...")
model = Inference("checkpoints/hf/pipeline.yaml", compile=False)
print("✓ Model loaded")

# Load test image and mask
print("Loading test data...")
image = Image.open("test_data/test_chair.jpg").convert('RGB')
mask = Image.open("test_data/test_mask.png").convert('L')

print(f"Image size: {image.size}")
print(f"Mask size: {mask.size}")

# Run inference
print("Running inference...")
try:
    output = model(image, mask, seed=42)
    print(f"✓ Inference successful!")
    print(f"Output keys: {output.keys()}")

    # Check for Gaussian splat output
    if 'gs' in output:
        print("✓ Gaussian splat generated")
        # Save output
        output['gs'].save_ply("test_data/output_test.ply")
        print("✓ Saved to test_data/output_test.ply")
    else:
        print("✗ No 'gs' key in output!")
        print(f"Available keys: {list(output.keys())}")

except Exception as e:
    print(f"✗ Inference failed: {e}")
    import traceback
    traceback.print_exc()
PYTHON_EOF
```

#### Step 3A.4: Validate Output File

```bash
# Check if PLY file was created
if [ -f "test_data/output_test.ply" ]; then
    echo "✓ PLY file created"
    ls -lh test_data/output_test.ply

    # Check file size (should be > 1KB)
    SIZE=$(stat -f%z "test_data/output_test.ply" 2>/dev/null || stat -c%s "test_data/output_test.ply")
    if [ $SIZE -gt 1000 ]; then
        echo "✓ File size: $SIZE bytes (looks valid)"
    else
        echo "✗ File too small: $SIZE bytes (might be empty)"
    fi

    # Show first few lines
    echo "First 20 lines of PLY file:"
    head -20 test_data/output_test.ply
else
    echo "✗ PLY file not created - inference failed"
    exit 1
fi
```

---

### 2. Fix Inference Code Structure

**Issue**: The `inference.py` file in Phase 3.6 has a name collision - it imports `from inference import Inference` but the file itself is named `inference.py`.

**Solution**: Rename to `sagemaker_handler.py`

#### Corrected File Structure:

```
/opt/ml/code/
├── sam-3d-objects/          # SAM 3D repository code
│   ├── inference.py         # SAM 3D's inference module
│   ├── requirements.txt
│   └── ...
├── sagemaker_handler.py     # Our SageMaker handler (RENAMED)
└── serve.py                 # Flask server
```

#### Updated serve.py:

```python
import flask
import json
import os
from sagemaker_handler import model_fn, input_fn, predict_fn, output_fn  # FIXED IMPORT

app = flask.Flask(__name__)
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
        input_data = input_fn(flask.request.data, flask.request.content_type)
        prediction = predict_fn(input_data, model)
        result = output_fn(prediction, flask.request.accept_mimetypes)
        return flask.Response(response=result, status=200, mimetype='application/json')
    except Exception as e:
        return flask.Response(
            response=json.dumps({'error': str(e)}),
            status=500,
            mimetype='application/json'
        )

if __name__ == '__main__':
    model = model_fn('/opt/ml/model')
    app.run(host='0.0.0.0', port=8080)
```

---

### 3. Fix Dockerfile

**Issue**: The Dockerfile copies files incorrectly and doesn't set up proper paths.

**Corrected Dockerfile**:

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/ml/code

# Copy SAM 3D repository
COPY . /opt/ml/code/sam-3d-objects/

# Copy model checkpoints
COPY checkpoints/ /opt/ml/model/checkpoints/

# Install Python dependencies
WORKDIR /opt/ml/code/sam-3d-objects
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements.inference.txt

# Install additional dependencies for SageMaker
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    boto3==1.34.0 \
    pillow==10.1.0

# Copy our custom handler scripts
WORKDIR /opt/ml/code
COPY sagemaker_handler.py /opt/ml/code/
COPY serve.py /opt/ml/code/

# Set Python path
ENV PYTHONPATH="/opt/ml/code:/opt/ml/code/sam-3d-objects:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE

# Expose port for inference
EXPOSE 8080

# Entry point
ENTRYPOINT ["python", "serve.py"]
```

---

### 4. Test Docker Container Locally

**Missing Step**: Test the Docker container locally BEFORE pushing to ECR.

#### Step 3.6A: Build and Test Container Locally

```bash
cd /tmp/gen3d-build/sam-3d-objects

# Build container
docker build -t gen3d-sam3d-inference:test .

# Run container locally
docker run -d -p 8080:8080 \
    --name gen3d-test \
    --gpus all \
    gen3d-sam3d-inference:test

# Wait for container to start
sleep 30

# Test health endpoint
curl http://localhost:8080/ping

# Check logs
docker logs gen3d-test

# If successful, stop container
docker stop gen3d-test
docker rm gen3d-test
```

---

### 5. Fix Web Interface Mask Format

**Issue**: The web interface creates a binary mask (black rectangle on white background), but SAM 3D expects specific mask format.

**Verification Needed**: Test what mask format SAM 3D expects

#### Test Mask Format:

```bash
python << 'PYTHON_EOF'
from PIL import Image
import numpy as np

# Test different mask formats
img = Image.open("test_data/test_chair.jpg")
width, height = img.size

# Format 1: Binary (0/255)
mask1 = np.zeros((height, width), dtype=np.uint8)
mask1[100:300, 100:300] = 255
Image.fromarray(mask1).save("mask_format_1.png")

# Format 2: Binary (0/1)
mask2 = np.zeros((height, width), dtype=np.uint8)
mask2[100:300, 100:300] = 1
Image.fromarray(mask2).save("mask_format_2.png")

# Format 3: Boolean
mask3 = np.zeros((height, width), dtype=bool)
mask3[100:300, 100:300] = True
Image.fromarray(mask3).save("mask_format_3.png")

print("Testing different mask formats...")
# Test each with SAM 3D model
PYTHON_EOF
```

**Update Web Interface**: Based on testing, ensure JavaScript creates correct mask format.

---

### 6. Missing: Image and Mask Upload Logic

**Issue**: The web interface only uploads the mask, not the original image AND mask separately.

**Current Behavior**:
```javascript
// Only uploads mask canvas
const blob = await new Promise(resolve => {
    maskCanvas.toBlob(resolve, 'image/png');
});
```

**Required Behavior**:
```javascript
// Should upload BOTH image and mask
async function uploadMaskedImage(userId, bbox, index) {
    const timestamp = new Date().getTime();

    // 1. Upload original image
    const imageBlob = await new Promise(resolve => {
        canvas.toBlob(resolve, 'image/png');
    });
    const imageKey = `users/${userId}/input/${timestamp}_object_${index}_image.png`;
    await s3.upload({Key: imageKey, Body: imageBlob, ContentType: 'image/png'}).promise();

    // 2. Upload mask
    const maskCanvas = createMaskCanvas(bbox);
    const maskBlob = await new Promise(resolve => {
        maskCanvas.toBlob(resolve, 'image/png');
    });
    const maskKey = `users/${userId}/input/${timestamp}_object_${index}_mask.png`;
    await s3.upload({Key: maskKey, Body: maskBlob, ContentType: 'image/png'}).promise();

    // 3. Upload metadata JSON
    const metadata = {
        image_key: imageKey,
        mask_key: maskKey,
        bbox: bbox,
        timestamp: timestamp
    };
    const metaKey = `users/${userId}/input/${timestamp}_object_${index}_meta.json`;
    await s3.upload({
        Key: metaKey,
        Body: JSON.stringify(metadata),
        ContentType: 'application/json'
    }).promise();
}
```

---

### 7. Missing: Lambda Function Input Validation

**Issue**: Extract Lambda doesn't validate that both image and mask exist before invoking SageMaker.

**Required Addition** to `extract_lambda.py`:

```python
def lambda_handler(event, context):
    # ... existing code ...

    # Check if mask file also exists
    mask_key = key.replace('_image.png', '_mask.png')
    try:
        s3_client.head_object(Bucket=bucket, Key=mask_key)
        print(f"✓ Found mask: {mask_key}")
    except:
        print(f"✗ Mask not found: {mask_key}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Mask file not found'})
        }

    # ... continue with SageMaker invocation ...
```

---

### 8. Missing: SageMaker Input/Output Format Documentation

**Issue**: The input_fn and output_fn use custom format, but it's not documented what SageMaker Async expects.

**Required**: Document the exact JSON format expected by SageMaker Async Inference:

```json
{
  "image_bucket": "gen3d-data-bucket",
  "image_key": "users/user123/input/123456_image.png",
  "mask_key": "users/user123/input/123456_mask.png",
  "output_bucket": "gen3d-data-bucket",
  "output_key": "users/user123/output/123456_output.ply",
  "seed": 42
}
```

---

### 9. Missing: Error Handling for Model Failures

**Issue**: No error handling for cases where SAM 3D model fails to generate output.

**Required Addition** to `sagemaker_handler.py`:

```python
def predict_fn(input_data, model):
    """Run prediction"""
    try:
        image, mask = model.preprocess(input_data['image'], input_data['mask'])
        seed = input_data['metadata'].get('seed', 42)

        # Run inference
        output = model.inference(image, mask, seed)

        # Validate output
        if 'gs' not in output:
            raise ValueError("Model did not generate 'gs' (Gaussian splat) output")

        if output['gs'] is None:
            raise ValueError("Model generated None for Gaussian splat")

        return {'output': output, 'metadata': input_data['metadata']}

    except Exception as e:
        print(f"Inference error: {str(e)}")
        # Write error file to S3
        error_key = input_data['metadata']['output_key'].replace('.ply', '.error')
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=input_data['metadata']['output_bucket'],
            Key=error_key,
            Body=str(e)
        )
        raise
```

---

### 10. Missing: Demo Script for Quick Testing

**Issue**: No simple script to test the entire workflow end-to-end.

**Required New File**: `test_local_inference.py`

```python
#!/usr/bin/env python3
"""
Test SAM 3D inference locally before deploying to AWS
"""
import sys
sys.path.append('sam-3d-objects')

from inference import Inference
from PIL import Image
import numpy as np
import argparse

def create_center_mask(width, height):
    """Create a mask covering the center of the image"""
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[height//4:3*height//4, width//4:3*width//4] = 255
    return Image.fromarray(mask)

def main(image_path, output_path):
    print("🚀 Starting SAM 3D local test...")

    # Load model
    print("📦 Loading model...")
    model = Inference("checkpoints/hf/pipeline.yaml", compile=False)
    print("✓ Model loaded")

    # Load image
    print(f"🖼️  Loading image: {image_path}")
    image = Image.open(image_path).convert('RGB')
    print(f"✓ Image size: {image.size}")

    # Create mask
    print("🎭 Creating mask...")
    mask = create_center_mask(*image.size)
    print("✓ Mask created")

    # Run inference
    print("🔮 Running inference...")
    output = model(image, mask, seed=42)
    print("✓ Inference complete")

    # Save output
    if 'gs' in output:
        print(f"💾 Saving to: {output_path}")
        output['gs'].save_ply(output_path)
        print("✓ Saved successfully")

        import os
        size = os.path.getsize(output_path)
        print(f"📊 Output file size: {size:,} bytes")

        if size < 1000:
            print("⚠️  Warning: File is very small, check if output is valid")
        else:
            print("✅ Test successful!")

    else:
        print("❌ Error: No 'gs' in output")
        print(f"Available keys: {list(output.keys())}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--output", default="output_test.ply", help="Output PLY file")
    args = parser.parse_args()

    main(args.image, args.output)
```

---

## SUMMARY OF REQUIRED ADDITIONS

### New Phase to Add: Phase 3A - Local Model Validation

Insert between current Phase 3 (Download Model) and Phase 3.6 (Create Container):

1. **Step 3A.1**: Verify model loads correctly
2. **Step 3A.2**: Prepare test data (image + mask)
3. **Step 3A.3**: Run local inference
4. **Step 3A.4**: Validate output file
5. **Step 3A.5**: Test different mask formats
6. **Step 3A.6**: Create test script for repeated testing

### Files to Fix:

1. **Rename**: `inference.py` → `sagemaker_handler.py`
2. **Update**: `serve.py` (fix import)
3. **Fix**: Dockerfile (proper paths and PYTHONPATH)
4. **Enhance**: `extract_lambda.py` (add mask validation)
5. **Enhance**: `sagemaker_handler.py` (add error handling)
6. **Fix**: Web interface JavaScript (upload image + mask separately)

### New Files to Add:

1. `test_local_inference.py` - Local testing script
2. `test_mask_formats.py` - Verify correct mask format
3. `validate_output.py` - Check PLY file validity

---

## RISK ASSESSMENT

**Current Plan Risk**: 🔴 **HIGH**
- Deploying to AWS without local validation
- High probability of runtime errors
- Expensive debugging in cloud environment

**With Revisions Risk**: 🟢 **LOW**
- All components tested locally first
- Known working configuration before deployment
- Cost-effective iterative development

---

## RECOMMENDED IMPLEMENTATION ORDER

1. ✅ Complete Phase 1-2 (IAM, S3) as written
2. ✅ Complete Phase 3.1-3.4 (Download model) as written
3. ⭐ **NEW Phase 3A** (Local validation) - CRITICAL
4. ✅ Phase 3.5 (Secrets Manager) as written
5. 🔧 Phase 3.6 (Container) - WITH FIXES
6. 🔧 Phase 3.7-3.10 (Deploy) - AFTER local testing succeeds
7. ✅ Continue with Phases 4-9

---

## CONCLUSION

The current plan will likely fail at runtime because:
1. No validation that SAM 3D model works
2. Code structure issues (naming collision)
3. Missing proper mask handling
4. No local testing before expensive cloud deployment

**Recommendation**: Implement all revisions before proceeding to AWS deployment.

**Time Investment**:
- Revisions: +4-6 hours
- Savings: 20-40 hours of cloud debugging
- ROI: 400-600% time savings

---

*Generated: 2025-11-27*
*Status: CRITICAL - Implement before AWS deployment*
