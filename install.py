import platform
import sys

from packaging import version

from launch import is_installed, run, run_pip

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
python = sys.executable


def check_mmcv() -> bool:
    if not is_installed("mmcv"):
        return False

    try:
        import mmcv
    except Exception:
        return False

    if not hasattr(mmcv, "__version__"):
        return False

    return version.parse(mmcv.__version__) >= version.parse("2.0.0")


def check_mmdet() -> bool:
    if not is_installed("mmdet"):
        return False

    try:
        import mmdet
    except Exception:
        return False

    if not hasattr(mmdet, "__version__"):
        return False

    return version.parse(mmdet.__version__) >= version.parse("3.0.0")


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
        run_pip("install openmim", desc="opemmim")

    if not check_mmcv():
        print("Installing mmcv...")
        run(f'"{python}" -m mim install -U mmcv==2.0.0', live=True)

    if not check_mmdet():
        print("Installing mmdet...")
        run(f'"{python}" -m mim install mmdet==3.0.0', live=True)


install()
