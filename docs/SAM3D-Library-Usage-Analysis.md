# SAM 3D Objects - Missing Library Usage Analysis

This document shows where each failed/missing library is used in the sam3d codebase.

## Summary

- **Total Failed Libraries**: 87
- **Libraries Found in Code**: 15
- **Libraries Not Found**: 72

## Libraries Found in Codebase

### MoGe

**Import Statements** (3):

- `sam3d_objects/pipeline/utils/pointmap.py:11` - `from moge.utils.geometry_torch import (`
- `sam3d_objects/pipeline/utils/pointmap.py:15` - `from moge.utils.geometry_numpy import (`
- `notebook/mesh_alignment.py:17` - `from moge.model.v1 import MoGeModel`

### astor

**Import Statements** (1):

- `sam3d_objects/data/utils.py:8` - `import astor`

**Usage Examples** (1 occurrences):

- `sam3d_objects/data/utils.py:218` - `label = astor.to_source(args[argnum]).strip()`

### cuda-python

**Usage Examples** (7 occurrences):

- `sam3d_objects/pipeline/layout_post_optimization_utils.py:295` - `torch.cuda.manual_seed(seed)`
- `sam3d_objects/pipeline/layout_post_optimization_utils.py:296` - `torch.cuda.manual_seed_all(seed)`
- `sam3d_objects/pipeline/inference_pipeline.py:12` - `if torch.cuda.is_available():`
- `sam3d_objects/pipeline/inference_pipeline.py:13` - `gpu_name = torch.cuda.get_device_name(0)`
- `sam3d_objects/pipeline/inference_pipeline.py:100` - `logger.info(f"Actually using GPU: {torch.cuda.current_device()}")`
- ... and 2 more occurrences

### easydict

**Import Statements** (4):

- `sam3d_objects/model/backbone/tdfy_dit/representations/mesh/cube2mesh.py:4` - `from easydict import EasyDict as edict`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/gaussian_render.py:15` - `from easydict import EasyDict as edict`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/gaussian_render.py:20` - `from easydict import EasyDict as edict`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:8` - `from easydict import EasyDict as edict`

### hydra-core

**Import Statements** (3):

- `sam3d_objects/pipeline/inference_pipeline.py:24` - `from hydra.utils import instantiate`
- `sam3d_objects/config/utils.py:6` - `from hydra.utils import instantiate`
- `notebook/inference.py:13` - `from hydra.utils import instantiate, get_method`

### igraph

**Import Statements** (1):

- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:13` - `import igraph`

**Usage Examples** (1 occurrences):

- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:139` - `g = igraph.Graph()`

### lightning

**Import Statements** (2):

- `sam3d_objects/model/io.py:3` - `import lightning.pytorch as pl`
- `sam3d_objects/model/io.py:9` - `from lightning.pytorch.utilities.consolidate_checkpoint import (`

### loguru

**Import Statements** (19):

- `sam3d_objects/pipeline/inference_pipeline_pointmap.py:8` - `from loguru import logger`
- `sam3d_objects/pipeline/inference_pipeline.py:6` - `from loguru import logger`
- `sam3d_objects/pipeline/inference_utils.py:10` - `from loguru import logger`
- `sam3d_objects/pipeline/inference_utils.py:332` - `from loguru import logger`
- `sam3d_objects/model/io.py:8` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:20` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/models/sparse_structure_vae.py:12` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/models/structured_latent_vae/decoder_mesh.py:14` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/models/structured_latent_vae/encoder.py:9` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/models/structured_latent_vae/decoder_gs.py:12` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/modules/attention/__init__.py:3` - `from loguru import logger`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/__init__.py:3` - `from loguru import logger`
- `sam3d_objects/model/backbone/generator/classifier_free_guidance.py:8` - `from loguru import logger`
- `sam3d_objects/model/backbone/dit/embedder/embedder_fuser.py:4` - `from loguru import logger`
- `sam3d_objects/model/backbone/dit/embedder/pointmap.py:7` - `from loguru import logger`
- `sam3d_objects/model/backbone/dit/embedder/dino.py:7` - `from loguru import logger`
- `sam3d_objects/data/dataset/tdfy/img_and_mask_transforms.py:12` - `from loguru import logger`
- `sam3d_objects/data/dataset/tdfy/pose_target.py:5` - `from loguru import logger`
- `sam3d_objects/data/dataset/tdfy/preprocessor.py:4` - `from loguru import logger`

### open3d

**Usage Examples** (13 occurrences):

- `sam3d_objects/pipeline/layout_post_optimization_utils.py:305` - `mesh_o3d = o3d.geometry.TriangleMesh()`
- `sam3d_objects/pipeline/layout_post_optimization_utils.py:306` - `mesh_o3d.vertices = o3d.utility.Vector3dVector(vertices)`
- `sam3d_objects/pipeline/layout_post_optimization_utils.py:307` - `mesh_o3d.triangles = o3d.utility.Vector3iVector(faces)`
- `sam3d_objects/pipeline/layout_post_optimization_utils.py:373` - `pcd = o3d.geometry.PointCloud()`
- `sam3d_objects/pipeline/layout_post_optimization_utils.py:374` - `pcd.points = o3d.utility.Vector3dVector(tensor.cpu().numpy())`
- ... and 8 more occurrences

### opencv-python

**Import Statements** (4):

- `sam3d_objects/pipeline/layout_post_optimization_utils.py:6` - `import cv2`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:6` - `import cv2`
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:14` - `import cv2`
- `sam3d_objects/data/dataset/tdfy/img_and_mask_transforms.py:859` - `import cv2`

**Usage Examples** (9 occurrences):

- `sam3d_objects/pipeline/layout_post_optimization_utils.py:337` - `# cv2.imwrite(path, mask_uint8)`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:259` - `text_bbox = cv2.getTextSize("Unsupported", cv2.FONT_HERSHEY_SIMPLEX, 2, 3)[`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:263` - `image = cv2.putText(`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:267` - `cv2.FONT_HERSHEY_SIMPLEX,`
- `sam3d_objects/model/backbone/tdfy_dit/renderers/octree_renderer.py:271` - `cv2.LINE_AA,`
- ... and 4 more occurrences

### optree

**Import Statements** (4):

- `sam3d_objects/model/backbone/generator/shortcut/model.py:7` - `import optree`
- `sam3d_objects/model/backbone/generator/flow_matching/solver.py:2` - `import optree`
- `sam3d_objects/model/backbone/generator/flow_matching/model.py:6` - `import optree`
- `sam3d_objects/data/utils.py:3` - `import optree`

**Usage Examples** (20 occurrences):

- `sam3d_objects/model/backbone/generator/shortcut/model.py:60` - `first_tensor = optree.tree_flatten(x1)[0][0]`
- `sam3d_objects/model/backbone/generator/shortcut/model.py:257` - `first_tensor = optree.tree_flatten(x1)[0][0]`
- `sam3d_objects/model/backbone/generator/shortcut/model.py:339` - `flow_matching_loss = optree.tree_broadcast_map(`
- `sam3d_objects/model/backbone/generator/shortcut/model.py:346` - `flow_matching_loss_val = sum(optree.tree_flatten(flow_matching_loss)[0])`
- `sam3d_objects/model/backbone/generator/shortcut/model.py:376` - `self_consistency_loss = optree.tree_broadcast_map(`
- ... and 15 more occurrences

### pymeshfix

**Import Statements** (1):

- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:12` - `from pymeshfix import _meshfix`

### timm

**Import Statements** (1):

- `sam3d_objects/model/backbone/dit/embedder/pointmap.py:2` - `from timm.models.vision_transformer import Block`

### xatlas

**Import Statements** (1):

- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:10` - `import xatlas`

**Usage Examples** (2 occurrences):

- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:348` - `Parametrize a mesh to a texture space, using xatlas.`
- `sam3d_objects/model/backbone/tdfy_dit/utils/postprocessing_utils.py:355` - `vmapping, indices, uvs = xatlas.parametrize(vertices, faces)`

### xformers

**Import Statements** (4):

- `sam3d_objects/model/backbone/tdfy_dit/modules/attention/full_attn.py:8` - `import xformers.ops as xops`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/full_attn.py:8` - `import xformers.ops as xops`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/serialized_attn.py:10` - `import xformers.ops as xops`
- `sam3d_objects/model/backbone/tdfy_dit/modules/sparse/attention/windowed_attn.py:9` - `import xformers.ops as xops`

## Libraries Not Found in Codebase

These libraries are listed in requirements but not directly imported:

- Flask
- OpenEXR
- PySocks
- Rtree
- Werkzeug
- async-timeout
- auto_gptq
- autoflake
- av
- bitsandbytes
- black
- bpy
- colorama
- conda-pack
- crcmod
- decord
- deprecation
- einops-exts
- exceptiongroup
- fastavro
- fasteners
- flake8
- fqdn
- ftfy
- fvcore
- gdown
- h5py
- hdfs
- httplib2
- hydra-submitit-launcher
- imath
- isoduration
- jsonlines
- jsonpickle
- jsonpointer
- jupyter
- librosa
- mosaicml-streaming
- nvidia-cuda-nvcc-cu12
- nvidia-pyindex
- objsize
- optimum
- orjson
- panda3d-gltf
- pdoc3
- peft
- pip-system-certs
- point-cloud-utils
- polyscope
- pycocotools
- pydot
- pymongo
- pyrender
- pytest
- python-pycg
- randomname
- roma
- rootutils
- sagemaker
- scikit-image
- sentence-transformers
- simplejson
- smplx
- spconv-cu121
- tensorboard
- tomli
- torchaudio
- uri-template
- usort
- wandb
- webcolors
- webdataset

*Note: These may be transitive dependencies or development tools.*

