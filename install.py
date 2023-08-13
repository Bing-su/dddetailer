import sys
from pathlib import Path
from textwrap import dedent

from packaging import version

import launch
from launch import is_installed, run, run_pip

try:
    skip_install = launch.args.skip_install
except Exception:
    skip_install = False

python = sys.executable

def check_ddetailer() -> bool:
    try:
        from modules.paths import extensions_dir

        extensions_path = Path(extensions_dir)
    except ImportError:
        from modules.paths import data_path

        extensions_path = Path(data_path, "extensions")

    ddetailer_exists = any(p.is_dir() and p.name.startswith("ddetailer") for p in extensions_path.iterdir())
    return not ddetailer_exists


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


def install():
    if not is_installed("pycocotools"):
        run(f'{python} -m pip install --extra-index-url https://bing-su.github.io/mypypi/ pycocotools', live=True)

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
