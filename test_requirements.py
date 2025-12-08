#!/usr/bin/env python3
"""
Test script to systematically verify all sam-3d-objects requirements
"""
import subprocess
import json
import sys
import importlib
from datetime import datetime

# Complete list of requirements from sam-3d-objects
REQUIREMENTS = [
    "astor==0.8.1",
    "async-timeout==4.0.3",
    "auto_gptq==0.7.1",
    "autoflake==2.3.1",
    "av==12.0.0",
    "bitsandbytes==0.43.0",
    "black==24.3.0",
    "bpy==4.3.0",
    "colorama==0.4.6",
    "conda-pack==0.7.1",
    "crcmod==1.7",
    "cuda-python==12.1.0",
    "dataclasses==0.6",
    "decord==0.6.0",
    "deprecation==2.1.0",
    "easydict==1.13",
    "einops-exts==0.0.4",
    "exceptiongroup==1.2.0",
    "fastavro==1.9.4",
    "fasteners==0.19",
    "flake8==7.0.0",
    "Flask==3.0.3",
    "fqdn==1.5.1",
    "ftfy==6.2.0",
    "fvcore==0.1.5.post20221221",
    "gdown==5.2.0",
    "h5py==3.12.1",
    "hdfs==2.7.3",
    "httplib2==0.22.0",
    "hydra-core==1.3.2",
    "hydra-submitit-launcher==1.2.0",
    "igraph==0.11.8",
    "imath==0.0.2",
    "isoduration==20.11.0",
    "jsonlines==4.0.0",
    "jsonpickle==3.0.4",
    "jsonpointer==2.4",
    "jupyter==1.1.1",
    "librosa==0.10.1",
    "lightning==2.3.3",
    "loguru==0.7.2",
    "mosaicml-streaming==0.7.5",
    "nvidia-cuda-nvcc-cu12==12.1.105",
    "nvidia-pyindex==1.0.9",
    "objsize==0.7.0",
    "open3d==0.18.0",
    "opencv-python==4.9.0.80",
    "OpenEXR==3.3.3",
    "optimum==1.18.1",
    "optree==0.14.1",
    "orjson==3.10.0",
    "panda3d-gltf==1.2.1",
    "pdoc3==0.10.0",
    "peft==0.10.0",
    "pip-system-certs==4.0",
    "point-cloud-utils==0.29.5",
    "polyscope==2.3.0",
    "pycocotools==2.0.7",
    "pydot==1.4.2",
    "pymeshfix==0.17.0",
    "pymongo==4.6.3",
    "pyrender==0.1.45",
    "PySocks==1.7.1",
    "pytest==8.1.1",
    "python-pycg==0.9.2",
    "randomname==0.2.1",
    "roma==1.5.1",
    "rootutils==1.0.7",
    "Rtree==1.3.0",
    "sagemaker==2.242.0",
    "scikit-image==0.23.1",
    "sentence-transformers==2.6.1",
    "simplejson==3.19.2",
    "smplx==0.1.28",
    "spconv-cu121==2.3.8",
    "tensorboard==2.16.2",
    "timm==0.9.16",
    "tomli==2.0.1",
    "torchaudio==2.5.1+cu121",
    "uri-template==1.3.0",
    "usort==1.0.8.post1",
    "wandb==0.20.0",
    "webcolors==1.13",
    "webdataset==0.2.86",
    "Werkzeug==3.0.6",
    "xatlas==0.0.9",
    "xformers==0.0.28.post3",
    "git+https://github.com/microsoft/MoGe.git@a8c37341bc0325ca99b9d57981cc3bb2bd3e255b#egg=MoGe"
]

def get_package_name(requirement):
    """Extract package name from requirement string"""
    if requirement.startswith("git+"):
        # Extract package name from git URL
        return requirement.split("#egg=")[1] if "#egg=" in requirement else "MoGe"
    return requirement.split("==")[0].split("[")[0]

def test_download(requirement):
    """Test if package can be downloaded"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps", requirement],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_install(requirement):
    """Test if package can be installed"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", requirement],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_import(package_name):
    """Test if package can be imported"""
    # Map common package name variations
    import_map = {
        "opencv-python": "cv2",
        "scikit-image": "skimage",
        "OpenEXR": "OpenEXR",
        "python-pycg": "pycg",
        "sentence-transformers": "sentence_transformers",
        "mosaicml-streaming": "streaming",
        "hydra-core": "hydra",
        "point-cloud-utils": "point_cloud_utils",
        "pip-system-certs": "pip_system_certs",
    }

    import_name = import_map.get(package_name, package_name.replace("-", "_"))

    try:
        mod = importlib.import_module(import_name)
        # Try to get version
        version = getattr(mod, "__version__", "unknown")
        return True, version, ""
    except Exception as e:
        return False, None, str(e)

