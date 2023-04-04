import torch
from packaging import version

from launch import is_installed, run

mmcv_url = {
    "2.0.0+cu117": "https://download.openmmlab.com/mmcv/dist/cu117/torch2.0.0/index.html",
    "2.0.0+cu118": "https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html",
}


def check_mmcv() -> bool:
    if not is_installed("mmcv"):
        return False

    import mmcv

    if version.parse(mmcv.__version__) >= version.parse("2.0.0"):
        return True
    return False


def install():
    if not check_mmcv():
        print("Installing mmcv...")
        torch_version = torch.__version__
        if torch_version in mmcv_url:
            run(f"pip install mmcv -f {mmcv_url[torch_version]}")
        else:
            run("pip install mmcv==2.0.0rc4")

    if not is_installed("pycocotools"):
        print("Installing pycocotools...")
        run("pip install aiartchan-pycocotools")

    if not is_installed("mmdet"):
        print("Installing mmdet...")
        run("pip install mmdet")

    if not is_installed("openmim"):
        print("Installing openmim...")
        run("pip install openmim")


install()
