# Gen3D - Architecture Guide v1.2

**Version**: 1.2
**Date**: November 30, 2025
**Status**: Production Architecture with Hybrid Split Interactive Masking

---

## Executive Summary

Gen3D v1.2 is an advanced cloud-based service that combines Meta's SAM 3 (Segment Anything Model 3) and SAM 3D Objects foundation models to provide interactive, real-time object segmentation and 3D reconstruction from single 2D images. This version introduces a revolutionary **Hybrid Split Architecture** that enables zero-latency interactive mask creation in the browser while leveraging cloud GPU resources for computationally intensive operations.

### What's New in v1.2

**Interactive Mask Generation**:
- Real-time, zero-latency mask creation using client-side ONNX inference
- Click-based object selection with instant visual feedback
- Iterative refinement capabilities
- No server round-trips during interaction phase

**Hybrid Split Processing**:
- **Stage 1 (Server)**: Heavy image encoding to generate embeddings
- **Stage 2 (Client)**: Interactive mask decoding in browser
- **Stage 3 (Server)**: GPU-accelerated 3D reconstruction

**Enhanced User Experience**:
- Multi-step guided workflow
- Real-time progress indicators
- 3D visualization with Three.js
- Session-based architecture for resumable workflows

---

## System Overview

Gen3D v1.2 transforms the 3D reconstruction workflow from a simple "upload and wait" model to an interactive, user-guided experience. The system processes single RGB images through three distinct stages, each optimized for its specific computational requirements.

### Key Capabilities

- **Interactive Object Selection**: Point-and-click mask creation with real-time feedback
- **Single-Image 3D Reconstruction**: Complete 3D models with geometry and texture
- **Hybrid Processing**: Optimal distribution between client and server computation
- **Asynchronous Scalability**: GPU resource auto-scaling based on demand
- **Session Management**: Resumable workflows with state persistence
- **Multi-Object Support**: Extract multiple objects from single image
- **Secure User Isolation**: Cognito-based authentication with user-scoped storage

---