def run_tests():
    """Run all tests and collect results"""
    results = []
    total = len(REQUIREMENTS)

    print(f"Testing {total} requirements...\n")

    for idx, requirement in enumerate(REQUIREMENTS, 1):
        package_name = get_package_name(requirement)
        print(f"[{idx}/{total}] Testing {package_name}...", end=" ")

        result = {
            "requirement": requirement,
            "package_name": package_name,
            "download_success": False,
            "download_output": "",
            "download_error": "",
            "install_success": False,
            "install_output": "",
            "install_error": "",
            "import_success": False,
            "import_version": None,
            "import_error": ""
        }

        # Test download
        success, stdout, stderr = test_download(requirement)
        result["download_success"] = success
        result["download_output"] = stdout[:500] if stdout else ""
        result["download_error"] = stderr[:500] if stderr else ""

        if success:
            print("✓ download", end=" ")
        else:
            print("✗ download", end=" ")

        # Test install (only if download succeeded)
        if success:
            success, stdout, stderr = test_install(requirement)
            result["install_success"] = success
            result["install_output"] = stdout[:500] if stdout else ""
            result["install_error"] = stderr[:500] if stderr else ""

            if success:
                print("✓ install", end=" ")
            else:
                print("✗ install", end=" ")

            # Test import (only if install succeeded)
            if success:
                success, version, error = test_import(package_name)
                result["import_success"] = success
                result["import_version"] = version
                result["import_error"] = error[:500] if error else ""

                if success:
                    print(f"✓ import (v{version})")
                else:
                    print("✗ import")
            else:
                print()
        else:
            print()

        results.append(result)

    return results

def generate_report(results):
    """Generate markdown report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# SAM 3D Objects Requirements Installation Test Report

**Generated**: {timestamp}
**Python Version**: {sys.version}
**Total Packages Tested**: {len(results)}

## Executive Summary

"""

    # Calculate statistics
    download_success = sum(1 for r in results if r["download_success"])
    install_success = sum(1 for r in results if r["install_success"])
    import_success = sum(1 for r in results if r["import_success"])

    report += f"- **Download Success**: {download_success}/{len(results)} ({download_success*100//len(results)}%)\n"
    report += f"- **Install Success**: {install_success}/{len(results)} ({install_success*100//len(results)}%)\n"
    report += f"- **Import Success**: {import_success}/{len(results)} ({import_success*100//len(results)}%)\n\n"

    # Detailed results
    report += "## Detailed Test Results\n\n"
    report += "| # | Package | Version | Download | Install | Import | Notes |\n"
    report += "|---|---------|---------|----------|---------|--------|-------|\n"

    for idx, r in enumerate(results, 1):
        download_icon = "✅" if r["download_success"] else "❌"
        install_icon = "✅" if r["install_success"] else "❌"
        import_icon = "✅" if r["import_success"] else "❌"
        version = r["import_version"] if r["import_version"] else "N/A"

        # Extract version from requirement
        req_version = r["requirement"].split("==")[1] if "==" in r["requirement"] else "latest"

        notes = ""
        if not r["download_success"]:
            notes = "Download failed"
        elif not r["install_success"]:
            notes = "Install failed"
        elif not r["import_success"]:
            notes = f"Import failed: {r['import_error'][:50]}"

        report += f"| {idx} | {r['package_name']} | {req_version} | {download_icon} | {install_icon} | {import_icon} | {notes} |\n"

    # Failed packages section
    failed = [r for r in results if not r["import_success"]]
    if failed:
        report += f"\n## Failed Packages ({len(failed)})\n\n"
        for r in failed:
            report += f"### {r['package_name']}\n\n"
            report += f"**Requirement**: `{r['requirement']}`\n\n"

            if not r["download_success"]:
                report += "**Download Error**:\n```\n"
                report += r["download_error"][:1000]
                report += "\n```\n\n"
            elif not r["install_success"]:
                report += "**Install Error**:\n```\n"
                report += r["install_error"][:1000]
                report += "\n```\n\n"
            else:
                report += "**Import Error**:\n```\n"
                report += r["import_error"][:1000]
                report += "\n```\n\n"

    return report

def generate_missing_list(results):
    """Generate short list of missing packages"""
    failed = [r for r in results if not r["import_success"]]

    content = f"""# Missing/Failed Libraries

**Total**: {len(failed)} packages failed to install or import successfully

## List

"""
    for r in failed:
        content += f"- {r['package_name']} ({r['requirement']})\n"

    return content

if __name__ == "__main__":
    print("=" * 60)
    print("SAM 3D Objects Requirements Test")
    print("=" * 60)
    print()

    # Run tests
    results = run_tests()

    # Save results to JSON
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to test_results.json")

    # Generate reports
    report = generate_report(results)
    with open("installation_report.md", "w") as f:
        f.write(report)
    print(f"✓ Full report saved to installation_report.md")

    missing_list = generate_missing_list(results)
    with open("missing_libraries.md", "w") as f:
        f.write(missing_list)
    print(f"✓ Missing libraries list saved to missing_libraries.md")

    print("\nDone!")
