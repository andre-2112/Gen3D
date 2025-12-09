# Missing/Failed Libraries for SAM 3D Objects

**Total**: 87 out of 88 packages failed to install or import successfully on Python 3.7.16

**Only 1 package succeeded**: dataclasses==0.6

## Complete List of Failed Packages

### Download Failures (45 packages)
These packages could not be downloaded, likely due to Python version incompatibility or missing platform wheels:

1. auto_gptq==0.7.1
2. autoflake==2.3.1
3. av==12.0.0
4. bitsandbytes==0.43.0
5. black==24.3.0
6. bpy==4.3.0
7. cuda-python==12.1.0
8. fastavro==1.9.4
9. flake8==7.0.0
10. Flask==3.0.3
11. ftfy==6.2.0
12. gdown==5.2.0
13. h5py==3.12.1
14. igraph==0.11.8
15. imath==0.0.2
16. jsonlines==4.0.0
17. lightning==2.3.3
18. mosaicml-streaming==0.7.5
19. nvidia-cuda-nvcc-cu12==12.1.105
20. open3d==0.18.0
21. opencv-python==4.9.0.80
22. optree==0.14.1
23. orjson==3.10.0
24. panda3d-gltf==1.2.1
25. peft==0.10.0
26. point-cloud-utils==0.29.5
27. polyscope==2.3.0
28. pymeshfix==0.17.0
29. pyrender==0.1.45
30. pytest==8.1.1
31. python-pycg==0.9.2
32. randomname==0.2.1
33. Rtree==1.3.0
34. sagemaker==2.242.0
35. scikit-image==0.23.1
36. sentence-transformers==2.6.1
37. simplejson==3.19.2
38. spconv-cu121==2.3.8
39. tensorboard==2.16.2
40. timm==0.9.16
41. torchaudio==2.5.1+cu121
42. usort==1.0.8.post1
43. wandb==0.20.0
44. webcolors==1.13
45. webdataset==0.2.86
46. Werkzeug==3.0.6
47. xatlas==0.0.9
48. xformers==0.0.28.post3
49. MoGe (git+https://github.com/microsoft/MoGe.git)

### Install Failures (4 packages)
These packages downloaded successfully but failed to install:

50. pymongo==4.6.3
51. smplx==0.1.28
52. tomli==2.0.1
53. uri-template==1.3.0

### Import Failures (36 packages)
These packages installed successfully but failed to import (likely due to missing dependencies):

54. astor==0.8.1
55. async-timeout==4.0.3
56. colorama==0.4.6
57. conda-pack==0.7.1
58. crcmod==1.7
59. decord==0.6.0
60. deprecation==2.1.0
61. easydict==1.13
62. einops-exts==0.0.4
63. exceptiongroup==1.2.0
64. fasteners==0.19
65. fqdn==1.5.1
66. fvcore==0.1.5.post20221221
67. hdfs==2.7.3
68. httplib2==0.22.0
69. hydra-core==1.3.2
70. hydra-submitit-launcher==1.2.0
71. isoduration==20.11.0
72. jsonpickle==3.0.4
73. jsonpointer==2.4
74. jupyter==1.1.1
75. librosa==0.10.1
76. loguru==0.7.2
77. nvidia-pyindex==1.0.9
78. objsize==0.7.0
79. OpenEXR==3.3.3
80. optimum==1.18.1
81. pdoc3==0.10.0
82. pip-system-certs==4.0
83. pycocotools==2.0.7
84. pydot==1.4.2
85. PySocks==1.7.1
86. roma==1.5.1
87. rootutils==1.0.7

## Critical Issues

### 1. Python Version Incompatibility
Current environment: **Python 3.7.16** (EOL: June 2023)
Most modern packages require Python 3.8 or higher.

### 2. Missing System Dependencies
Many packages require system libraries that are not installed.

### 3. CUDA/GPU Dependencies
GPU-related packages require CUDA toolkit and drivers.

### 4. Missing Package Dependencies
Import failures indicate missing dependent packages (tested with `--no-deps` flag).

## Recommended Action
**Upgrade to Python 3.9 or 3.10** and install all packages with their dependencies enabled.
