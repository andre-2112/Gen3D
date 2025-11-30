# **Technical Architecture: Meta SAM 3 & SAM 3D Reconstruction Pipeline**

Date: November 2025  
Target Infrastructure: AWS (SageMaker Asynchronous Inference) \+ Hybrid Client/Server Interactivity

## **1\. Executive Summary**

This document outlines a high-performance "Text/Click-to-3D" pipeline. It allows users to interactively segment objects in a browser with zero latency and subsequently reconstruct them into 3D meshes using Meta's **SAM 3D** model.

The architecture uses a **Hybrid Split** approach:

1. **Heavy Compute (Server):** Image Encoding & 3D Reconstruction.  
2. **Interactive Compute (Client):** Mask Decoding & User Guidance.

## **2\. Logical Workflow (The "Hybrid" Pattern)**

### **Stage 1: Initialization**

1. **User** uploads an RGB image to S3.  
2. **Client** requests "Initialization" from SageMaker.  
3. **SageMaker** runs **SAM 3 Image Encoder** (ViT-H).  
4. **SageMaker** returns **Image Embeddings** (approx. 4MB) to the client.

### **Stage 2: Interaction (Client-Side)**

1. **Client** loads the **SAM Mask Decoder** (ONNX model) in the browser.  
2. **User** clicks on the object.  
3. **Browser** runs the ONNX model using the *Embeddings* \+ *Click Coordinates*.  
4. **Result:** Instant mask generation (milliseconds) with zero server latency.  
5. **User** confirms the selection.

### **Stage 3: 3D Reconstruction (Server-Side)**

1. **Client** uploads the final binary mask (PNG) to S3.  
2. **Client** triggers the "Reconstruct" job on SageMaker.  
3. **SageMaker** loads **SAM 3D**.  
4. **SageMaker** inputs the *Original Image* \+ *Binary Mask*.  
5. **Result:** A 3D Mesh (.obj/.glb) is generated and saved to S3.

## **3\. Infrastructure & Components**

### **A. AWS SageMaker Asynchronous Inference**

We use **Async Inference** because SAM 3D requires GPUs and processing times can exceed standard API gateway timeouts (60s). It also allows **scaling to zero** to save costs.

* **Instance Type:** ml.g5.2xlarge (NVIDIA A10G, 24GB VRAM).  
* **Autoscaling:** Min=0, Max=5.

### **B. Client-Side Libraries**

* **Interactivity:** onnxruntime-web or @xenova/transformers.  
* **3D Preview:** Three.js or Google \<model-viewer\>.

## **4\. Code Implementation**

### **4.1 Server-Side Inference Script (inference.py)**

This script handles both "Embedding Generation" and "3D Reconstruction" tasks within the same container.

import os  
import json  
import torch  
import numpy as np  
import base64  
from PIL import Image  
from io import BytesIO

\# Import SAM libraries (Simulated)  
from sam3 import sam\_model\_registry, SAM3Predictor  
from sam3d import SAM3DObjectReconstructor

def model\_fn(model\_dir):  
    """Load models into VRAM once at startup."""  
    device \= "cuda" if torch.cuda.is\_available() else "cpu"  
      
    \# Load SAM 3 (ViT-Huge)  
    sam \= sam\_model\_registry\["vit\_h"\](checkpoint=f"{model\_dir}/sam3\_vit\_h.pth")  
    sam\_predictor \= SAM3Predictor(sam)  
    sam\_predictor.model.to(device)

    \# Load SAM 3D  
    sam3d \= SAM3DObjectReconstructor.from\_pretrained(f"{model\_dir}/sam3d", device=device)  
      
    return {"sam": sam\_predictor, "sam3d": sam3d}

def predict\_fn(input\_data, models):  
    """  
    Dispatcher for different tasks.  
    Expected Input JSON: { "task": "...", "image\_path": "...", "mask\_path": "..." }  
    """  
    task \= input\_data.get("task")  
    image\_path \= input\_data.get("image\_path")  
      
    \# Load Original Image  
    image \= Image.open(image\_path).convert("RGB")

    \# \--- TASK A: GET EMBEDDINGS (For Client Interactivity) \---  
    if task \== "get\_embedding":  
        \# Run Image Encoder Only  
        with torch.no\_grad():  
            \# transform\_image is a helper from SAM utils  
            input\_image \= models\["sam"\].transform.apply\_image(np.array(image))  
            input\_image\_torch \= torch.as\_tensor(input\_image, device="cuda")  
            input\_image\_torch \= input\_image\_torch.permute(2, 0, 1).contiguous()\[None, :, :, :\]  
              
            features \= models\["sam"\].model.image\_encoder(input\_image\_torch)  
              
        \# Serialize features (1, 256, 64, 64\) \-\> Base64  
        features\_np \= features.cpu().numpy().astype(np.float32)  
        encoded\_features \= base64.b64encode(features\_np.tobytes()).decode('utf-8')  
          
        return {  
            "status": "success",  
            "embedding": encoded\_features,  
            "shape": features\_np.shape  
        }

    \# \--- TASK B: GENERATE 3D (Final Output) \---  
    elif task \== "generate\_3d":  
        mask\_path \= input\_data.get("mask\_path")  
          
        \# Load the Client-Generated Mask  
        mask\_image \= Image.open(mask\_path).convert("L") \# Grayscale  
        mask\_bool \= np.array(mask\_image) \> 128  
          
        \# Run SAM 3D  
        mesh\_bytes \= models\["sam3d"\].reconstruct(  
            image=image,  
            mask=mask\_bool,  
            quality="high"  
        )  
          
        return mesh\_bytes

    else:  
        raise ValueError(f"Unknown task: {task}")

### **4.2 The Lambda Wrapper**

This triggers the Async Endpoint.

import boto3  
import json  
import uuid

sm\_runtime \= boto3.client("sagemaker-runtime")

def lambda\_handler(event, context):  
    body \= json.loads(event\['body'\])  
    task \= body.get('task') \# 'get\_embedding' or 'generate\_3d'  
      
    \# Invoke SageMaker Async  
    response \= sm\_runtime.invoke\_endpoint\_async(  
        EndpointName="sam3-3d-pipeline",  
        InputLocation=body\['input\_s3\_uri'\], \# JSON file on S3 containing task params  
        InvocationTimeoutSeconds=3600  
    )  
      
    return {  
        "statusCode": 202,  
        "body": json.dumps({  
            "job\_id": response\['InferenceId'\],  
            "output\_path": response\['OutputLocation'\]  
        })  
    }

### **4.3 Dockerfile (SageMaker Image)**

FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

RUN apt-get update && apt-get install \-y libgl1-mesa-glx git

\# Install Dependencies  
RUN pip install \--no-cache-dir \\  
    sagemaker-inference \\  
    opencv-python \\  
    transformers \\  
    diffusers \\  
    accelerate \\  
    scipy

\# Install SAM 3 & SAM 3D  
RUN pip install git+\[https://github.com/facebookresearch/segment-anything-3.git\](https://github.com/facebookresearch/segment-anything-3.git)  
RUN pip install git+\[https://github.com/facebookresearch/sam-3d.git\](https://github.com/facebookresearch/sam-3d.git)

COPY inference.py /opt/ml/code/inference.py  
ENV SAGEMAKER\_PROGRAM inference.py  
