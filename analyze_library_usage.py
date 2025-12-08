#!/usr/bin/env python3
"""
Analyze sam3d codebase to find where missing libraries are used
"""
import os
import re
from collections import defaultdict

# List of failed libraries from test
FAILED_LIBRARIES = [
    "auto_gptq", "autoflake", "av", "bitsandbytes", "black", "bpy",
    "cuda-python", "fastavro", "flake8", "Flask", "ftfy", "gdown",
    "h5py", "igraph", "imath", "jsonlines", "lightning", "mosaicml-streaming",
    "nvidia-cuda-nvcc-cu12", "open3d", "opencv-python", "optree", "orjson",
    "panda3d-gltf", "peft", "point-cloud-utils", "polyscope", "pymeshfix",
    "pyrender", "pytest", "python-pycg", "randomname", "Rtree", "sagemaker",
    "scikit-image", "sentence-transformers", "simplejson", "spconv-cu121",
    "tensorboard", "timm", "torchaudio", "usort", "wandb", "webcolors",
    "webdataset", "Werkzeug", "xatlas", "xformers", "MoGe",
    "pymongo", "smplx", "tomli", "uri-template",
    "astor", "async-timeout", "colorama", "conda-pack", "crcmod", "decord",
    "deprecation", "easydict", "einops-exts", "exceptiongroup", "fasteners",
    "fqdn", "fvcore", "hdfs", "httplib2", "hydra-core", "hydra-submitit-launcher",
    "isoduration", "jsonpickle", "jsonpointer", "jupyter", "librosa", "loguru",
    "nvidia-pyindex", "objsize", "OpenEXR", "optimum", "pdoc3", "pip-system-certs",
    "pycocotools", "pydot", "PySocks", "roma", "rootutils"
]

# Map package names to common import names
IMPORT_MAP = {
    "opencv-python": "cv2",
    "scikit-image": "skimage",
    "OpenEXR": "OpenEXR",
    "python-pycg": "pycg",
    "sentence-transformers": "sentence_transformers",
    "mosaicml-streaming": "streaming",
    "hydra-core": "hydra",
    "point-cloud-utils": "point_cloud_utils",
    "pip-system-certs": "pip_system_certs",
    "open3d": "o3d",
    "cuda-python": "cuda",
    "einops-exts": "einops_exts",
    "async-timeout": "async_timeout",
    "uri-template": "uri_template",
}

def get_import_name(package):
    """Convert package name to likely import name"""
    if package in IMPORT_MAP:
        return IMPORT_MAP[package]
    return package.replace("-", "_").lower()

def search_library_usage(source_dir):
    """Search for library usage in Python files"""
    results = defaultdict(lambda: {"imports": [], "usage": []})

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, source_dir)

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        lines = content.split("\n")

                        for line_num, line in enumerate(lines, 1):
                            # Check each failed library
                            for lib in FAILED_LIBRARIES:
                                import_name = get_import_name(lib)

                                # Check for import statements
                                if re.search(rf"^import\s+{import_name}|^from\s+{import_name}", line.strip()):
                                    results[lib]["imports"].append({
                                        "file": relpath,
                                        "line": line_num,
                                        "code": line.strip()
                                    })

                                # Check for usage (more complex)
                                elif re.search(rf"\b{import_name}\.", line):
                                    results[lib]["usage"].append({
                                        "file": relpath,
                                        "line": line_num,
                                        "code": line.strip()
                                    })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

    return results

def generate_report(results):
    """Generate markdown report"""
    report = "# SAM 3D Objects - Missing Library Usage Analysis\n\n"
    report += "This document shows where each failed/missing library is used in the sam3d codebase.\n\n"

    # Count libraries found
    found_libs = {lib: data for lib, data in results.items() if data["imports"] or data["usage"]}
    report += f"## Summary\n\n"
    report += f"- **Total Failed Libraries**: {len(FAILED_LIBRARIES)}\n"
    report += f"- **Libraries Found in Code**: {len(found_libs)}\n"
    report += f"- **Libraries Not Found**: {len(FAILED_LIBRARIES) - len(found_libs)}\n\n"

    # Libraries found in code
    if found_libs:
        report += "## Libraries Found in Codebase\n\n"
        for lib in sorted(found_libs.keys()):
            data = found_libs[lib]
            report += f"### {lib}\n\n"

            if data["imports"]:
                report += f"**Import Statements** ({len(data['imports'])}):\n\n"
                for imp in data["imports"]:
                    report += f"- `{imp['file']}:{imp['line']}` - `{imp['code']}`\n"
                report += "\n"

            if data["usage"]:
                report += f"**Usage Examples** ({len(data['usage'])} occurrences):\n\n"
                # Show first 5 usages
                for usage in data["usage"][:5]:
                    report += f"- `{usage['file']}:{usage['line']}` - `{usage['code']}`\n"
                if len(data["usage"]) > 5:
                    report += f"- ... and {len(data['usage']) - 5} more occurrences\n"
                report += "\n"

    # Libraries not found
    not_found = [lib for lib in FAILED_LIBRARIES if lib not in found_libs]
    if not_found:
        report += "## Libraries Not Found in Codebase\n\n"
        report += "These libraries are listed in requirements but not directly imported:\n\n"
        for lib in sorted(not_found):
            report += f"- {lib}\n"
        report += "\n"
        report += "*Note: These may be transitive dependencies or development tools.*\n\n"

    return report

if __name__ == "__main__":
    source_dir = "./sam3d-source"
    print("Analyzing library usage in sam3d codebase...")
    results = search_library_usage(source_dir)

    report = generate_report(results)

    with open("docs/SAM3D-Library-Usage-Analysis.md", "w") as f:
        f.write(report)

    print(f"✓ Report saved to docs/SAM3D-Library-Usage-Analysis.md")
