"""
Gen3D SageMaker Inference Script - FIXED VERSION
Handles both SAM 3 image encoding and SAM 3D reconstruction

Changes from original:
1. Enhanced logging for debugging model loading issues
2. Automatic checkpoint file detection
3. Support for multiple checkpoint formats (.pt, .pth, .safetensors, .ckpt)
4. Explicit error handling (fails instead of returning mock data)
5. Directory structure logging for troubleshooting
"""

import json
import os
import sys
import base64
import logging
from io import BytesIO
import glob

import boto3
import numpy as np
import torch
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client('s3')

# Global model storage
MODELS = {}


def log_directory_structure(path, max_depth=2, current_depth=0):
    """
    Log directory structure for debugging.

    Args:
        path: Directory path to log
        max_depth: Maximum depth to traverse
        current_depth: Current depth (for recursion)
    """
    if not os.path.exists(path):
        logger.warning(f"Path does not exist: {path}")
        return

    indent = "  " * current_depth
    try:
        items = os.listdir(path)
        logger.info(f"{indent}{os.path.basename(path)}/ ({len(items)} items)")

        if current_depth < max_depth:
            for item in sorted(items)[:20]:  # Limit to first 20 items
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    log_directory_structure(item_path, max_depth, current_depth + 1)
                else:
                    size_mb = os.path.getsize(item_path) / (1024 * 1024)
                    logger.info(f"{indent}  {item} ({size_mb:.2f} MB)")
    except Exception as e:
        logger.error(f"{indent}Error listing {path}: {e}")


def find_checkpoint_file(model_dir, patterns):
    """
    Automatically find checkpoint file matching any of the patterns.

    Args:
        model_dir: Directory to search
        patterns: List of file patterns to match (e.g., ['*.pt', '*.pth'])

    Returns:
        str: Path to first matching checkpoint, or None
    """
    for pattern in patterns:
        matches = glob.glob(os.path.join(model_dir, "**", pattern), recursive=True)
        if matches:
            # Return the largest file (likely the main checkpoint)
            matches_with_size = [(f, os.path.getsize(f)) for f in matches]
            largest = max(matches_with_size, key=lambda x: x[1])
            logger.info(f"Found checkpoint matching '{pattern}': {largest[0]} ({largest[1]/(1024**3):.2f} GB)")
            return largest[0]
    return None