## Architecture Diagrams

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE LAYER                           │
│                   (S3 Static Website + CloudFront)                      │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Web Application                                                 │   │
│  │  • HTML5/CSS3/JavaScript                                        │   │
│  │  • AWS Amplify (Auth + Storage)                                 │   │
│  │  • ONNX Runtime Web (SAM Decoder)                               │   │
│  │  • Three.js (3D Visualization)                                  │   │
│  └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ HTTPS/REST API
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          API & ORCHESTRATION LAYER                      │
│  ┌─────────────────────┐    ┌──────────────────────────────────────┐  │
│  │  API Gateway        │────│  Lambda Functions                    │  │
│  │  • /initialize      │    │   • Gen3DWrapperLambda               │  │
│  │  • /reconstruct     │    │   • Gen3DNotifyLambda                │  │
│  │  • /status          │    │   • Gen3DErrorHandlerLambda          │  │
│  └─────────────────────┘    └──────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ SageMaker Async Invocation
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          ML INFERENCE LAYER                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  SageMaker Async Endpoint (ml.g5.2xlarge + GPU)                 │  │
│  │  ┌────────────────────┐    ┌────────────────────┐               │  │
│  │  │  SAM 3 Encoder     │    │  SAM 3D            │               │  │
│  │  │  (ViT-H)           │    │  Reconstructor     │               │  │
│  │  │  - Image → Embeddi │    │  - Image + Mask    │               │  │
│  │  │  - ~2-5 seconds    │    │  → 3D Point Cloud  │               │  │
│  │  │  - Output: 4MB JSON│    │  - ~30-60 seconds  │               │  │
│  │  └────────────────────┘    └────────────────────┘               │  │
│  │                                                                   │  │
│  │  Auto-scaling: Min=0, Max=5                                      │  │
│  │  Container: Single Docker image with both models                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ Read/Write
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          STORAGE & DATA LAYER                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Amazon S3 (gen3d-data-bucket)                                   │  │
│  │  ├── /public/           (Web app assets, ONNX models)            │  │
│  │  ├── /users/{id}/       (User sessions and outputs)              │  │
│  │  └── /models/           (SAM3 & SAM3D model artifacts)           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Amazon Cognito                                                   │  │
│  │  • User Authentication                                            │  │
│  │  • Identity Pool for S3 Access                                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Notifications
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     MONITORING & NOTIFICATION LAYER                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  CloudWatch     │  │  Amazon SES      │  │  SNS Topics          │  │
│  │  • Logs         │  │  • Email Notif.  │  │  • Success/Error     │  │
│  │  • Metrics      │  │  • Admin Alerts  │  │  • Status Updates    │  │
│  │  • Alarms       │  └──────────────────┘  └──────────────────────┘  │
│  └─────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Three-Stage Workflow Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: INITIALIZATION (Server-Heavy Processing)                        │
│  Timeline: ~2-5 seconds                                                    │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  User ──[Upload JPG]──▶ S3 ──[Trigger]──▶ Lambda ──[Async]──▶ SageMaker  │
│                                                        │                   │
│                                                        │ SAM 3 Encoder     │
│                                                        │ (ViT-H on GPU)    │
│                                                        ▼                   │
│  User ◀─[Download]─── S3 ◀──────────────── [embeddings.json (~4MB)]      │
│                                                                            │
│  Output: Image embeddings tensor (1, 256, 64, 64) serialized to JSON     │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: INTERACTION (Client-Only Processing)                            │
│  Timeline: Real-time (< 100ms per interaction)                            │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Browser ──[Load ONNX]──▶ SAM Mask Decoder Model (~40MB)                 │
│     │                                                                      │
│     │  ┌─────────────────────────────────────────────────────────┐       │
│     └──│  Interactive Loop (No Server Calls)                     │       │
│        │                                                          │       │
│        │  1. User clicks object                                  │       │
│        │  2. ONNX inference: embeddings + coords → mask          │       │
│        │  3. Display mask overlay (Canvas API)                   │       │
│        │  4. User refines (add/remove points)                    │       │
│        │  5. Repeat until satisfied                              │       │
│        │                                                          │       │
│        │  Performance: Zero latency, pure client-side           │       │
│        └─────────────────────────────────────────────────────────┘       │
│     │                                                                      │
│     └──[Confirm Mask]──▶ Convert canvas to PNG ──▶ Upload to S3          │
│                                                                            │
│  Output: Binary mask PNG stored in session folder                         │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: 3D RECONSTRUCTION (Server-Heavy Processing)                     │
│  Timeline: ~30-60 seconds                                                  │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Browser ──[POST /reconstruct]──▶ Lambda ──[Async]──▶ SageMaker          │
│                                                             │              │
│                                               SAM 3D Model │              │
│                                               • Load image + mask          │
│                                               • 3D reconstruction          │
│                                               • Generate point cloud       │
│                                                             ▼              │
│  Browser ◀──[Download]─── S3 ◀──────────── [output_mesh.ply (~5MB)]      │
│     │                                                                      │
│     └──[Render]──▶ Three.js Viewer ──▶ Interactive 3D Display            │
│                                                                            │
│  Output: 3D Gaussian splat point cloud (.ply format)                      │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Web Application Layer

**Technology Stack**:
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Authentication**: AWS Amplify + Amazon Cognito
- **Storage**: AWS Amplify Storage (S3 wrapper)
- **ML Inference**: ONNX Runtime Web
- **3D Rendering**: Three.js with PLYLoader
- **API Communication**: Fetch API with async/await

**Key Features**:

#### 1.1 Interactive Mask Creation
- Canvas-based image editing
- Real-time ONNX model inference
- Point/click-based segmentation
- Visual mask overlay with adjustable opacity
- Multi-point refinement (foreground/background)
- Instant feedback (< 100ms response)

#### 1.2 Session Management
- Unique session IDs for each workflow
- State persistence in S3
- Resume capability
- History tracking

#### 1.3 3D Visualization
- WebGL-accelerated point cloud rendering
- Interactive camera controls (rotate, zoom, pan)
- Lighting and material adjustments
- Wireframe toggle
- Screenshot capture
- Download options (.ply export)

**Deployment**:
- Static hosting on S3
- CloudFront CDN distribution
- HTTPS enforced
- CORS configured for API access
- Cognito-authenticated access to user data

### 2. Amazon S3 Storage Architecture

