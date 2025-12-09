# SAM 3D Objects - Missing Libraries Download Links and Usage

This document provides download links and usage details for libraries that failed to install and are actually used in the SAM 3D Objects codebase.

## Critical Libraries (Used in Code)

These 15 libraries are directly imported and used in the sam3d codebase:

### 1. MoGe ⚠️ CRITICAL
**Status**: Git repository, Download failed
**PyPI**: Not available on PyPI
**GitHub**: https://github.com/microsoft/MoGe
**Download**: `git clone https://github.com/microsoft/MoGe.git` or `pip install git+https://github.com/microsoft/MoGe.git@a8c37341bc0325ca99b9d57981cc3bb2bd3e255b`

**Usage in Code**:
- `sam3d_objects/pipeline/utils/pointmap.py` - Geometry utilities
- `notebook/mesh_alignment.py` - MoGe model loading

**Invocations**:
- `from moge.utils.geometry_torch import ...`
- `from moge.utils.geometry_numpy import ...`
- `from moge.model.v1 import MoGeModel`

---

### 2. astor
**Status**: Download succeeded, Import failed
**PyPI**: https://pypi.org/project/astor/
**GitHub**: https://github.com/berkerpeksag/astor
**Download**: `pip install astor==0.8.1`

**Usage in Code**:
- `sam3d_objects/data/utils.py:8` - Source code manipulation

**Invocations**:
- `import astor`
- `label = astor.to_source(args[argnum]).strip()`

---

### 3. easydict
**Status**: Download succeeded, Import failed
**PyPI**: https://pypi.org/project/easydict/
**GitHub**: https://github.com/makinacorpus/easydict
**Download**: `pip install easydict==1.13`

**Usage in Code**:
- Used in 4 files for EasyDict/edict functionality
- `sam3d_objects/model/backbone/tdfy_dit/representations/mesh/cube2mesh.py`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/gaussian_render.py`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py`

**Invocations**:
- `from easydict import EasyDict as edict`

---

### 4. hydra-core ⚠️ CRITICAL
**Status**: Download succeeded, Import failed
**PyPI**: https://pypi.org/project/hydra-core/
**GitHub**: https://github.com/facebookresearch/hydra
**Download**: `pip install hydra-core==1.3.2`

**Usage in Code**:
- Used in 3 files for configuration management
- `sam3d_objects/pipeline/inference_pipeline.py`
- `sam3d_objects/config/utils.py`
- `notebook/inference.py`

**Invocations**:
- `from hydra.utils import instantiate`
- `from hydra.utils import get_method`

---

### 5. igraph ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/igraph/
**GitHub**: https://github.com/igraph/python-igraph
**Download**: `pip install igraph==0.11.8`
**System Requirements**: May require C libraries

**Usage in Code**:
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:13`

**Invocations**:
- `import igraph`
- `g = igraph.Graph()`

---

### 6. lightning ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/lightning/
**GitHub**: https://github.com/Lightning-AI/pytorch-lightning
**Download**: `pip install lightning==2.3.3`

**Usage in Code**:
- `sam3d_objects/model/io.py:3`

**Invocations**:
- `import lightning.pytorch as pl`
- `from lightning.pytorch.utilities.consolidate_checkpoint import ...`

---

### 7. loguru ⚠️ CRITICAL
**Status**: Download succeeded, Import failed
**PyPI**: https://pypi.org/project/loguru/
**GitHub**: https://github.com/Delgan/loguru
**Download**: `pip install loguru==0.7.2`

**Usage in Code**:
- Used extensively (19 import statements across multiple files)
- Primary logging framework for the entire project

**Invocations**:
- `from loguru import logger`
- Used for all logging throughout the codebase

---

### 8. open3d ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/open3d/
**GitHub**: https://github.com/isl-org/Open3D
**Download**: `pip install open3d==0.18.0`
**System Requirements**: Requires OpenGL libraries

**Usage in Code**:
- Used extensively (13+ occurrences)
- `sam3d_objects/pipeline/layout_post_optimization_utils.py`
- `sam3d_objects/pipeline/inference_utils.py`

**Invocations**:
- `import open3d as o3d`
- `mesh_o3d = o3d.geometry.TriangleMesh()`
- `pcd = o3d.geometry.PointCloud()`
- Plane estimation and 3D geometry operations

---

### 9. opencv-python ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/opencv-python/
**GitHub**: https://github.com/opencv/opencv-python
**Download**: `pip install opencv-python==4.9.0.80`
**System Requirements**: May require video codec libraries

**Usage in Code**:
- Used in 4 files for image processing
- `sam3d_objects/pipeline/layout_post_optimization_utils.py`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py`
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py`
- `sam3d_objects/data/dataset/tdfy/img_and_mask_transforms.py`

**Invocations**:
- `import cv2`
- `cv2.getTextSize()`, `cv2.putText()`, `cv2.imwrite()`

---

### 10. optree ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/optree/
**GitHub**: https://github.com/metaopt/optree
**Download**: `pip install optree==0.14.1`

**Usage in Code**:
- Used extensively (20+ invocations across 4 files)
- `sam3d_objects/model/backbone/generator/shortcut/model.py`
- `sam3d_objects/model/backbone/generator/flow_matching/solver.py`
- `sam3d_objects/model/backbone/generator/flow_matching/model.py`
- `sam3d_objects/data/utils.py`

**Invocations**:
- `import optree`
- `optree.tree_flatten()`, `optree.tree_broadcast_map()`

---

### 11. pymeshfix
**Status**: Download failed
**PyPI**: https://pypi.org/project/pymeshfix/
**GitHub**: https://github.com/pyvista/pymeshfix
**Download**: `pip install pymeshfix==0.17.0`
**System Requirements**: Requires mesh processing C++ libraries

**Usage in Code**:
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:12`