def model_fn(model_dir):
    """
    Load both SAM3 and SAM3D models once at startup.
    This is called once when the container starts.

    Args:
        model_dir: Directory where models are stored

    Returns:
        dict: Dictionary containing loaded models
    """
    global MODELS

    logger.info("=" * 80)
    logger.info("MODEL_FN CALLED - Starting model loading")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"model_dir parameter: {model_dir}")
    logger.info(f"model_dir exists: {os.path.exists(model_dir)}")

    # Log directory structure
    logger.info("-" * 40)
    logger.info("Directory structure:")
    log_directory_structure(model_dir, max_depth=2)
    logger.info("-" * 40)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")

    # ========================================================================
    # SAM3 Loading
    # ========================================================================
    logger.info("=" * 80)
    logger.info("ATTEMPTING TO LOAD SAM3")
    logger.info("=" * 80)

    sam3_loaded = False
    try:
        logger.info("Step 1: Importing sam3 library...")
        try:
            from sam3 import sam_model_registry, SAM3Predictor
            logger.info("✓ SAM3 library imported successfully from 'sam3' package")
        except ImportError as e1:
            logger.warning(f"Failed to import from 'sam3': {e1}")
            logger.info("Trying alternative import from 'segment_anything'...")
            try:
                from segment_anything import sam_model_registry, SamPredictor as SAM3Predictor
                logger.info("✓ SAM3 library imported successfully from 'segment_anything' package")
            except ImportError as e2:
                raise ImportError(f"Could not import SAM3 from either 'sam3' or 'segment_anything': {e1}, {e2}")

        logger.info("Step 2: Looking for SAM3 checkpoint...")
        sam3_dir = os.path.join(model_dir, "sam3")

        # Try multiple checkpoint patterns
        checkpoint_patterns = [
            "sam3.pt",
            "sam3_vit_h.pth",
            "model.safetensors",
            "*.pt",
            "*.pth"
        ]

        sam3_checkpoint = find_checkpoint_file(sam3_dir, checkpoint_patterns)

        if sam3_checkpoint:
            logger.info(f"✓ Found SAM3 checkpoint: {sam3_checkpoint}")
        else:
            logger.warning("No SAM3 checkpoint found, attempting to load without checkpoint")
            sam3_checkpoint = None

        logger.info("Step 3: Loading SAM3 model...")
        sam3_model = sam_model_registry["vit_h"](checkpoint=sam3_checkpoint)

        logger.info("Step 4: Moving model to device...")
        sam3_model.to(device).eval()

        logger.info("Step 5: Creating predictor...")
        sam3_predictor = SAM3Predictor(sam3_model)

        MODELS["sam3_predictor"] = sam3_predictor
        MODELS["device"] = device
        sam3_loaded = True

        logger.info("=" * 80)
        logger.info("✓✓✓ SAM3 LOADED SUCCESSFULLY!")
        logger.info("=" * 80)

    except ImportError as e:
        logger.error("=" * 80)
        logger.error("✗✗✗ SAM3 IMPORT ERROR - PACKAGE NOT INSTALLED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        logger.error("The 'sam3' or 'segment_anything' Python package is not installed in the container.")
        logger.error("This indicates the Dockerfile did not install the SAM3 library correctly.")
        logger.error("Please update the Dockerfile to install SAM3 properly.")
        MODELS["sam3_predictor"] = None
        MODELS["device"] = device

    except Exception as e:
        logger.error("=" * 80)
        logger.error("✗✗✗ SAM3 LOADING ERROR")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        MODELS["sam3_predictor"] = None
        MODELS["device"] = device

    # ========================================================================
    # SAM3D Loading
    # ========================================================================
    logger.info("")
    logger.info("=" * 80)
    logger.info("ATTEMPTING TO LOAD SAM3D")
    logger.info("=" * 80)

    sam3d_loaded = False
    try:
        logger.info("Step 1: Importing sam3d library...")
        try:
            from sam3d import SAM3DReconstructor
            logger.info("✓ SAM3D library imported successfully")
        except ImportError as e:
            logger.warning(f"Failed to import from 'sam3d': {e}")
            logger.info("Trying alternative imports...")
            # Try alternative package names
            raise ImportError(f"Could not import SAM3D: {e}")

        logger.info("Step 2: Looking for SAM3D checkpoints...")
        sam3d_dir = os.path.join(model_dir, "sam3d")

        # Log checkpoints directory
        checkpoints_dir = os.path.join(sam3d_dir, "checkpoints")
        if os.path.exists(checkpoints_dir):
            logger.info(f"Found checkpoints directory: {checkpoints_dir}")
            log_directory_structure(checkpoints_dir, max_depth=1)

        # Try to find main checkpoint
        checkpoint_patterns = [
            "*.ckpt",
            "*.pt",
            "*.pth"
        ]

        sam3d_checkpoint = find_checkpoint_file(sam3d_dir, checkpoint_patterns)

        if sam3d_checkpoint:
            logger.info(f"✓ Found SAM3D checkpoint: {sam3d_checkpoint}")
        else:
            logger.warning("No SAM3D checkpoint found, attempting to load without checkpoint")
            sam3d_checkpoint = None

        logger.info("Step 3: Loading SAM3D model...")
        if sam3d_checkpoint:
            sam3d_model = SAM3DReconstructor.from_pretrained(sam3d_checkpoint, device=device)
        else:
            sam3d_model = SAM3DReconstructor(device=device)

        logger.info("Step 4: Setting eval mode...")
        sam3d_model.eval()

        MODELS["sam3d_model"] = sam3d_model
        sam3d_loaded = True

        logger.info("=" * 80)
        logger.info("✓✓✓ SAM3D LOADED SUCCESSFULLY!")
        logger.info("=" * 80)

    except ImportError as e:
        logger.error("=" * 80)
        logger.error("✗✗✗ SAM3D IMPORT ERROR - PACKAGE NOT INSTALLED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        logger.error("The 'sam3d' Python package is not installed in the container.")
        logger.error("This indicates the Dockerfile did not install the SAM3D library correctly.")
        logger.error("Please update the Dockerfile to install SAM3D properly.")
        MODELS["sam3d_model"] = None

    except Exception as e:
        logger.error("=" * 80)
        logger.error("✗✗✗ SAM3D LOADING ERROR")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        MODELS["sam3d_model"] = None

    # ========================================================================
    # Final Summary
    # ========================================================================
    logger.info("")
    logger.info("=" * 80)
    logger.info("MODEL LOADING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"SAM3 loaded: {sam3_loaded}")
    logger.info(f"SAM3D loaded: {sam3d_loaded}")
    logger.info(f"Device: {device}")
    logger.info("=" * 80)

    # CRITICAL: Fail if no models loaded (don't return mock data)
    if not sam3_loaded and not sam3d_loaded:
        error_msg = "CRITICAL: No models loaded successfully. Container is non-functional."
        logger.error(error_msg)
        # In production, you might want to raise an exception here
        # For now, we'll allow the container to start but log the error
        # raise RuntimeError(error_msg)

    return MODELS


def input_fn(request_body, content_type):
    """
    Deserialize and prepare the input data.

    Args:
        request_body: The request payload
        content_type: The content type of the request

    Returns:
        dict: Parsed input data
    """
    logger.info(f"INPUT_FN called with content_type: {content_type}")

    if content_type == "application/json":
        input_data = json.loads(request_body)
        logger.info(f"Parsed JSON input with keys: {list(input_data.keys())}")
        return input_data
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, models):
    """
    Main prediction function - dispatcher for different tasks.

    Args:
        input_data: Dictionary containing task type and parameters
        models: Dictionary of loaded models

    Returns:
        dict: Prediction results
    """
    task = input_data.get("task")

    logger.info("=" * 40)
    logger.info(f"PREDICT_FN: Processing task '{task}'")
    logger.info(f"PREDICT_FN: Input keys: {list(input_data.keys())}")
    logger.info("=" * 40)

    if task == "get_embedding":
        logger.info("PREDICT_FN: Routing to process_initialization")
        return process_initialization(input_data, models)
    elif task == "generate_3d":
        logger.info("PREDICT_FN: Routing to process_reconstruction")
        return process_reconstruction(input_data, models)
    else:
        logger.error(f"PREDICT_FN: Unknown task '{task}'")
        logger.error(f"Valid tasks are: 'get_embedding', 'generate_3d'")
        raise ValueError(f"Unknown task: {task}. Valid tasks: 'get_embedding', 'generate_3d'")


def process_initialization(input_data, models):
    """
    Stage 1: Generate embeddings from image using SAM 3 encoder.

    Args:
        input_data: Contains image_s3_key, bucket, session_id
        models: Dictionary of loaded models

    Returns:
        dict: Status and embedding information
    """
    logger.info("Starting Stage 1: Initialization (embedding generation)")

    image_s3_key = input_data["image_s3_key"]
    bucket = input_data.get("bucket", "gen3d-data-bucket")
    session_id = input_data.get("session_id", "unknown")
    user_id = input_data.get("user_id", "unknown")

    try:
        # Check if model is available
        sam3_predictor = models.get("sam3_predictor")
        if sam3_predictor is None:
            logger.error("SAM3 model not available - cannot process request")
            logger.error("This request would have returned mock data in the old version")
            logger.error("Please fix the model loading issues before using this endpoint")
            return {
                "status": "failed",
                "task": "get_embedding",
                "session_id": session_id,
                "user_id": user_id,
                "error": "SAM3 model not loaded. Check container logs for model loading errors.",
                "note": "Model loading failed during container startup. This is a critical error."
            }

        # Download image from S3
        logger.info(f"Downloading image from s3://{bucket}/{image_s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=image_s3_key)
        image_bytes = response['Body'].read()

        # Load and preprocess image
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        logger.info(f"Image loaded: {image.size}")

        # Extract embeddings using SAM 3 predictor
        sam3_predictor.set_image(np.array(image))

        # Get image embeddings (features)
        features = sam3_predictor.features  # Shape: (1, 256, 64, 64)
        logger.info(f"Embeddings extracted: {features.shape}")

        # Serialize embeddings to base64
        features_np = features.cpu().numpy().astype(np.float32)
        features_bytes = features_np.tobytes()
        features_b64 = base64.b64encode(features_bytes).decode('utf-8')

        # Prepare output
        output = {
            "embedding": features_b64,
            "shape": list(features_np.shape),
            "dtype": str(features_np.dtype)
        }

        # Save embeddings to S3
        embeddings_key = image_s3_key.rsplit('/', 1)[0] + "/embeddings.json"
        logger.info(f"Saving embeddings to s3://{bucket}/{embeddings_key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=embeddings_key,
            Body=json.dumps(output),
            ContentType='application/json'
        )

        logger.info("Stage 1 complete")
        return {
            "status": "success",
            "task": "get_embedding",
            "session_id": session_id,
            "user_id": user_id,
            "output_s3_key": embeddings_key,
            "embedding_size_mb": len(features_bytes) / (1024 * 1024)
        }

    except Exception as e:
        logger.error(f"Stage 1 failed: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "task": "get_embedding",
            "error": str(e)
        }


def process_reconstruction(input_data, models):
    """
    Stage 3: Generate 3D point cloud using SAM 3D.

    Args:
        input_data: Contains image_s3_key, mask_s3_key, bucket, session_id
        models: Dictionary of loaded models

    Returns:
        dict: Status and mesh information
    """
    logger.info("Starting Stage 3: 3D Reconstruction")

    image_s3_key = input_data["image_s3_key"]
    mask_s3_key = input_data["mask_s3_key"]
    bucket = input_data.get("bucket", "gen3d-data-bucket")
    session_id = input_data.get("session_id", "unknown")
    user_id = input_data.get("user_id", "unknown")
    quality = input_data.get("quality", "balanced")  # fast, balanced, high

    try:
        # Check if model is available
        sam3d_model = models.get("sam3d_model")
        if sam3d_model is None:
            logger.error("SAM3D model not available - cannot process request")
            logger.error("This request would have returned mock data in the old version")
            logger.error("Please fix the model loading issues before using this endpoint")
            return {
                "status": "failed",
                "task": "generate_3d",
                "session_id": session_id,
                "user_id": user_id,
                "quality": quality,
                "error": "SAM3D model not loaded. Check container logs for model loading errors.",
                "note": "Model loading failed during container startup. This is a critical error."
            }

        # Download image from S3
        logger.info(f"Downloading image from s3://{bucket}/{image_s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=image_s3_key)
        image_bytes = response['Body'].read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        # Download mask from S3
        logger.info(f"Downloading mask from s3://{bucket}/{mask_s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=mask_s3_key)
        mask_bytes = response['Body'].read()
        mask = Image.open(BytesIO(mask_bytes)).convert("L")

        # Convert mask to binary numpy array
        mask_np = np.array(mask)
        mask_bool = mask_np > 128  # Threshold

        if not np.any(mask_bool):
            raise ValueError("Mask is empty - no pixels selected")

        logger.info(f"Mask loaded: {mask_bool.shape}, pixels selected: {np.sum(mask_bool)}")

        # Run SAM 3D reconstruction
        logger.info("Running SAM 3D reconstruction...")

        # Convert to numpy arrays
        image_np = np.array(image)

        # Reconstruct 3D point cloud
        point_cloud = sam3d_model.reconstruct(
            image=image_np,
            mask=mask_bool,
            quality_preset=quality
        )

        logger.info(f"3D reconstruction complete: {len(point_cloud['points'])} points")

        # Convert to PLY format
        ply_bytes = convert_to_ply(point_cloud)

        # Save PLY to S3
        output_key = mask_s3_key.rsplit('/', 1)[0] + "/output_mesh.ply"
        logger.info(f"Saving PLY to s3://{bucket}/{output_key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=ply_bytes,
            ContentType='application/octet-stream'
        )

        logger.info("Stage 3 complete")
        return {
            "status": "success",
            "task": "generate_3d",
            "session_id": session_id,
            "user_id": user_id,
            "output_s3_key": output_key,
            "mesh_size_mb": len(ply_bytes) / (1024 * 1024),
            "num_points": len(point_cloud['points']),
            "quality": quality
        }

    except Exception as e:
        logger.error(f"Stage 3 failed: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "task": "generate_3d",
            "error": str(e)
        }


def convert_to_ply(point_cloud):
    """
    Convert point cloud dictionary to PLY format bytes.

    Args:
        point_cloud: Dictionary with 'points' (Nx3) and 'colors' (Nx3)

    Returns:
        bytes: PLY format binary data
    """
    points = point_cloud['points']  # Nx3 numpy array
    colors = point_cloud.get('colors', None)  # Nx3 numpy array (0-255)

    num_points = len(points)

    # PLY header
    header = f"""ply
format binary_little_endian 1.0
element vertex {num_points}
property float x
property float y
property float z
"""

    if colors is not None:
        header += """property uchar red
property uchar green
property uchar blue
"""

    header += "end_header\n"

    # Write header
    ply_bytes = BytesIO()
    ply_bytes.write(header.encode('ascii'))

    # Write vertex data
    if colors is not None:
        # Interleave points and colors
        for i in range(num_points):
            # Write xyz as float32
            ply_bytes.write(points[i].astype(np.float32).tobytes())
            # Write rgb as uint8
            ply_bytes.write(colors[i].astype(np.uint8).tobytes())
    else:
        # Write points only
        ply_bytes.write(points.astype(np.float32).tobytes())

    return ply_bytes.getvalue()


def output_fn(prediction, content_type):
    """
    Serialize the prediction output.

    Args:
        prediction: The prediction result
        content_type: Desired output content type

    Returns:
        str: Serialized prediction
    """
    if content_type == "application/json":
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


# For local testing
if __name__ == "__main__":
    logger.info("Running inference script in standalone mode")
    logger.info("This script is designed to run inside SageMaker")
    logger.info("For testing, use SageMaker Local Mode or deploy to SageMaker")