**Bucket Structure**:
```
s3://gen3d-data-bucket/
│
├── public/                              # PUBLIC ACCESS
│   ├── index.html
│   ├── css/
│   │   ├── main.css
│   │   └── theme.css
│   ├── js/
│   │   ├── app.js                       # Main application logic
│   │   ├── sam-decoder.js               # ONNX mask generation
│   │   ├── three-viewer.js              # 3D visualization
│   │   ├── api-client.js                # API wrapper
│   │   └── utils.js
│   ├── libs/                            # Third-party libraries
│   │   ├── onnxruntime-web.min.js
│   │   ├── three.min.js
│   │   ├── PLYLoader.js
│   │   └── aws-amplify.min.js
│   ├── models/
│   │   └── sam_vit_h_decoder.onnx      # 40MB client-side model
│   └── assets/
│       ├── logo.png
│       ├── icons/
│       └── tutorials/
│
├── users/                               # USER-SCOPED ACCESS
│   └── {cognito_identity_id}/           # Unique per user
│       └── sessions/
│           └── {session_id}/            # Format: sess_{timestamp}_{uuid}
│               ├── original_image.jpg   # Stage 1: User upload
│               ├── embeddings.json      # Stage 1: SAM3 output (4MB)
│               ├── mask_final.png       # Stage 2: User-confirmed mask
│               ├── output_mesh.ply      # Stage 3: Final 3D output
│               ├── metadata.json        # Session info & timestamps
│               └── thumbnail.jpg        # Preview image (optional)
│
└── models/                              # SAGEMAKER ACCESS ONLY
    ├── sam3/
    │   ├── sam3_vit_h.pth              # SAM 3 encoder weights (~2.5GB)
    │   └── config.yaml
    └── sam3d/
        ├── sam3d_checkpoint.pth        # SAM 3D weights (~3GB)
        └── pipeline.yaml
```

**Session Metadata Format** (`metadata.json`):
```json
{
  "session_id": "sess_1701234567_a1b2c3d4",
  "user_id": "us-east-1:abc-123-def-456",
  "created_at": "2025-11-30T10:30:00Z",
  "status": "completed",
  "stages": {
    "initialization": {
      "started_at": "2025-11-30T10:30:05Z",
      "completed_at": "2025-11-30T10:30:08Z",
      "duration_sec": 3.2,
      "embedding_size_mb": 3.8
    },
    "interaction": {
      "started_at": "2025-11-30T10:30:10Z",
      "completed_at": "2025-11-30T10:32:15Z",
      "num_clicks": 5,
      "num_refinements": 2
    },
    "reconstruction": {
      "started_at": "2025-11-30T10:32:20Z",
      "completed_at": "2025-11-30T10:33:05Z",
      "duration_sec": 45.3,
      "mesh_size_mb": 5.2,
      "num_points": 125000
    }
  },
  "image_info": {
    "original_filename": "chair_photo.jpg",
    "width": 1920,
    "height": 1080,
    "format": "JPEG"
  },
  "mask_info": {
    "num_pixels": 245760,
    "coverage_percent": 11.85
  }
}
```

**S3 Features**:
- Server-side encryption (SSE-S3)
- Versioning enabled for data recovery
- Lifecycle policies:
  - Move to S3-IA after 30 days
  - Move to Glacier after 90 days
  - Delete after 1 year
- Event notifications for workflow automation
- CORS configuration for browser uploads
- Pre-signed URLs for secure downloads

### 3. Amazon Cognito Authentication

**User Pool Configuration**:
- Email-based user registration
- Password requirements: 8+ chars, mixed case, numbers
- MFA optional (recommended for production)
- Email verification required
- Password reset via email
- Custom attributes: user_preferences, subscription_tier

**Identity Pool Configuration**:
- Federated identities support
- Authenticated role: `Gen3DAuthenticatedRole`
- Unauthenticated role: `Gen3DUnauth Role` (read-only public access)
- Identity-based S3 access: `users/${cognito-identity.amazonaws.com:sub}/*`

**Authentication Flow**:
```
1. User signs up → Email verification
2. User signs in → Cognito returns JWT tokens
3. App exchanges JWT → IAM temporary credentials
4. Credentials allow S3 access scoped to user's folder
5. Token refresh every 60 minutes
```

### 4. API Gateway & Lambda Functions

#### 4.1 API Gateway Configuration

**Endpoints**:
- `POST /initialize` - Start Stage 1 (embedding generation)
- `POST /reconstruct` - Start Stage 3 (3D reconstruction)
- `GET /status/{job_id}` - Poll job status
- `GET /sessions` - List user's sessions
- `DELETE /sessions/{session_id}` - Delete session

**Configuration**:
- REST API (not HTTP API) for full feature set
- Cognito authorizer on all endpoints
- CORS enabled for browser access
- Request validation enabled
- Rate limiting: 100 req/min per user
- Throttling: 1000 req/sec burst
- CloudWatch logging enabled

#### 4.2 Gen3DWrapperLambda Function

**Purpose**: API Gateway → SageMaker async invocation orchestrator

**Specifications**:
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 30 seconds
- Concurrent executions: 100
- Reserved concurrency: 20 (prevent throttling)

**Environment Variables**:
```
SAGEMAKER_ENDPOINT_NAME=gen3d-sam3-sam3d-endpoint
S3_BUCKET=gen3d-data-bucket
AWS_REGION=us-east-1
JOB_STATUS_TABLE=Gen3DJobStatus (DynamoDB)
```