**Invocations**:
- `from pymeshfix import _meshfix`

---

### 12. timm ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/timm/
**GitHub**: https://github.com/huggingface/pytorch-image-models
**Download**: `pip install timm==0.9.16`

**Usage in Code**:
- `sam3d_objects/model/backbone/dit/embedder/pointmap.py:2`

**Invocations**:
- `from timm.models.vision_transformer import Block`

---

### 13. xatlas
**Status**: Download failed
**PyPI**: https://pypi.org/project/xatlas/
**GitHub**: https://github.com/mworchel/xatlas-python
**Download**: `pip install xatlas==0.0.9`
**System Requirements**: May require C++ build tools

**Usage in Code**:
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:10`

**Invocations**:
- `import xatlas`
- `vmapping, indices, uvs = xatlas.parametrize(vertices, faces)`
- Used for mesh UV parametrization

---

### 14. xformers ⚠️ CRITICAL
**Status**: Download failed
**PyPI**: https://pypi.org/project/xformers/
**GitHub**: https://github.com/facebookresearch/xformers
**Download**: `pip install xformers==0.0.28.post3`
**System Requirements**: Requires CUDA toolkit

**Usage in Code**:
- Used in 4 attention module files
- `sam3d_objects/model/backbone/tdfy_dit/modules/attention/full_attn.py`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/full_attn.py`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/serialized_attn.py`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/windowed_attn.py`

**Invocations**:
- `import xformers.ops as xops`
- Memory-efficient attention operations

---

### 15. cuda-python
**Status**: Download failed
**PyPI**: https://pypi.org/project/cuda-python/
**NVIDIA**: https://developer.nvidia.com/cuda-python
**Download**: `pip install cuda-python==12.1.0`
**System Requirements**: CUDA Toolkit 12.1

**Usage in Code**:
- `torch.cuda` operations throughout the codebase (7+ occurrences)
- GPU memory management, device selection, random seeding

**Invocations**:
- `torch.cuda.manual_seed()`
- `torch.cuda.is_available()`
- `torch.cuda.get_device_name()`
- `torch.cuda.current_device()`

---

## Development/Testing Libraries (Not Used in Main Code)

These 72 libraries are not directly imported in the sam3d codebase and are likely:
- Transitive dependencies (required by other packages)
- Development tools (testing, linting, formatting)
- Optional features

**Full list available in**: `SAM3D-Library-Usage-Analysis.md`

## Installation Priority

### Tier 1 - Critical (Must Install)
1. **MoGe** - Core geometry utilities
2. **loguru** - Logging framework (used everywhere)
3. **open3d** - 3D geometry processing
4. **opencv-python** - Image processing
5. **optree** - Tree operations
6. **xformers** - Attention mechanisms
7. **lightning** - Training framework
8. **hydra-core** - Configuration management
9. **timm** - Vision transformer components

### Tier 2 - Important (Should Install)
10. **igraph** - Graph operations
11. **xatlas** - UV parametrization
12. **easydict** - Configuration dictionaries
13. **pymeshfix** - Mesh repair
14. **astor** - Source code manipulation
15. **cuda-python** - GPU operations

## Installation Commands

### Python 3.9+ Environment (Recommended)
```bash
# Create new environment
python3.9 -m venv sam3d-env
source sam3d-env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install critical dependencies in order
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install loguru==0.7.2
pip install hydra-core==1.3.2
pip install lightning==2.3.3
pip install opencv-python==4.9.0.80
pip install open3d==0.18.0
pip install optree==0.14.1
pip install timm==0.9.16
pip install xformers==0.0.28.post3 --index-url https://download.pytorch.org/whl/cu121
pip install igraph==0.11.8
pip install xatlas==0.0.9
pip install easydict==1.13
pip install astor==0.8.1
pip install pymeshfix==0.17.0
pip install git+https://github.com/microsoft/MoGe.git@a8c37341bc0325ca99b9d57981cc3bb2bd3e255b

# Install all remaining requirements
pip install -r requirements.txt
```

### System Dependencies (Amazon Linux 2)
```bash
sudo yum install -y gcc gcc-c++ make cmake \\
  mesa-libGL-devel mesa-libEGL-devel \\
  libX11-devel libXext-devel libXrender-devel \\
  ffmpeg ffmpeg-devel \\
  lapack-devel blas-devel
```

## Notes

1. **Python Version**: Upgrade to Python 3.9 or 3.10 (Python 3.7.16 is EOL)
2. **CUDA**: Install CUDA Toolkit 12.1 for GPU support
3. **Dependencies**: Install with dependencies enabled (remove `--no-deps` flag)
4. **Build Tools**: Some packages require C/C++ compilers
5. **Order Matters**: Install PyTorch first, then other packages
