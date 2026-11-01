"""GPU detection module for FazeraDock.

Detects NVIDIA and AMD GPUs and recommends the best docking engine.
"""

from __future__ import annotations

import logging
import subprocess
import winreg
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Windows registry path for display adapters
_DISPLAY_CLASS_GUID = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


@dataclass
class GPUInfo:
    """Information about the available GPU hardware."""

    has_nvidia: bool = False
    has_amd: bool = False
    gpu_name: str = "Unknown"
    cuda_available: bool = False
    opencl_available: bool = False


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _check_nvidia() -> tuple[bool, str, bool]:
    """Check for an NVIDIA GPU via ``nvidia-smi``.

    Returns
    -------
    tuple[bool, str, bool]
        (has_nvidia, gpu_name, cuda_available)
    """
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


def _check_amd_registry() -> tuple[bool, str]:
    """Check for an AMD GPU via the Windows registry.

    Returns
    -------
    tuple[bool, str]
        (has_amd, gpu_name)
    """
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


def _check_opencl() -> bool:
    """Attempt to detect OpenCL availability via pyopencl (best-effort)."""
    try:
        import pyopencl  # type: ignore[import-untyped]
        platforms = pyopencl.get_platforms()
        return len(platforms) > 0
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def detect_gpu() -> GPUInfo:
    """Detect available GPUs and return a :class:`GPUInfo` instance."""
    info = GPUInfo()

    # NVIDIA check
    has_nvidia, nvidia_name, cuda = _check_nvidia()
    info.has_nvidia = has_nvidia
    info.cuda_available = cuda
    if has_nvidia:
        info.gpu_name = nvidia_name

    # AMD check
    has_amd, amd_name = _check_amd_registry()
    info.has_amd = has_amd
    if has_amd and not has_nvidia:
        info.gpu_name = amd_name
    elif has_amd and has_nvidia:
        info.gpu_name = f"{nvidia_name} / {amd_name}"

    # OpenCL check
    info.opencl_available = _check_opencl()

    if not has_nvidia and not has_amd:
        info.gpu_name = "No dedicated GPU detected"

    return info


def get_recommended_engine() -> str:
    """Return the recommended docking engine identifier.

    Returns ``"vina-gpu"`` when an NVIDIA GPU with CUDA is available,
    otherwise returns ``"vina"`` (CPU-based).
    """
    info = detect_gpu()
    if info.has_nvidia and info.cuda_available:
        return "vina-gpu"
    return "vina"


def print_gpu_info() -> None:
    """Pretty-print GPU detection results to *stdout*."""
    info = detect_gpu()

    print("=" * 50)
    print("  FazeraDock — GPU Detection Report")
    print("=" * 50)
    print(f"  GPU Name        : {info.gpu_name}")
    print(f"  NVIDIA Present  : {'Yes' if info.has_nvidia else 'No'}")
    print(f"  AMD Present     : {'Yes' if info.has_amd else 'No'}")
    print(f"  CUDA Available  : {'Yes' if info.cuda_available else 'No'}")
    print(f"  OpenCL Available: {'Yes' if info.opencl_available else 'No'}")
    print("-" * 50)
    engine = get_recommended_engine()
    print(f"  Recommended Engine: {engine}")
    print("=" * 50)
