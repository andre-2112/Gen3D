# ONNX and Hybrid Split Architecture - User Guide

**Purpose**: High-level explanation of ONNX Runtime Web and how it enables client-side mask generation in Gen3D

**Date**: 2025-12-03

**Audience**: Developers integrating ONNX models into the Gen3D web application

---

## Table of Contents

1. [What is ONNX?](#1-what-is-onnx)
2. [Why ONNX for Gen3D?](#2-why-onnx-for-gen3d)
3. [Hybrid Split Architecture](#3-hybrid-split-architecture)
4. [How ONNX Enables Client-Side Masking](#4-how-onnx-enables-client-side-masking)
5. [User Guide: Integrating ONNX into Gen3D](#5-user-guide-integrating-onnx-into-gen3d)
6. [Performance Optimization](#6-performance-optimization)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. What is ONNX?

### 1.1 ONNX Definition

**ONNX** (Open Neural Network Exchange) is an open-source format for representing machine learning models.

**Key Characteristics**:
- **Interoperable**: Models trained in PyTorch, TensorFlow, etc. can be exported to ONNX
- **Portable**: Same model file runs on different platforms (server, browser, mobile)
- **Optimized**: Runtime engines apply hardware-specific optimizations
- **Standardized**: Consistent input/output interface across frameworks

**Analogy**: ONNX is like a "universal adapter" for AI models—train anywhere, run anywhere.

### 1.2 ONNX Runtime

**ONNX Runtime** is the execution engine that runs ONNX models.

**Flavors**:
- **ONNX Runtime** (Python/C++): Server-side execution with GPU/CPU
- **ONNX Runtime Web**: Browser-based execution (JavaScript/WebAssembly)
- **ONNX Runtime Mobile**: iOS/Android execution

**For Gen3D, we use**: **ONNX Runtime Web**

### 1.3 ONNX Runtime Web

**What it does**: Runs AI models directly in the user's web browser.

**How it works**:
```
┌─────────────────────────────────────────────────────────────┐
│                      Web Browser                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  JavaScript Application (app.js)                            │
│         │                                                   │
│         ├──> Load ONNX model from S3                       │
│         │    (sam3_mask_decoder.onnx, 1.4 GB)              │
│         │                                                   │
│         v                                                   │
│  ONNX Runtime Web (ort.min.js)                              │
│         │                                                   │
│         ├──> Parse ONNX model                              │
│         ├──> Compile to WebAssembly                        │
│         ├──> Use WebGL for GPU acceleration (optional)     │
│         │                                                   │
│         v                                                   │
│  Run Inference (in browser, no server needed)              │
│         │                                                   │
│         ├──> Input: Image embeddings + points + bbox       │
│         └──> Output: Binary mask (1024×1024)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Advantages**:
- **Privacy**: Data never leaves user's browser
- **Latency**: No round-trip to server (~50-200ms vs. ~500-2000ms)
- **Cost**: No server GPU costs for mask generation
- **Scalability**: Distributes compute to user devices

**Trade-offs**:
- **Initial Load**: 1.4 GB model download (one-time, cached)
- **Performance**: Slower than server GPU (but acceptable for masking)
- **Compatibility**: Requires modern browser (Chrome 90+, Firefox 88+)

---

## 2. Why ONNX for Gen3D?

### 2.1 Problem: Expensive Mask Generation

**Without ONNX** (Server-side only):
```
User clicks on image
    │
    ├──> Send request to SageMaker
    ├──> Queue request (async)
    ├──> Wait for GPU instance to wake up (~60s cold start)
    ├──> Run mask inference (~1s)
    ├──> Upload mask to S3
    ├──> Poll S3 for result
    │
    └──> Total: 65-120 seconds per mask
         Cost: $0.50-$1.00 per hour (ml.g5.2xlarge)
```

**Cost Analysis**:
- **ml.g5.2xlarge**: $1.515/hour = $0.000421/second
- **Per mask**: 60s (cold start) + 1s (inference) = $0.026
- **100 masks/day**: $2.60/day = $78/month
- **1000 users × 10 masks**: $260/1000 users

**Problems**:
- High latency (60+ seconds)
- High cost ($78/month for light usage)
- Poor user experience (long wait times)

### 2.2 Solution: Hybrid Split Architecture

**With ONNX** (Client-side masking):
```
User clicks on image
    │
    ├──> Run mask inference IN BROWSER (50-200ms)
    │
    └──> Instant feedback, $0 cost
```

**Benefits**:
- **Latency**: 50-200ms (120x faster)
- **Cost**: $0 (no server inference)
- **UX**: Real-time feedback
- **Scalability**: No server load

**Trade-off**:
- **Initial setup**: 1.4 GB model download (one-time)
- **Performance**: Depends on user's CPU (but acceptable)

### 2.3 Why Split SAM into Encoder + Decoder?

**SAM Model Architecture**:
```
┌───────────────────────────────────────────────────────────────┐
│                    SAM (Segment Anything)                      │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌─────────────────────┐        │
│  │  Image Encoder   │────────>│   Mask Decoder      │        │
│  │  (ViT-Huge)      │         │   (Lightweight)     │        │
│  │                  │         │                     │        │
│  │  Input: Image    │         │  Input: Embeddings │        │
│  │  Output: 256×64× │         │         + Prompts  │        │
│  │          64      │         │  Output: Mask      │        │
│  │  Size: 6.5 GB    │         │  Size: 1.4 GB      │        │
│  │  Compute: Heavy  │         │  Compute: Light    │        │
│  │  (GPU required)  │         │  (CPU ok)          │        │
│  └──────────────────┘         └─────────────────────┘        │
│         │                              │                      │
│         └──────────────────────────────┘                      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Why Split?**

| Component | Image Encoder | Mask Decoder |
|-----------|---------------|--------------|
| **Size** | 6.5 GB | 1.4 GB |
| **Compute** | Heavy (GPU) | Light (CPU) |
| **Frequency** | Once per image | Multiple times (user refinement) |
| **Latency** | 1-3 seconds | 50-200ms |
| **Best Location** | Server (GPU) | Browser (CPU) |

**Key Insight**: The encoder is expensive but runs once. The decoder is cheap and runs many times during refinement.

**Optimal Split**:
- **Server (SageMaker)**: Run encoder once, generate embeddings
- **Client (Browser)**: Run decoder many times as user refines mask
- **Result**: Fast feedback + low cost

---

## 3. Hybrid Split Architecture

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Gen3D Hybrid Split                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Stage 1: Image Embeddings (SERVER-SIDE, ONE-TIME)                      │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │                                                            │          │
│  │  User uploads image                                       │          │
│  │        │                                                   │          │
│  │        v                                                   │          │
│  │  ┌──────────┐      ┌──────────────────────┐              │          │
│  │  │  WebApp  │─────>│  SageMaker Endpoint   │              │          │
│  │  │          │      │  (ml.g5.2xlarge)      │              │          │
│  │  └──────────┘      │  SAM3 Image Encoder   │              │          │
│  │                    │  (6.5 GB, GPU)        │              │          │
│  │                    └──────────────────────┘              │          │
│  │                             │                             │          │
│  │                             v                             │          │
│  │                    ┌──────────────┐                       │          │
│  │                    │  Embeddings  │                       │          │
│  │                    │  (256×64×64) │                       │          │
│  │                    │  Saved to S3 │                       │          │
│  │                    └──────────────┘                       │          │
│  │                                                            │          │
│  └──────────────────────────────────────────────────────────┘          │
│                             │                                            │
│                             │ Download embeddings                        │
│                             v                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                          │
│  Stage 2: Interactive Masking (CLIENT-SIDE, REAL-TIME)                  │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │                                                            │          │
│  │  User draws bounding box / clicks points                  │          │
│  │        │                                                   │          │
│  │        v                                                   │          │
│  │  ┌──────────────────────────────────────────┐             │          │
│  │  │     Browser (ONNX Runtime Web)           │             │          │
│  │  │                                           │             │          │
│  │  │  Input:                                   │             │          │
│  │  │    - Embeddings (256×64×64)               │             │          │
│  │  │    - Bounding box coords                  │             │          │
│  │  │    - Foreground/background points         │             │          │
│  │  │                                           │             │          │
│  │  │  ONNX Model:                              │             │          │
│  │  │    - sam3_mask_decoder.onnx (1.4 GB)     │             │          │
│  │  │    - Runs on user's CPU                   │             │          │
│  │  │                                           │             │          │
│  │  │  Output:                                  │             │          │
│  │  │    - Binary mask (1024×1024)              │             │          │
│  │  │    - Latency: 50-200ms                    │             │          │
│  │  │                                           │             │          │
│  │  └──────────────────────────────────────────┘             │          │
│  │        │                                                   │          │
│  │        v                                                   │          │
│  │  Display mask overlay (real-time feedback)                │          │
│  │                                                            │          │
│  └──────────────────────────────────────────────────────────┘          │
│                             │                                            │
│                             │ Upload final mask to S3                    │
│                             v                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                          │
│  Stage 3: 3D Reconstruction (SERVER-SIDE, ONE-TIME)                     │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │                                                            │          │
│  │  User clicks "Generate 3D"                                │          │
│  │        │                                                   │          │
│  │        v                                                   │          │
│  │  ┌──────────┐      ┌──────────────────────┐              │          │
│  │  │  WebApp  │─────>│  SageMaker Endpoint   │              │          │
│  │  │          │      │  (ml.g5.2xlarge)      │              │          │
│  │  └──────────┘      │  SAM3D Model          │              │          │
│  │                    │  (12 GB, GPU)         │              │          │
│  │                    └──────────────────────┘              │          │
│  │                             │                             │          │
│  │                             v                             │          │
│  │                    ┌──────────────┐                       │          │
│  │                    │  PLY File    │                       │          │
│  │                    │  Point Cloud │                       │          │
│  │                    │  Saved to S3 │                       │          │
│  │                    └──────────────┘                       │          │
│  │                                                            │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

**Stage 1 → Stage 2**:
```
SageMaker generates embeddings (256×64×64, ~16 MB)
    │
    ├──> Upload to S3: users/{user_id}/{session_id}/embeddings.json
    │
    └──> WebApp downloads embeddings (16 MB, ~2 seconds)
```

**Stage 2 (Client-side loop)**:
```
User interaction (bbox, points)
    │
    ├──> ONNX Runtime Web inference (50-200ms)
    │
    └──> Display mask overlay (instant)

Repeat until user is satisfied
```

**Stage 2 → Stage 3**:
```
Final mask generated in browser
    │
    ├──> Export as PNG (binary: 0=bg, 255=fg)
    │
    ├──> Upload to S3: users/{user_id}/{session_id}/mask.png
    │
    └──> Trigger Stage 3 reconstruction
```

### 3.3 Cost Breakdown

| Stage | Location | Compute | Cost/Operation | Frequency |
|-------|----------|---------|----------------|-----------|
| **Stage 1: Embeddings** | Server (GPU) | SAM3 Encoder | $0.026 | Once per image |
| **Stage 2: Masking** | Client (CPU) | SAM3 Decoder | $0.00 | 5-20 times (refinement) |
| **Stage 3: 3D** | Server (GPU) | SAM3D Model | $0.10 | Once per image |
| **Total** | Mixed | - | **$0.126** | **Per complete workflow** |

**vs. Server-only approach**:
- Server-only: $0.026 × 10 (masks) + $0.10 = **$0.36** per workflow
- Hybrid: **$0.126** per workflow
- **Savings**: 65% cost reduction

---

## 4. How ONNX Enables Client-Side Masking

### 4.1 The Masking Workflow

**User Action → Inference → Visual Feedback**:

```
1. User draws bounding box
       │
       ├──> JavaScript captures coordinates: (x1, y1, x2, y2)
       │
       v
2. Convert to SAM format
       │
       ├──> Normalize coords: [0, 1] range
       ├──> Create point_coords: [[x1, y1], [x2, y2]]
       ├──> Create point_labels: [2, 3] (bbox corners)
       │
       v
3. Prepare ONNX inputs
       │
       ├──> image_embeddings: Float32Array[1, 256, 64, 64]
       ├──> point_coords: Float32Array[1, 2, 2]
       ├──> point_labels: Float32Array[1, 2]
       │
       v
4. Run ONNX inference
       │
       ├──> ort.InferenceSession.run(...)
       ├──> Latency: 50-200ms
       │
       v
5. Process output
       │
       ├──> masks: Float32Array[1, 1, 1024, 1024]
       ├──> Threshold at 0.5: binary mask
       │
       v
6. Render mask overlay
       │
       ├──> Draw blue overlay on canvas
       └──> User sees result instantly
```

**Time from click to visual feedback**: **< 250ms**

### 4.2 Input Preparation

**Image Embeddings** (from Stage 1):
```javascript
// Downloaded from S3 after Stage 1
const embeddings = await fetch(embeddingsUrl).then(r => r.json());

// Shape: [1, 256, 64, 64]
// Size: ~16 MB
// Format: Float32Array
```

**Point Coordinates** (from user interaction):
```javascript
// User draws bounding box: (100, 100) to (500, 500)
const bbox = {
    x1: 100, y1: 100,
    x2: 500, y2: 500
};

// Normalize to [0, 1] range
const point_coords = new Float32Array([
    bbox.x1 / imageWidth,  bbox.y1 / imageHeight,  // Top-left
    bbox.x2 / imageWidth,  bbox.y2 / imageHeight   // Bottom-right
]);

// Shape: [1, 2, 2] (batch=1, num_points=2, xy=2)
```

**Point Labels**:
```javascript
// SAM label convention:
// 0 = background point
// 1 = foreground point
// 2 = top-left corner of bounding box
// 3 = bottom-right corner of bounding box

const point_labels = new Float32Array([2, 3]);  // Bounding box
// Shape: [1, 2] (batch=1, num_points=2)
```

### 4.3 Running ONNX Inference

```javascript
// 1. Load ONNX model (one-time, on page load)
const session = await ort.InferenceSession.create(
    'https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx'
);

// 2. Create input tensors
const feeds = {
    'image_embeddings': new ort.Tensor(
        'float32',
        embeddings.data,
        [1, 256, 64, 64]
    ),
    'point_coords': new ort.Tensor(
        'float32',
        point_coords,
        [1, 2, 2]
    ),
    'point_labels': new ort.Tensor(
        'float32',
        point_labels,
        [1, 2]
    )
};

// 3. Run inference
const results = await session.run(feeds);

// 4. Extract mask output
const maskData = results.masks.data;  // Float32Array[1048576] (1024×1024)
const maskShape = results.masks.dims;  // [1, 1, 1024, 1024]
```

### 4.4 Post-Processing and Rendering

```javascript
// 1. Threshold mask (sigmoid output → binary)
const binaryMask = new Uint8Array(maskData.length);
for (let i = 0; i < maskData.length; i++) {
    binaryMask[i] = maskData[i] > 0.5 ? 255 : 0;
}

// 2. Resize to canvas dimensions (if needed)
const resizedMask = resizeMask(binaryMask, canvasWidth, canvasHeight);

// 3. Render as blue overlay
const maskCanvas = document.getElementById('mask-canvas');
const ctx = maskCanvas.getContext('2d');
const imageData = ctx.createImageData(canvasWidth, canvasHeight);

for (let i = 0; i < resizedMask.length; i++) {
    const idx = i * 4;
    if (resizedMask[i] > 0) {
        imageData.data[idx + 0] = 0;    // R
        imageData.data[idx + 1] = 120;  // G
        imageData.data[idx + 2] = 255;  // B
        imageData.data[idx + 3] = 153;  // A (60% opacity)
    }
}

ctx.putImageData(imageData, 0, 0);
```

---

## 5. User Guide: Integrating ONNX into Gen3D

### 5.1 Prerequisites

**1. ONNX Model Available in S3**:
```
https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx
```

**2. ONNX Runtime Web Loaded** (already in `index.html`):
```html
<script src="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.16.3/dist/ort.min.js"></script>
```

**3. Image Embeddings Available** (from Stage 1):
```javascript
STATE.imageEmbeddings = {
    embedding: Float32Array[1, 256, 64, 64],
    shape: [1, 256, 64, 64]
};
```

### 5.2 Step 1: Load ONNX Model

Add to `initializeStage2()` in `app.js`:

```javascript
async function initializeStage2() {
    console.log('[Stage 2] Initializing masking interface...');

    // Load ONNX model (with progress tracking)
    try {
        console.log('[Stage 2] Loading ONNX model...');
        showLoading('Loading mask decoder model (1.4 GB, one-time download)...');

        const modelUrl = 'https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx';

        STATE.onnxSession = await ort.InferenceSession.create(modelUrl, {
            executionProviders: ['wasm'],  // Use WebAssembly backend
            graphOptimizationLevel: 'all'
        });

        console.log('[Stage 2] ONNX model loaded successfully');
        hideLoading();

    } catch (error) {
        console.error('[Stage 2] Failed to load ONNX model:', error);
        showErrorBanner('Failed to load mask decoder model. Falling back to mock inference.');

        // Continue with mock inference if ONNX fails
        STATE.onnxSession = null;
    }

    // Continue with canvas setup...
    const img = document.getElementById('preview-img');
    const imageCanvas = document.getElementById('image-canvas');
    // ... rest of initializeStage2
}
```

### 5.3 Step 2: Replace Mock Inference with ONNX

Update `MaskingInterface.triggerInference()` in `app.js`:

```javascript
async triggerInference() {
    console.log('[Stage 2] Triggering inference...');
    const startTime = performance.now();

    try {
        let maskData;

        // Use ONNX if available, otherwise fall back to mock
        if (STATE.onnxSession && STATE.imageEmbeddings) {
            console.log('[Stage 2] Running ONNX inference...');
            maskData = await this.runONNXInference();
        } else {
            console.log('[Stage 2] Running mock inference (ONNX not available)...');
            maskData = this.generateMockMask();
        }

        const inferenceTime = (performance.now() - startTime).toFixed(1);
        console.log(`[Stage 2] Inference completed in ${inferenceTime}ms`);

        // Render mask overlay
        this.renderMask(maskData);

        // Update status panel
        this.updateStatus('inference_time', `${inferenceTime}ms`);
        this.updateStatus('mode', STATE.onnxSession ? 'ONNX' : 'MOCK');

    } catch (error) {
        console.error('[Stage 2] Inference failed:', error);
        showErrorBanner('Mask inference failed. Please try again.');
    }
}
```

### 5.4 Step 3: Implement ONNX Inference Method

Add new method to `MaskingInterface` class:

```javascript
async runONNXInference() {
    // 1. Prepare inputs
    const inputs = this.prepareONNXInputs();

    // 2. Run inference
    const results = await STATE.onnxSession.run({
        'image_embeddings': inputs.imageEmbeddings,
        'point_coords': inputs.pointCoords,
        'point_labels': inputs.pointLabels
    });

    // 3. Process output
    const maskTensor = results.masks;
    const maskData = this.processONNXOutput(maskTensor);

    return maskData;
}

prepareONNXInputs() {
    const { width, height } = this.imageCanvas;

    // Get embeddings from STATE
    const embeddingData = STATE.imageEmbeddings.embedding;
    const embeddingShape = STATE.imageEmbeddings.shape;

    // Collect all prompts (bbox + foreground/background points)
    const allPoints = [];
    const allLabels = [];

    // Add bounding box
    if (this.bboxStart && this.bboxEnd) {
        const x1 = this.bboxStart.x / width;
        const y1 = this.bboxStart.y / height;
        const x2 = this.bboxEnd.x / width;
        const y2 = this.bboxEnd.y / height;

        allPoints.push([x1, y1], [x2, y2]);
        allLabels.push(2, 3);  // Bbox corners
    }

    // Add foreground points
    this.foregroundPoints.forEach(pt => {
        allPoints.push([pt.x / width, pt.y / height]);
        allLabels.push(1);  // Foreground
    });

    // Add background points
    this.backgroundPoints.forEach(pt => {
        allPoints.push([pt.x / width, pt.y / height]);
        allLabels.push(0);  // Background
    });

    // Create tensors
    const pointCoordsData = new Float32Array(allPoints.flat());
    const pointLabelsData = new Float32Array(allLabels);

    return {
        imageEmbeddings: new ort.Tensor('float32', embeddingData, embeddingShape),
        pointCoords: new ort.Tensor('float32', pointCoordsData, [1, allPoints.length, 2]),
        pointLabels: new ort.Tensor('float32', pointLabelsData, [1, allPoints.length])
    };
}

processONNXOutput(maskTensor) {
    const maskData = maskTensor.data;  // Float32Array
    const [batch, channels, maskHeight, maskWidth] = maskTensor.dims;

    // Threshold at 0.5 to get binary mask
    const binaryMask = new Uint8ClampedArray(maskHeight * maskWidth);
    for (let i = 0; i < maskData.length; i++) {
        binaryMask[i] = maskData[i] > 0.5 ? 255 : 0;
    }

    // Resize to canvas dimensions if needed
    if (maskHeight !== this.maskCanvas.height || maskWidth !== this.maskCanvas.width) {
        return this.resizeMask(binaryMask, maskWidth, maskHeight);
    }

    return binaryMask;
}

resizeMask(mask, srcWidth, srcHeight) {
    const dstWidth = this.maskCanvas.width;
    const dstHeight = this.maskCanvas.height;
    const resized = new Uint8ClampedArray(dstWidth * dstHeight);

    const scaleX = srcWidth / dstWidth;
    const scaleY = srcHeight / dstHeight;

    for (let y = 0; y < dstHeight; y++) {
        for (let x = 0; x < dstWidth; x++) {
            const srcX = Math.floor(x * scaleX);
            const srcY = Math.floor(y * scaleY);
            const srcIdx = srcY * srcWidth + srcX;
            const dstIdx = y * dstWidth + x;
            resized[dstIdx] = mask[srcIdx];
        }
    }

    return resized;
}
```

### 5.5 Step 4: Add Loading Progress Indicator

```javascript
async function initializeStage2() {
    // ... existing code

    // Show progress during ONNX model download
    console.log('[Stage 2] Loading ONNX model (1.4 GB)...');
    updateLoadingMessage('Downloading mask decoder model...');
    updateLoadingMessage('This is a one-time download (~2-4 minutes)');
    updateLoadingMessage('Subsequent page loads will use cached model');

    try {
        STATE.onnxSession = await ort.InferenceSession.create(modelUrl);
        console.log('[Stage 2] ONNX model loaded and cached');

    } catch (error) {
        console.warn('[Stage 2] ONNX load failed, using mock inference');
        STATE.onnxSession = null;
    }

    hideLoading();
    // ... continue with canvas setup
}
```

### 5.6 Step 5: Test ONNX Integration

**Test Checklist**:
1. **First Load** (cold cache):
   - [ ] Loading message appears
   - [ ] Model downloads (~2-4 minutes)
   - [ ] Console shows "ONNX model loaded"
   - [ ] Status panel shows "ONNX" mode

2. **Bounding Box Inference**:
   - [ ] Draw bbox on canvas
   - [ ] Inference runs in 50-200ms (check console)
   - [ ] Blue mask overlay appears
   - [ ] Mask accuracy better than mock

3. **Point Refinement**:
   - [ ] Add foreground points → mask updates
   - [ ] Add background points → mask updates
   - [ ] Each update takes 50-200ms

4. **Subsequent Loads** (warm cache):
   - [ ] Model loads instantly from cache
   - [ ] No download required

**Debug Console Output**:
```
[Stage 2] Loading ONNX model...
[Stage 2] ONNX model loaded successfully
[Stage 2] Triggering inference...
[Stage 2] Running ONNX inference...
[Stage 2] Inference completed in 127.3ms
[Stage 2] Mask coverage: 34.2%
```

---

## 6. Performance Optimization

### 6.1 Model Loading Optimization

**Problem**: 1.4 GB model takes 2-4 minutes to download on first load.

**Solutions**:

1. **Browser Caching** (already enabled):
```javascript
// ONNX Runtime Web automatically caches models in browser
// Subsequent loads are instant
```

2. **Pre-load on Login**:
```javascript
// Start loading ONNX model immediately after login
async function handleSuccessfulAuth(session) {
    // ... existing code

    // Pre-load ONNX model in background
    console.log('[Auth] Pre-loading ONNX model...');
    preloadONNXModel();
}

async function preloadONNXModel() {
    try {
        const modelUrl = 'https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx';
        STATE.onnxSession = await ort.InferenceSession.create(modelUrl);
        console.log('[Preload] ONNX model ready');
    } catch (error) {
        console.warn('[Preload] ONNX model preload failed:', error);
    }
}
```

3. **Service Worker Caching**:
```javascript
// service-worker.js (create new file)
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('gen3d-models-v1').then((cache) => {
            return cache.add('https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx');
        })
    );
});
```

### 6.2 Inference Performance Optimization

**Problem**: Inference may be slow on older devices.

**Solutions**:

1. **Use WebAssembly Backend**:
```javascript
const session = await ort.InferenceSession.create(modelUrl, {
    executionProviders: ['wasm']  // Fastest on CPU
});
```

2. **Enable WebGL (if available)**:
```javascript
const session = await ort.InferenceSession.create(modelUrl, {
    executionProviders: ['webgl', 'wasm']  // Try WebGL first, fall back to WASM
});
```

3. **Debounce User Input**:
```javascript
let inferenceTimeout;

handleMouseMove(e) {
    // ... draw bounding box

    // Debounce inference during drag
    clearTimeout(inferenceTimeout);
    inferenceTimeout = setTimeout(() => {
        this.triggerInference();
    }, 100);  // Wait 100ms after user stops moving
}
```

4. **Show Spinner During Inference**:
```javascript
async triggerInference() {
    // Show spinner
    document.getElementById('inference-spinner').style.display = 'block';

    const maskData = await this.runONNXInference();

    // Hide spinner
    document.getElementById('inference-spinner').style.display = 'none';

    this.renderMask(maskData);
}
```

### 6.3 Memory Optimization

**Problem**: Large tensors may cause memory issues.

**Solutions**:

1. **Dispose Old Tensors**:
```javascript
async runONNXInference() {
    // Create tensors
    const inputs = this.prepareONNXInputs();

    // Run inference
    const results = await STATE.onnxSession.run(inputs);

    // Dispose input tensors to free memory
    inputs.imageEmbeddings.dispose();
    inputs.pointCoords.dispose();
    inputs.pointLabels.dispose();

    // Process output
    const maskData = this.processONNXOutput(results.masks);

    // Dispose output tensor
    results.masks.dispose();

    return maskData;
}
```

2. **Limit History Size**:
```javascript
// Only keep last 10 interactions
if (this.history.length > 10) {
    this.history.shift();
}
```

---

## 7. Troubleshooting

### Issue 1: ONNX Model Fails to Load

**Error**:
```
Failed to load ONNX model: TypeError: Failed to fetch
```

**Causes**:
- Model not uploaded to S3
- Incorrect model URL
- S3 bucket not public
- CORS not configured

**Solutions**:
```bash
# 1. Verify model exists in S3
aws s3 ls s3://gen3d-data-bucket/models/sam3/

# 2. Check public access
aws s3api get-object-acl --bucket gen3d-data-bucket --key models/sam3/sam3_mask_decoder.onnx

# 3. Set public-read if needed
aws s3api put-object-acl \
    --bucket gen3d-data-bucket \
    --key models/sam3/sam3_mask_decoder.onnx \
    --acl public-read

# 4. Test download
curl -I https://gen3d-data-bucket.s3.us-east-1.amazonaws.com/models/sam3/sam3_mask_decoder.onnx
```

### Issue 2: ONNX Inference Returns Error

**Error**:
```
Error: Error during model inference
```

**Causes**:
- Incorrect input shapes
- Missing embeddings
- Invalid point coordinates

**Debug**:
```javascript
async runONNXInference() {
    const inputs = this.prepareONNXInputs();

    // Log input shapes for debugging
    console.log('[ONNX Debug] Input shapes:');
    console.log('  image_embeddings:', inputs.imageEmbeddings.dims);
    console.log('  point_coords:', inputs.pointCoords.dims);
    console.log('  point_labels:', inputs.pointLabels.dims);

    try {
        const results = await STATE.onnxSession.run(inputs);
        console.log('[ONNX Debug] Output shape:', results.masks.dims);
        return this.processONNXOutput(results.masks);

    } catch (error) {
        console.error('[ONNX Debug] Inference failed:', error);
        console.error('[ONNX Debug] Input data:', {
            embeddings: inputs.imageEmbeddings.data.slice(0, 10),
            coords: inputs.pointCoords.data,
            labels: inputs.pointLabels.data
        });
        throw error;
    }
}
```

### Issue 3: Slow Inference Performance

**Symptom**: Inference takes >500ms

**Causes**:
- Running on old/slow device
- Using CPU backend instead of WebGL
- Large input size

**Solutions**:

1. **Check execution provider**:
```javascript
const session = await ort.InferenceSession.create(modelUrl, {
    executionProviders: ['webgl', 'wasm']
});

console.log('Using provider:', session.executionProviders);
```

2. **Profile inference**:
```javascript
async runONNXInference() {
    const t0 = performance.now();
    const inputs = this.prepareONNXInputs();
    const t1 = performance.now();

    const results = await STATE.onnxSession.run(inputs);
    const t2 = performance.now();

    const maskData = this.processONNXOutput(results.masks);
    const t3 = performance.now();

    console.log(`[Perf] Input prep: ${(t1-t0).toFixed(1)}ms`);
    console.log(`[Perf] ONNX run: ${(t2-t1).toFixed(1)}ms`);
    console.log(`[Perf] Post-process: ${(t3-t2).toFixed(1)}ms`);

    return maskData;
}
```

3. **Fall back to mock if too slow**:
```javascript
async triggerInference() {
    const startTime = performance.now();
    const maskData = await this.runONNXInference();
    const inferenceTime = performance.now() - startTime;

    // If ONNX is too slow (>500ms), suggest mock mode
    if (inferenceTime > 500) {
        console.warn('[Stage 2] ONNX inference slow, consider mock mode');
        showWarningBanner('Mask generation is slow on this device. Consider using a faster browser or device.');
    }

    this.renderMask(maskData);
}
```

### Issue 4: Mask Quality Poor

**Symptom**: Generated masks are inaccurate

**Causes**:
- Incorrect normalization of coordinates
- Wrong point labels
- Embeddings from wrong image

**Debug**:
```javascript
prepareONNXInputs() {
    const { width, height } = this.imageCanvas;

    // ... prepare inputs

    // Validate inputs
    console.log('[Validation] Canvas size:', width, height);
    console.log('[Validation] Bbox:', this.bboxStart, this.bboxEnd);
    console.log('[Validation] Normalized coords:', allPoints);
    console.log('[Validation] Labels:', allLabels);

    // Check if coordinates are in [0, 1] range
    for (const [x, y] of allPoints) {
        if (x < 0 || x > 1 || y < 0 || y > 1) {
            console.error('[Validation] Invalid normalized coords:', x, y);
        }
    }

    // ... create tensors
}
```

---

## Summary

**What You Learned**:
1. **ONNX** enables running AI models in web browsers
2. **Hybrid Split** architecture optimizes cost and latency
3. **SAM3 Mask Decoder** runs client-side for real-time masking
4. **Integration** requires loading ONNX model and replacing mock inference
5. **Optimization** techniques for performance and user experience

**Key Benefits**:
- **65% cost reduction** vs. server-only approach
- **120x faster** mask generation (50-200ms vs. 60+ seconds)
- **Real-time feedback** for better user experience
- **Privacy**: User data stays in browser
- **Scalability**: No server load for masking

**Next Steps**:
1. Follow **ONNX-Model-Generation-Plan.md** to generate/upload model
2. Integrate ONNX inference using code examples above
3. Test thoroughly on different devices and browsers
4. Monitor performance and optimize as needed

---

**Document Version**: 1.0
**Date**: 2025-12-03
**Author**: Gen3D Development Team
