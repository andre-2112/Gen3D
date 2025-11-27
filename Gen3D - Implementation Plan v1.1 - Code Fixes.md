# Gen3D - Implementation Plan v1.1 - Code Fixes Reference

## Critical Code Updates for v1.1

This document contains code fixes to be applied to the Implementation Plan v1.1.
These fixes are referenced in the main plan but detailed here for clarity.

---

## Fix 1: Rename inference.py to sagemaker_handler.py

**Issue**: Name collision with SAM 3D's own `inference.py` module

**Location**: Step 3.6

**Old**: `inference.py`
**New**: `sagemaker_handler.py`

**Complete File** (`sagemaker_handler.py`):

```python
import os
import json
import boto3
import torch
from PIL import Image
import numpy as np
from io import BytesIO

# Import SAM 3D components from the sam-3d-objects module
import sys
sys.path.append('/opt/ml/code/sam-3d-objects')
from inference import Inference  # SAM 3D's inference module

class SAM3DHandler:
    def __init__(self):
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def initialize(self):
        """Load model on initialization"""
        config_path = "/opt/ml/model/checkpoints/hf/pipeline.yaml"
        print(f"Loading SAM 3D model from: {config_path}")
        self.model = Inference(config_path, compile=False)
        print(f"Model loaded successfully on {self.device}")

    def preprocess(self, image_bytes, mask_bytes=None):
        """Preprocess input image and mask"""
        # Load image
        image = Image.open(BytesIO(image_bytes)).convert('RGB')

        if mask_bytes:
            mask = Image.open(BytesIO(mask_bytes)).convert('L')
        else:
            # Extract mask from alpha channel if RGBA
            img_rgba = Image.open(BytesIO(image_bytes))
            if img_rgba.mode == 'RGBA':
                mask = img_rgba.split()[-1]
            else:
                raise ValueError("No mask provided and image has no alpha channel")

        return image, mask

    def inference(self, image, mask, seed=42):
        """Run inference"""
        print(f"Running inference with seed={seed}, image size={image.size}, mask size={mask.size}")
        output = self.model(image, mask, seed=seed)
        print(f"Inference complete. Output keys: {list(output.keys())}")
        return output

    def postprocess(self, output, output_path):
        """Save output to file"""
        if 'gs' not in output:
            raise ValueError(f"No 'gs' key in model output. Available: {list(output.keys())}")

        if output['gs'] is None:
            raise ValueError("Model returned None for Gaussian splat")

        # Save PLY file
        output["gs"].save_ply(output_path)

        # Verify file was created
        if not os.path.exists(output_path):
            raise ValueError(f"Failed to create output file: {output_path}")

        file_size = os.path.getsize(output_path)
        print(f"Output saved: {output_path} ({file_size:,} bytes)")

        return output_path

# SageMaker handler functions
handler = SAM3DHandler()

def model_fn(model_dir):
    """Load model (called once on container startup)"""
    print("="*60)
    print("Initializing SAM 3D model...")
    print("="*60)
    handler.initialize()
    print("Model initialization complete")
    return handler

def input_fn(request_body, content_type):
    """Parse input (called for each request)"""
    print(f"Processing input with content_type: {content_type}")

    if content_type == 'application/json':
        input_data = json.loads(request_body)
        s3 = boto3.client('s3')

        # Download image from S3
        image_bucket = input_data['image_bucket']
        image_key = input_data['image_key']

        print(f"Downloading image: s3://{image_bucket}/{image_key}")
        image_obj = s3.get_object(Bucket=image_bucket, Key=image_key)
        image_bytes = image_obj['Body'].read()

        # Download mask if specified
        mask_bytes = None
        mask_key = input_data.get('mask_key')
        if mask_key:
            print(f"Downloading mask: s3://{image_bucket}/{mask_key}")
            mask_obj = s3.get_object(Bucket=image_bucket, Key=mask_key)
            mask_bytes = mask_obj['Body'].read()

        return {
            'image': image_bytes,
            'mask': mask_bytes,
            'metadata': input_data
        }
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

def predict_fn(input_data, model):
    """Run prediction (called for each request)"""
    try:
        # Preprocess
        image, mask = model.preprocess(input_data['image'], input_data['mask'])

        # Run inference
        seed = input_data['metadata'].get('seed', 42)
        output = model.inference(image, mask, seed)

        return {
            'output': output,
            'metadata': input_data['metadata']
        }
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        # Write error to S3
        try:
            output_key = input_data['metadata']['output_key']
            error_key = output_key.replace('.ply', '.error')
            s3 = boto3.client('s3')
            s3.put_object(
                Bucket=input_data['metadata']['output_bucket'],
                Key=error_key,
                Body=json.dumps({
                    'error': str(e),
                    'metadata': input_data['metadata']
                })
            )
            print(f"Error details written to: s3://{input_data['metadata']['output_bucket']}/{error_key}")
        except:
            pass
        raise

def output_fn(prediction, accept):
    """Save output (called for each request)"""
    try:
        s3 = boto3.client('s3')

        output_bucket = prediction['metadata']['output_bucket']
        output_key = prediction['metadata']['output_key']

        # Save to temporary file
        temp_path = '/tmp/output.ply'
        prediction['output']["gs"].save_ply(temp_path)

        # Verify file
        file_size = os.path.getsize(temp_path)
        print(f"Temporary file created: {file_size:,} bytes")

        if file_size < 1000:
            raise ValueError(f"Output file too small: {file_size} bytes")

        # Upload to S3
        print(f"Uploading to: s3://{output_bucket}/{output_key}")
        s3.upload_file(temp_path, output_bucket, output_key)

        # Verify upload
        s3.head_object(Bucket=output_bucket, Key=output_key)
        print("Upload verified successfully")

        # Clean up
        os.remove(temp_path)

        return json.dumps({
            'status': 'success',
            'output_location': f's3://{output_bucket}/{output_key}',
            'file_size': file_size
        })
    except Exception as e:
        print(f"Output error: {str(e)}")
        # Write error file
        try:
            error_key = prediction['metadata']['output_key'].replace('.ply', '.error')
            s3.put_object(
                Bucket=prediction['metadata']['output_bucket'],
                Key=error_key,
                Body=json.dumps({'error': str(e)})
            )
        except:
            pass
        raise
```