**Request Handling**:

```python
def lambda_handler(event, context):
    """
    Handle API Gateway requests and invoke SageMaker async.
    """
    path = event['path']
    body = json.loads(event['body'])
    user_id = event['requestContext']['authorizer']['claims']['sub']

    if path == '/initialize':
        return handle_initialize(body, user_id)
    elif path == '/reconstruct':
        return handle_reconstruct(body, user_id)
    elif path.startswith('/status/'):
        job_id = path.split('/')[-1]
        return handle_status(job_id, user_id)
```

**Key Operations**:
1. Validate request parameters
2. Verify S3 object exists
3. Create SageMaker async invocation payload
4. Invoke endpoint with proper IAM credentials
5. Store job metadata in DynamoDB
6. Return job_id and status URL to client

#### 4.3 Gen3DNotifyLambda Function

**Purpose**: Send notifications when processing completes

**Trigger**: S3 PUT event on `users/*/sessions/*/output_mesh.ply`

**Specifications**:
- Runtime: Python 3.11
- Memory: 256 MB
- Timeout: 15 seconds
- Concurrent executions: 50

**Workflow**:
1. Parse S3 event to extract session info
2. Read metadata.json for user details
3. Generate pre-signed URL (24-hour expiry)
4. Format HTML email with download link
5. Send email via SES to user
6. Send copy to admin (info@2112-lab.com)
7. Update session status to "notified"
8. Log notification to CloudWatch

#### 4.4 Gen3DErrorHandlerLambda Function

**Purpose**: Handle SageMaker errors and notify users

**Trigger**: SNS topic subscribed to SageMaker error notifications

**Error Categorization**:
- **User Errors**: Invalid image, corrupted file, mask too small
- **System Errors**: Model crash, OOM, timeout
- **Transient Errors**: Network issues, S3 throttling

**Notification Strategy**:
- User errors → Friendly message with troubleshooting tips
- System errors → "Technical issue, we're investigating"
- Admin always receives full stack trace

### 5. Amazon SageMaker Async Inference

**Endpoint Configuration**:

**Model**: Single container with SAM 3 + SAM 3D
**Instance**: ml.g5.2xlarge
- GPU: NVIDIA A10G with 24GB VRAM
- vCPU: 8 cores
- Memory: 32 GB
- Storage: 500 GB EBS
- Cost: ~$1.21/hour (on-demand)

**Auto-Scaling**:
```python
{
    "MinCapacity": 0,  # Scale to zero when idle (cost optimization)
    "MaxCapacity": 5,  # Max 5 instances for burst traffic
    "TargetTrackingScalingPolicyConfiguration": {
        "CustomizedMetricSpecification": {
            "MetricName": "ApproximateBacklogSizePerInstance",
            "Namespace": "AWS/SageMaker",
            "Statistic": "Average",
            "Dimensions": [{
                "Name": "EndpointName",
                "Value": "gen3d-sam3-sam3d-endpoint"
            }]
        },
        "TargetValue": 2.0,  # Process 2 jobs per instance
        "ScaleInCooldown": 600,  # Wait 10 min before scaling in
        "ScaleOutCooldown": 60   # Scale out quickly (1 min)
    }
}
```

**Async Configuration**:
```python
{
    "OutputConfig": {
        "S3OutputPath": "s3://gen3d-data-bucket/users/",
        "NotificationConfig": {
            "SuccessTopic": "arn:aws:sns:region:account:gen3d-inference-success",
            "ErrorTopic": "arn:aws:sns:region:account:gen3d-inference-error"
        },
        "S3FailurePath": "s3://gen3d-data-bucket/errors/"
    },
    "ClientConfig": {
        "MaxConcurrentInvocationsPerInstance": 4  # GPU can handle 4 parallel
    }
}
```

**Container Architecture**:

The single Docker container hosts both models and a dispatcher:

```python
# inference.py (main entry point)
def model_fn(model_dir):
    """Load both models once at startup."""
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load SAM 3 Image Encoder
    sam3_encoder = load_sam3_encoder(
        checkpoint=f"{model_dir}/sam3/sam3_vit_h.pth",
        device=device
    )

    # Load SAM 3D Reconstructor
    sam3d_model = load_sam3d_model(
        checkpoint=f"{model_dir}/sam3d/sam3d_checkpoint.pth",
        device=device
    )

    return {
        "sam3_encoder": sam3_encoder,
        "sam3d_model": sam3d_model
    }

def predict_fn(input_data, models):
    """
    Dispatcher for different tasks.
    """
    task = input_data.get("task")

    if task == "get_embedding":
        return process_stage1_initialization(input_data, models)
    elif task == "generate_3d":
        return process_stage3_reconstruction(input_data, models)
    else:
        raise ValueError(f"Unknown task: {task}")
```

