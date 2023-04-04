import platform
import sys

import torch
from packaging import version

from launch import is_installed, run

mmcv_url = {
    "2.0.0+cu117": "https://download.openmmlab.com/mmcv/dist/cu117/torch2.0.0/index.html",
    "2.0.0+cu118": "https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html",
}

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


def check_mmcv() -> bool:
    if not is_installed("mmcv"):
        return False

    import mmcv

    return version.parse(mmcv.__version__) >= version.parse("2.0.0rc4")


def check_mmdet() -> bool:
    if not is_installed("mmdet"):
        return False

    import mmdet

    return version.parse(mmdet.__version__) >= version.parse("3.0.0rc6")


def install_pycocotools():
    system = platform.system()
    machine = platform.machine()

    if system not in ["Windows", "Linux"] or machine not in ["AMD64", "x86_64"]:
        print("Installing pycocotools from pypi...")
        run("pip install pycocotools")
        return

    links = pycocotools[system]
    version = sys.version_info[:2]
    if version not in links:
        print("Installing pycocotools from pypi...")
        run("pip install pycocotools")
        return

    url = links[version]
    print("Installing pycocotools...")
    run(f"pip install {url}")


def install():
    if not check_mmcv():
        print("Installing mmcv...")
        torch_version = torch.__version__
        if torch_version in mmcv_url:
            run(f"pip install mmcv -f {mmcv_url[torch_version]}")
        else:
            run("pip install mmcv==2.0.0rc4")

    if not is_installed("pycocotools"):
        install_pycocotools()

    if not check_mmdet():
        print("Installing mmdet...")
        run("pip install mmdet==3.0.0rc6")

    if not is_installed("mim"):
        print("Installing openmim...")
        run("pip install openmim")


install()