---

## Fix 2: Updated serve.py

**Location**: Step 3.6

**Updated File** (`serve.py`):

```python
import flask
import json
import os

# Import from our handler module (NOT from inference.py)
from sagemaker_handler import model_fn, input_fn, predict_fn, output_fn

app = flask.Flask(__name__)

# Global model instance
model = None

@app.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint"""
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
        error_msg = json.dumps({
            'error': str(e),
            'type': type(e).__name__
        })
        print(f"Request failed: {error_msg}")
        return flask.Response(
            response=error_msg,
            status=500,
            mimetype='application/json'
        )

if __name__ == '__main__':
    print("="*60)
    print("Starting SAM 3D SageMaker Inference Server")
    print("="*60)

    # Load model on startup
    model = model_fn('/opt/ml/model')

    print("\nServer ready. Listening on 0.0.0.0:8080")
    print("="*60)

    # Start Flask server
    app.run(host='0.0.0.0', port=8080)
```

---

## Fix 3: Corrected Dockerfile

**Location**: Step 3.6

**Updated Dockerfile**:

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create directory structure
WORKDIR /opt/ml/code

# Copy SAM 3D repository (this has the inference.py module)
COPY . /opt/ml/code/sam-3d-objects/

# Copy model checkpoints
COPY checkpoints/ /opt/ml/model/checkpoints/

# Install SAM 3D dependencies
WORKDIR /opt/ml/code/sam-3d-objects
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements.inference.txt

# Install SageMaker dependencies
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    boto3==1.34.0 \
    pillow==10.1.0

# Copy our custom handler files
WORKDIR /opt/ml/code
COPY sagemaker_handler.py /opt/ml/code/
COPY serve.py /opt/ml/code/

# Set Python path so we can import from both locations
ENV PYTHONPATH="/opt/ml/code:/opt/ml/code/sam-3d-objects:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE

# Expose inference port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8080/ping || exit 1