**Stage 1: Initialization Processing**:
```python
def process_stage1_initialization(input_data, models):
    """
    Generate embeddings from image using SAM 3 encoder.
    """
    # Download image from S3
    image_s3_key = input_data['image_s3_key']
    image = load_image_from_s3(image_s3_key)

    # Preprocess (resize to 1024x1024, normalize)
    image_tensor = preprocess_image(image)

    # Run SAM 3 Image Encoder (ViT-H)
    with torch.no_grad():
        embeddings = models['sam3_encoder'].encode_image(image_tensor)

    # Serialize embeddings to base64
    embeddings_np = embeddings.cpu().numpy().astype(np.float32)
    embeddings_b64 = base64.b64encode(embeddings_np.tobytes()).decode('utf-8')

    # Prepare output
    output = {
        "status": "success",
        "task": "get_embedding",
        "embedding": embeddings_b64,
        "shape": list(embeddings_np.shape),
        "image_size": [1024, 1024],
        "dtype": "float32"
    }

    # Save to S3
    output_s3_key = image_s3_key.replace('original_image.jpg', 'embeddings.json')
    save_json_to_s3(output, output_s3_key)

    return output
```

**Stage 3: Reconstruction Processing**:
```python
def process_stage3_reconstruction(input_data, models):
    """
    Generate 3D point cloud from image + mask using SAM 3D.
    """
    # Download image and mask from S3
    image = load_image_from_s3(input_data['image_s3_key'])
    mask = load_mask_from_s3(input_data['mask_s3_key'])

    # Validate mask (not all zeros)
    if not np.any(mask):
        raise ValueError("Mask is empty - no object selected")

    # Run SAM 3D reconstruction
    with torch.no_grad():
        point_cloud = models['sam3d_model'].reconstruct(
            image=image,
            mask=mask,
            quality=input_data.get('quality', 'high')
        )

    # Convert to PLY format
    ply_bytes = convert_to_ply(point_cloud)

    # Save to S3
    output_s3_key = input_data['mask_s3_key'].replace('mask_final.png', 'output_mesh.ply')
    save_bytes_to_s3(ply_bytes, output_s3_key)

    # Generate mesh statistics
    stats = {
        "num_points": len(point_cloud['vertices']),
        "file_size_mb": len(ply_bytes) / (1024 * 1024),
        "has_colors": 'colors' in point_cloud,
        "bounds": calculate_bounds(point_cloud['vertices'])
    }

    return {
        "status": "success",
        "task": "generate_3d",
        "output_s3_key": output_s3_key,
        "mesh_stats": stats
    }
```

### 6. Amazon SES (Email Notifications)

**Configuration**:
- Verified sender domain: genesis3d.com
- Verified sender address: noreply@genesis3d.com
- Verified admin address: info@2112-lab.com
- Production access (out of sandbox)
- DKIM configured for deliverability
- SPF record configured

**Email Templates**:

**Success Notification**:
```html
Subject: Your 3D Model is Ready!

<html>
<body>
  <h2>Gen3D - Your 3D Model is Ready</h2>
  <p>Hi {user_name},</p>
  <p>Your 3D reconstruction is complete! Your mesh contains <strong>{num_points}</strong> points.</p>

  <p><a href="{download_url}" style="background:#4CAF50;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Download Your 3D Model</a></p>

  <p><small>Download link expires in 24 hours.</small></p>

  <p>Session ID: {session_id}<br>
  File size: {file_size_mb} MB<br>
  Processing time: {processing_time_sec} seconds</p>

  <p>Thank you for using Gen3D!</p>
</body>
</html>
```

**Error Notification**:
```html
Subject: Gen3D Processing Error

<html>
<body>
  <h2>Gen3D - Processing Issue</h2>
  <p>Hi {user_name},</p>
  <p>Unfortunately, we encountered an issue processing your image.</p>

  <p><strong>Error:</strong> {error_message}</p>

  <p><strong>Troubleshooting:</strong></p>
  <ul>
    <li>Ensure your image is in JPEG or PNG format</li>
    <li>Check that the object mask is clearly defined</li>
    <li>Try with a different image or mask</li>
  </ul>

  <p>If the problem persists, please contact support: info@2112-lab.com</p>

  <p>Session ID: {session_id}</p>
</body>
</html>
```

### 7. Amazon CloudWatch Monitoring

