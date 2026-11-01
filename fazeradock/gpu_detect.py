# Author: Yehor Franchuk (@MrEgorin) | FAZENA Project
"""GPU detection module for FazeraDock.

Detects NVIDIA, AMD, Apple Silicon, and Intel GPUs across Windows, Linux, and macOS,
and recommends the best docking engine.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Safe import for Windows registry
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None

_DISPLAY_CLASS_GUID = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


@dataclass
class GPUInfo:
    """Information about the available GPU hardware."""

    has_nvidia: bool = False
    has_amd: bool = False
    has_apple: bool = False
    gpu_name: str = "Unknown"
    cuda_available: bool = False
    opencl_available: bool = False


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _check_nvidia() -> tuple[bool, str, bool]:
    """Check for an NVIDIA GPU via nvidia-smi (Windows/Linux)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_name = parts[0].strip() if parts else "NVIDIA GPU"
            logger.info("NVIDIA GPU detected: %s", gpu_name)
            return True, gpu_name, True
    except FileNotFoundError:
        logger.debug("nvidia-smi not found on PATH")
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timed out")
    except OSError as exc:
        logger.debug("nvidia-smi check failed: %s", exc)

    return False, "", False


def _check_amd_windows() -> tuple[bool, str]:
    """Check for an AMD GPU via Windows registry."""
    if not winreg:
        return False, ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _DISPLAY_CLASS_GUID) as class_key:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(class_key, index)
                    index += 1
                except OSError:
                    break

                try:
                    with winreg.OpenKey(class_key, subkey_name) as dev_key:
                        driver_desc, _ = winreg.QueryValueEx(dev_key, "DriverDesc")
                        desc_upper = str(driver_desc).upper()
                        if "AMD" in desc_upper or "RADEON" in desc_upper or "ATI" in desc_upper:
                            logger.info("AMD GPU detected: %s", driver_desc)
                            return True, str(driver_desc)
                except OSError:
                    continue
    except OSError as exc:
        logger.debug("AMD registry check failed: %s", exc)

    return False, ""


def _check_unix_gpu() -> tuple[bool, bool, str]:
    """Check for GPUs on Linux via lspci / rocm-smi or macOS via system_profiler."""
    has_amd = False
    has_apple = False
    name = ""

    if sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            out = res.stdout
            if "Chipset Model: Apple" in out or "Apple M" in out:
                has_apple = True
                name = "Apple Silicon GPU"
            elif "AMD" in out or "Radeon" in out:
                has_amd = True
                name = "AMD GPU (macOS)"
            elif "Intel" in out:
                name = "Intel Integrated Graphics"
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        # Check lspci
        try:
            res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            for line in res.stdout.splitlines():
                if "VGA" in line or "3D" in line or "Display" in line:
                    line_upper = line.upper()
                    if "AMD" in line_upper or "RADEON" in line_upper:
                        has_amd = True
                        name = line.split(":", 2)[-1].strip()
                        break
                    elif "INTEL" in line_upper:
                        name = line.split(":", 2)[-1].strip()
        except Exception:
            pass

    return has_amd, has_apple, name


def _check_opencl() -> bool:
    """Attempt to detect OpenCL availability via pyopencl."""
    try:
        import pyopencl  # type: ignore[import-untyped]
        platforms = pyopencl.get_platforms()
        return len(platforms) > 0
    except Exception:
        return False


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def detect_gpu() -> GPUInfo:
    """Detect available GPU hardware across Windows, Linux, and macOS."""
    info = GPUInfo()

    # 1. NVIDIA (all platforms)
    has_nv, nv_name, cuda = _check_nvidia()
    if has_nv:
        info.has_nvidia = True
        info.gpu_name = nv_name
        info.cuda_available = cuda
        info.opencl_available = _check_opencl()
        return info

    # 2. AMD / Other on Windows
    if sys.platform == "win32":
        has_amd, amd_name = _check_amd_windows()
        if has_amd:
            info.has_amd = True
            info.gpu_name = amd_name

    # 3. Unix (Linux / macOS)
    else:
        has_amd, has_apple, unix_name = _check_unix_gpu()
        info.has_amd = has_amd
        info.has_apple = has_apple
        if unix_name:
            info.gpu_name = unix_name

    if info.gpu_name == "Unknown":
        info.gpu_name = "CPU Only (No discrete GPU detected)"

    info.opencl_available = _check_opencl()
    return info


def get_recommended_engine(info: Optional[GPUInfo] = None) -> str:
    """Return the recommended docking engine name."""
    if info is None:
        info = detect_gpu()
    if info.cuda_available:
        return "vina-gpu"
    return "vina"


def print_gpu_info() -> None:
    """Print a human-readable summary of detected GPU hardware."""
    info = detect_gpu()
    print("=" * 45)
    print("  FazeraDock Hardware Detection")
    print("=" * 45)
    print(f"  OS Platform       : {sys.platform}")
    print(f"  GPU Name          : {info.gpu_name}")
    print(f"  NVIDIA GPU        : {'Yes' if info.has_nvidia else 'No'}")
    print(f"  AMD GPU           : {'Yes' if info.has_amd else 'No'}")
    print(f"  CUDA Available    : {'Yes' if info.cuda_available else 'No'}")
    print(f"  OpenCL Available  : {'Yes' if info.opencl_available else 'No'}")
    print(f"  Recommended Engine: {get_recommended_engine(info)}")
    print("=" * 45)