# Entry point
ENTRYPOINT ["python", "serve.py"]
```

---

## Fix 4: Enhanced Lambda Extract Function

**Location**: Step 4.1

**Add this validation section** to `extract_lambda.py`:

```python
def lambda_handler(event, context):
    """
    Triggered by S3 upload to users/{user_id}/input/*
    Validates input and invokes SageMaker async endpoint
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse S3 event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        print(f"Processing file: s3://{bucket}/{key}")

        # Only process image files (not masks or metadata)
        if not key.endswith('_image.png') and not key.endswith('.jpg'):
            print(f"Skipping non-image file: {key}")
            return {'statusCode': 200, 'body': 'Skipped'}

        # Extract user_id from path
        parts = key.split('/')
        if len(parts) < 4 or parts[0] != 'users':
            raise ValueError(f"Invalid key format: {key}")

        user_id = parts[1]
        filename = parts[3]

        # Check if corresponding mask exists
        mask_key = key.replace('_image.png', '_mask.png').replace('.jpg', '_mask.png')
        try:
            s3_client.head_object(Bucket=bucket, Key=mask_key)
            print(f"✓ Found mask: {mask_key}")
        except:
            print(f"✗ Mask not found: {mask_key}")
            send_error_notification(user_id, f"Mask file missing: {mask_key}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Mask file not found'})
            }

        # Generate output path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{timestamp}_{os.path.splitext(filename)[0]}.ply"
        output_key = f"users/{user_id}/output/{output_filename}"

        # Prepare inference input
        input_data = {
            'image_bucket': bucket,
            'image_key': key,
            'mask_key': mask_key,
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
                'mask_file': mask_key,
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
```

---

## Fix 5: Web Interface Upload Logic

**Location**: Step 7.1

**Replace the `uploadMaskedImage` function** with:

```javascript
async function uploadMaskedImage(userId, bbox, index) {
    const timestamp = new Date().getTime();

    try:
        // 1. Create and upload the original image with cropped view
        const imageBlob = await new Promise(resolve => {
            // Use the original canvas (not mask canvas)
            canvas.toBlob(resolve, 'image/png');
        });

        const imageKey = `users/${userId}/input/${timestamp}_object_${index}_image.png`;
        await s3.upload({
            Key: imageKey,
            Body: imageBlob,
            ContentType: 'image/png'
        }).promise();

        console.log(`✓ Uploaded image: ${imageKey}`);

        // 2. Create and upload the mask
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

        const maskBlob = await new Promise(resolve => {
            maskCanvas.toBlob(resolve, 'image/png');
        });

        const maskKey = `users/${userId}/input/${timestamp}_object_${index}_mask.png`;
        await s3.upload({
            Key: maskKey,
            Body: maskBlob,
            ContentType: 'image/png'
        }).promise();

        console.log(`✓ Uploaded mask: ${maskKey}`);

        // 3. Upload metadata JSON
        const metadata = {
            image_key: imageKey,
            mask_key: maskKey,
            bbox: {
                x1: Math.min(bbox.startX, bbox.endX),
                y1: Math.min(bbox.startY, bbox.endY),
                x2: Math.max(bbox.startX, bbox.endX),
                y2: Math.max(bbox.startY, bbox.endY)
            },
            timestamp: timestamp,
            canvas_size: {
                width: canvas.width,
                height: canvas.height
            }
        };

        const metaKey = `users/${userId}/input/${timestamp}_object_${index}_meta.json`;
        await s3.upload({
            Key: metaKey,
            Body: JSON.stringify(metadata, null, 2),
            ContentType: 'application/json'
        }).promise();

        console.log(`✓ Uploaded metadata: ${metaKey}`);

        return {
            success: true,
            imageKey,
            maskKey,
            metaKey
        };

    } catch (error) {
        console.error(`✗ Upload failed:`, error);
        throw error;
    }
}
```

---

## Fix 6: Enhanced Lambda Notify Function

**Location**: Step 4.2

**Add error handling** to `notify_lambda.py`:

```python
def lambda_handler(event, context):
    """
    Triggered by S3 upload to users/{user_id}/output/*
    Sends email notification with download link or error details
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

        # Check if this is a PLY file
        if not filename.endswith('.ply'):
            print(f"Skipping non-PLY file: {key}")
            return {'statusCode': 200, 'body': 'Skipped'}

        # Validate PLY file size
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = response['ContentLength']
        file_size_mb = file_size / (1024 * 1024)

        if file_size < 1000:
            print(f"⚠️ Warning: Small file size: {file_size} bytes")
            # Still send notification but include warning

        # Generate pre-signed URL (24 hour expiry)
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=86400
        )

        # Send success notification
        send_success_notification(user_id, filename, download_url, file_size_mb)

        print(f"Success notification sent for user {user_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Notification sent',
                'user_id': user_id,
                'output_file': key,
                'file_size': file_size
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        raise e
```

---

## Summary of All Fixes

1. ✅ Renamed inference.py → sagemaker_handler.py (avoid naming collision)
2. ✅ Fixed Dockerfile PYTHONPATH and structure
3. ✅ Updated serve.py imports
4. ✅ Added validation to Extract Lambda (check mask exists)
5. ✅ Enhanced web interface to upload image + mask + metadata
6. ✅ Added error handling in Notify Lambda
7. ✅ Added error file creation in prediction failures
8. ✅ Added file size validation
9. ✅ Added comprehensive logging

---

## Application Instructions

These fixes should be applied to Implementation Plan v1.1 in the corresponding sections.
Each fix is marked with its location (Step X.Y) for easy reference.

---

*Document Version: 1.1*
*Last Updated: 2025-11-27*