**Log Groups**:
- `/aws/lambda/Gen3DWrapperLambda`
- `/aws/lambda/Gen3DNotifyLambda`
- `/aws/lambda/Gen3DErrorHandlerLambda`
- `/aws/sagemaker/Endpoints/gen3d-sam3-sam3d-endpoint`
- `/aws/apigateway/gen3d-api`

**Custom Metrics**:
```python
# Embedded in application code
cloudwatch.put_metric_data(
    Namespace='Gen3D',
    MetricData=[
        {
            'MetricName': 'Initialization.Duration',
            'Value': duration_ms,
            'Unit': 'Milliseconds',
            'Dimensions': [{'Name': 'Stage', 'Value': 'Stage1'}]
        },
        {
            'MetricName': 'Reconstruction.Success',
            'Value': 1,
            'Unit': 'Count'
        },
        {
            'MetricName': 'MeshSize',
            'Value': size_mb,
            'Unit': 'Megabytes'
        }
    ]
)
```

**CloudWatch Dashboards**:

**Dashboard 1: Real-Time Operations**
- Active SageMaker endpoints (widget: number)
- Current async queue depth (widget: line graph)
- Processing jobs in flight (widget: number)
- Error rate last 5 min (widget: gauge)
- API request rate (widget: line graph)

**Dashboard 2: Business Metrics**
- Daily session count (widget: bar chart)
- Success rate 7-day trend (widget: line graph)
- Average processing time (widget: line graph)
- Cost per mesh (widget: number with sparkline)
- User engagement (widget: heatmap)

**CloudWatch Alarms**:

**Critical** (PagerDuty integration):
- `Error Rate > 10%` (5-minute window)
- `SageMaker Endpoint Down`
- `Lambda Failures > 50/hour`
- `API Gateway 5xx > 100/hour`

**Warning** (Email to admin):
- `Processing Time p95 > 120 seconds`
- `Queue Depth > 20 for 10 minutes`
- `Cost > $100/day`
- `S3 Bucket Size > 1TB`

---

## Data Flow & User Journey

### Complete User Journey

**Pre-Stage: User Registration**
```
1. User visits https://gen3d.genesis3d.com
2. Clicks "Sign Up"
3. Enters email, password, name
4. Receives verification email
5. Clicks verification link
6. Account activated → Redirected to app
```

**Stage 1: Image Upload & Initialization (2-5 seconds)**
```
1. User logs in with Cognito credentials
2. App generates session_id
3. User selects/drags image file
4. JavaScript validates image (size, format)
5. App uploads to S3: users/{id}/sessions/{session_id}/original_image.jpg
6. App calls POST /initialize
7. API Gateway validates request
8. Lambda invokes SageMaker async
9. SageMaker:
   a. Downloads image from S3
   b. Runs SAM 3 Image Encoder (ViT-H)
   c. Generates embeddings (~4MB)
   d. Saves embeddings.json to S3
10. App polls GET /status/{job_id} every 2 seconds
11. When complete, app downloads embeddings.json
12. Transitions to Stage 2
```

**Stage 2: Interactive Mask Creation (30-120 seconds)**
```
1. App loads embeddings into memory
2. App loads SAM Mask Decoder ONNX model
3. Canvas displays original image
4. User clicks on object
5. JavaScript extracts click coordinates
6. ONNX inference: embeddings + coords → mask (< 100ms)
7. Canvas overlays mask with transparency
8. User sees immediate visual feedback
9. User can:
   a. Add foreground points (left click)
   b. Add background points (right click)
   c. Adjust mask threshold
   d. Reset and try again
10. Each interaction triggers instant ONNX inference
11. User satisfied with mask → Clicks "Confirm"
12. Canvas mask converted to PNG blob
13. PNG uploaded to S3: users/{id}/sessions/{session_id}/mask_final.png
14. Transitions to Stage 3
```

**Stage 3: 3D Reconstruction (30-60 seconds)**
```
1. App calls POST /reconstruct
2. API Gateway validates request
3. Lambda invokes SageMaker async
4. SageMaker:
   a. Downloads image and mask from S3
   b. Validates mask (not empty)
   c. Runs SAM 3D reconstruction
   d. Generates 3D point cloud
   e. Converts to PLY format
   f. Saves output_mesh.ply to S3
5. S3 PUT event triggers Gen3DNotifyLambda
6. Lambda:
   a. Generates pre-signed download URL
   b. Sends success email to user
   c. Sends copy to admin
7. App polls GET /status/{job_id}
8. When complete, app downloads output_mesh.ply
9. Three.js PLYLoader parses PLY file
10. WebGL renders 3D point cloud
11. User can:
    a. Rotate, zoom, pan camera
    b. Toggle wireframe
    c. Adjust point size
    d. Take screenshot
    e. Download PLY file
12. User can start new session or logout
```

