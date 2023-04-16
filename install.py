import platform
import sys
from pathlib import Path
from textwrap import dedent

from packaging import version

from launch import (
    extensions_dir,
    is_installed,
    python,
    run,
    run_pip,
    skip_install,
)

pycocotools = {
    "Windows": {
        (3, 8): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp38-cp38-win_amd64.whl",
        (3, 9): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp39-cp39-win_amd64.whl",
        (3, 10): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp310-cp310-win_amd64.whl",
        (3, 11): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp311-cp311-win_amd64.whl",
    },
    "Linux": {
        (3, 8): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        (3, 9): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        (3, 10): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        (3, 11): "https://github.com/Bing-su/dddetailer/releases/download/pycocotools/pycocotools-2.0.6-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    },
}


def check_ddetailer() -> bool:
    original = Path(extensions_dir, "ddetailer")
    return not original.exists()


def check_install() -> bool:
    try:
        import mmcv
        import mmdet
        from mmdet.evaluation import get_classes
    except Exception:
        return False

    if not hasattr(mmcv, "__version__") or not hasattr(mmdet, "__version__"):
        return False

    v1 = version.parse(mmcv.__version__) >= version.parse("2.0.0")
    v2 = version.parse(mmdet.__version__) >= version.parse("3.0.0")
    return v1 and v2


def install_pycocotools():
    system = platform.system()
    machine = platform.machine()

    if system not in ["Windows", "Linux"] or machine not in ["AMD64", "x86_64"]:
        print("Installing pycocotools from pypi...")
        run(f'"{python}" -m pip install pycocotools', live=True)
        return

    links = pycocotools[system]
    version = sys.version_info[:2]
    if version not in links:
        print("Installing pycocotools from pypi...")
        run(f'"{python}" -m pip install pycocotools', live=True)
        return

    url = links[version]
    print("Installing pycocotools...")
    run(f'"{python}" -m pip install {url}', live=True)


def install():
    if not is_installed("pycocotools"):
        install_pycocotools()

    if not is_installed("mim"):
        run_pip("install openmim", desc="openmim")

    if not check_install():
        print("Uninstalling mmcv mmdet... (if installed)")
        run(f'"{python}" -m pip uninstall -y mmcv mmcv-full mmdet mmengine', live=True)
        print("Installing mmcv mmdet...")
        run(f'"{python}" -m mim install -U mmcv>=2.0.0 mmdet>=3.0.0', live=True)


if not check_ddetailer():
    message = """
    [-] dddetailer: Please remove the following:
          1. the original ddetailer extension - "stable-diffusion-webui/extensions/ddetailer" folder.
          2. original model files - "stable-diffusion-webui/models/mmdet" folder.
    """
    message = dedent(message)
    raise RuntimeError(message)

if not skip_install:
    install()