### Error Handling Flows

**Initialization Errors**:
```
User uploads → S3 → Lambda → SageMaker
                                  ↓ (Error)
                             SNS Error Topic
                                  ↓
                           ErrorHandlerLambda
                                  ↓
                          Categorize Error
                                  ↓
                  ┌─────────────┴──────────────┐
            User Error                    System Error
                  ↓                             ↓
         Email: "Invalid image"      Email: "Technical issue"
         + Troubleshooting tips       Admin: Full stack trace
                  ↓                             ↓
         User retries                  Dev investigates
```

**Interaction Errors** (Client-Side):
```
User clicks → ONNX inference fails
                  ↓
         JavaScript catch block
                  ↓
         Display error message
                  ↓
         Log to CloudWatch (via API)
                  ↓
         Offer to reload model or restart session
```

**Reconstruction Errors**:
```
Similar to Initialization, but with additional checks:
- Mask validation (not empty)
- Mask/image size mismatch
- SAM 3D model crash
```

---

## Security Architecture

### Authentication & Authorization

**Cognito User Pool**:
- Enforces strong passwords
- MFA optional (recommended)
- Email verification required
- Token expiration: 60 minutes
- Refresh token valid: 30 days

**Cognito Identity Pool**:
- Authenticated users get temporary AWS credentials
- Credentials scoped to user's S3 folder only
- Cannot access other users' data
- Cannot access model artifacts
- Session duration: 1 hour

**IAM Policies** (Least Privilege):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::gen3d-data-bucket/users/${cognito-identity.amazonaws.com:sub}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::gen3d-data-bucket/public/*",
        "arn:aws:s3:::gen3d-data-bucket/models/*"
      ]
    }
  ]
}
```

### Data Protection

**Encryption at Rest**:
- S3: SSE-S3 (AES-256)
- DynamoDB: AWS-managed encryption
- SageMaker: EBS encryption enabled

**Encryption in Transit**:
- HTTPS enforced (TLS 1.2+)
- API Gateway: TLS only
- CloudFront: HTTPS redirect

**Data Isolation**:
- User folders scoped by Cognito Identity ID
- No cross-user access possible
- Session IDs unpredictable (UUID v4)
- Pre-signed URLs time-limited (24 hours)

### Network Security

**VPC Configuration** (SageMaker):
- Private subnets for endpoint
- NAT Gateway for internet access
- Security group: Ingress from Lambda only
- No public IP addresses

**API Security**:
- Rate limiting: 100 req/min per user
- Request validation enabled
- SQL injection prevention (input sanitization)
- CORS: Whitelist origins only

**Secrets Management**:
- HuggingFace token in Secrets Manager
- SES SMTP credentials in Secrets Manager
- Database connection strings encrypted
- Automatic rotation enabled

---

## Scalability & Performance

### Horizontal Scaling

**SageMaker**:
- Auto-scales 0-5 instances based on queue depth
- Each instance handles 4 concurrent requests
- Max throughput: 20 requests in parallel
- Queue absorbs traffic spikes

**Lambda**:
- Auto-scales to 100 concurrent executions
- Reserved concurrency prevents throttling
- Cold start mitigation: Provisioned concurrency for critical functions

**S3**:
- Unlimited scalability
- Request rate: 3,500 PUT/sec, 5,500 GET/sec per prefix
- Multi-part upload for large files

**API Gateway**:
- Default: 10,000 req/sec burst
- Steady state: 5,000 req/sec
- Can request limit increase

### Performance Optimization

**Caching**:
- CloudFront caches static assets (1-day TTL)
- Browser caching headers for immutable assets
- ONNX model cached in browser localStorage
- SageMaker model loaded once per instance (warm start)

**Latency Reduction**:
- CloudFront edge locations (global)
- Region selection close to users
- Async processing prevents API timeout
- Client-side ONNX eliminates Stage 2 server calls

**Cost Optimization**:
- SageMaker scales to zero (no idle cost)
- S3 Intelligent-Tiering for old data
- Lambda memory optimization (right-sizing)
- Spot instances for non-critical workloads (future)

### Capacity Planning

**Estimated Throughput**:
- Stage 1 (Initialization): ~720 requests/hour (5 instances × 4 concurrent × 12/min)
- Stage 2 (Interaction): Unlimited (client-side)
- Stage 3 (Reconstruction): ~240 requests/hour (5 instances × 4 concurrent × 60 sec)

**Bottlenecks**:
- SageMaker GPU instances (mitigated by auto-scaling)
- Lambda concurrent execution limit (can increase)
- API Gateway rate limits (can increase)

**Growth Projections**:
- 1,000 users/day: Current architecture sufficient
- 10,000 users/day: Increase max SageMaker instances to 10
- 100,000 users/day: Multi-region deployment recommended

---

## Disaster Recovery & Business Continuity

### Backup Strategy

**Data Backups**:
- S3 versioning enabled (restore deleted files)
- Cross-region replication (optional, for critical data)
- Daily snapshots of DynamoDB tables
- Model artifacts versioned in S3

**Configuration Backups**:
- Infrastructure as Code (CloudFormation/Terraform)
- Lambda code in Git repository
- Docker images tagged and stored in ECR
- Database schemas in version control

### Recovery Procedures

**Data Loss Scenarios**:
- Accidental file deletion: Restore from S3 versions
- Bucket deletion: Restore from cross-region replica
- Corruption: Rollback to previous version

**Service Outage**:
- SageMaker endpoint failure: Auto-restart via CloudWatch alarm
- Lambda failure: Automatic retries (3x)
- API Gateway: AWS manages availability
- S3: 99.999999999% durability guaranteed

**RTO/RPO Targets**:
- Recovery Time Objective (RTO): < 1 hour
- Recovery Point Objective (RPO): < 5 minutes (real-time replication)

### Incident Response

**Detection**:
- CloudWatch alarms trigger PagerDuty
- Automated health checks every 5 minutes
- User-reported errors logged

**Response**:
1. Identify affected component (SageMaker, Lambda, S3)
2. Check CloudWatch logs for root cause
3. Failover to backup region (if applicable)
4. Communicate with users via status page
5. Post-mortem document after resolution

---

## Compliance & Governance

### Data Residency
- All data stored in `us-east-1` region (configurable)
- Can deploy in EU regions for GDPR compliance
- User data never leaves configured region

### Privacy
- User data isolated by Cognito Identity ID
- No cross-user data access
- Data deletion on user request (7-day grace period)
- Audit trail via CloudTrail

### License Compliance
- SAM 3 License: Facebook Research (non-commercial)
- SAM 3D License: Facebook Research (non-commercial)
- ONNX Runtime: MIT License
- Three.js: MIT License

### Access Reviews
- Quarterly IAM permission audits
- Annual security assessment
- Penetration testing annually
- Dependency vulnerability scanning (Snyk)

---

## Future Enhancements

### Short-Term (v1.3 - Q1 2026)
- **Mesh Export Formats**: OBJ, GLB, FBX in addition to PLY
- **Batch Processing**: Process multiple objects in one session
- **Quality Presets**: Fast/Balanced/Quality modes
- **Mobile App**: iOS and Android native apps
- **WebSocket Status Updates**: Replace polling with real-time

### Medium-Term (v1.4 - Q2 2026)
- **SAM 3D Body Integration**: Human mesh reconstruction
- **Advanced Mask Editing**: Brush tool, eraser, layers
- **Collaborative Sessions**: Share session with team members
- **Model Fine-Tuning**: Custom model training per user
- **API for Developers**: REST API with SDKs

### Long-Term (v2.0 - Q3 2026)
- **Multi-View Reconstruction**: Combine multiple images
- **Video Processing**: Extract 3D from video frames
- **AR Integration**: View models in augmented reality
- **Enterprise Features**: SSO, team management, quotas
- **Marketplace**: Buy/sell 3D models

---

## Conclusion

Gen3D v1.2 represents a significant architectural evolution from v1.0, introducing interactive mask creation that dramatically improves user experience while maintaining the scalability and cost-efficiency of a serverless architecture. The Hybrid Split approach optimally distributes computation between client and server, ensuring zero-latency interaction while leveraging cloud GPU resources for compute-intensive tasks.

The system is designed for production deployment with comprehensive security, monitoring, error handling, and disaster recovery capabilities. The modular architecture allows for future enhancements without requiring major refactoring.

**Key Architectural Achievements**:
- ✅ Zero-latency interactive mask creation
- ✅ Optimal cost efficiency (scale to zero)
- ✅ Secure multi-tenant architecture
- ✅ Comprehensive monitoring and alerting
- ✅ Production-ready error handling
- ✅ Scalable to 10,000+ users/day

---

**Document Version**: 1.2
**Last Updated**: November 30, 2025
**Status**: PRODUCTION READY
**Authors**: Gen3D Architecture Team
**Contact**: info@2112-lab.com
