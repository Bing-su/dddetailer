import os
import sys
from copy import copy
from pathlib import Path
from textwrap import dedent

import cv2
import gradio as gr
import numpy as np
from basicsr.utils.download_util import load_file_from_url
from packaging.version import parse
from PIL import Image

from launch import run
from modules import (
    devices,
    images,
    modelloader,
    processing,
    script_callbacks,
    scripts,
    shared,
)
from modules.paths import data_path, models_path
from modules.processing import (
    Processed,
    StableDiffusionProcessingImg2Img,
    StableDiffusionProcessingTxt2Img,
)
from modules.sd_models import model_hash
from modules.shared import cmd_opts, opts, state

DETECTION_DETAILER = "Detection Detailer"
dd_models_path = os.path.join(models_path, "mmdet")
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

    v1 = parse(mmcv.__version__) >= parse("2.0.0")
    v2 = parse(mmdet.__version__) >= parse("3.0.0")
    return v1 and v2


def list_models(model_path):
    model_list = modelloader.load_models(model_path=model_path, ext_filter=[".pth"])

    def modeltitle(path, shorthash):
        abspath = os.path.abspath(path)

        if abspath.startswith(model_path):
            name = abspath.replace(model_path, "")
        else:
            name = os.path.basename(path)

        if name.startswith(("\\", "/")):
            name = name[1:]

        shortname = os.path.splitext(name.replace("/", "_").replace("\\", "_"))[0]

        return f"{name} [{shorthash}]", shortname

    models = []
    for filename in model_list:
        h = model_hash(filename)
        title, short_model_name = modeltitle(filename, h)
        models.append(title)

    return models


def startup():
    if not check_ddetailer():
        message = """
        [-] dddetailer: dddetailer doesn't work with the original ddetailer extension.
                        dddetailer는 원본 ddetailer 확장이 있을 때 동작하지 않습니다.
        """
        raise RuntimeError(dedent(message))

    if not check_install():
        run(f'"{python}" -m pip uninstall -y mmcv mmcv-full mmdet mmengine')
        run(f'"{python}" -m pip install openmim', desc="Installing openmim", errdesc="Couldn't install openmim")
        run(
            f'"{python}" -m mim install mmcv>=2.0.0 mmdet>=3.0.0',
            desc="Installing mmdet",
            errdesc="Couldn't install mmdet",
        )

    if len(list_models(dd_models_path)) == 0:
        print("No detection models found, downloading...")
        bbox_path = os.path.join(dd_models_path, "bbox")
        segm_path = os.path.join(dd_models_path, "segm")
        # bbox
        load_file_from_url(
            "https://huggingface.co/dustysys/ddetailer/resolve/main/mmdet/bbox/mmdet_anime-face_yolov3.pth",
            bbox_path,
        )
        load_file_from_url(
            "https://raw.githubusercontent.com/Bing-su/dddetailer/master/config/mmdet_anime-face_yolov3.py",
            bbox_path,
        )
        # segm
        load_file_from_url(
            "https://github.com/Bing-su/dddetailer/releases/download/segm/mmdet_dd-person_mask2former.pth",
            segm_path,
        )
        load_file_from_url(
            "https://raw.githubusercontent.com/Bing-su/dddetailer/master/config/mmdet_dd-person_mask2former.py",
            segm_path,
        )
        load_file_from_url(
            "https://raw.githubusercontent.com/Bing-su/dddetailer/master/config/mask2former_r50_8xb2-lsj-50e_coco-panoptic.py",
            segm_path,
        )
        load_file_from_url(
            "https://raw.githubusercontent.com/Bing-su/dddetailer/master/config/coco_panoptic.py",
            segm_path,
        )


startup()


def gr_show(visible=True):
    return {"visible": visible, "__type__": "update"}


def ddetailer_extra_generation_params(
    dd_prompt,
    dd_neg_prompt,
    dd_model_a,
    dd_conf_a,
    dd_dilation_factor_a,
    dd_offset_x_a,
    dd_offset_y_a,
    dd_preprocess_b,
    dd_bitwise_op,
    dd_model_b,
    dd_conf_b,
    dd_dilation_factor_b,
    dd_offset_x_b,
    dd_offset_y_b,
    dd_mask_blur,
    dd_denoising_strength,
    dd_inpaint_full_res,
    dd_inpaint_full_res_padding,
    dd_cfg_scale,
):
    params = {
        "DDetailer prompt": dd_prompt,
        "DDetailer neg prompt": dd_neg_prompt,
        "DDetailer model a": dd_model_a,
        "DDetailer conf a": dd_conf_a,
        "DDetailer dilation a": dd_dilation_factor_a,
        "DDetailer offset x a": dd_offset_x_a,
        "DDetailer offset y a": dd_offset_y_a,
        "DDetailer preprocess b": dd_preprocess_b,
        "DDetailer bitwise": dd_bitwise_op,
        "DDetailer model b": dd_model_b,
        "DDetailer conf b": dd_conf_b,
        "DDetailer dilation b": dd_dilation_factor_b,
        "DDetailer offset x b": dd_offset_x_b,
        "DDetailer offset y b": dd_offset_y_b,
        "DDetailer mask blur": dd_mask_blur,
        "DDetailer denoising": dd_denoising_strength,
        "DDetailer inpaint full": dd_inpaint_full_res,
        "DDetailer inpaint padding": dd_inpaint_full_res_padding,
        "DDetailer cfg": dd_cfg_scale,
        "Script": DETECTION_DETAILER,
    }
    if not dd_prompt:
        params.pop("DDetailer prompt")
    if not dd_neg_prompt:
        params.pop("DDetailer neg prompt")
    return params


class DetectionDetailerScript(scripts.Script):
    def title(self):
        return DETECTION_DETAILER

    def show(self, is_img2img):
        return True

    def ui(self, is_img2img):
        import modules.ui

        model_list = list_models(dd_models_path)
        model_list.insert(0, "None")
        if is_img2img:
            info = gr.HTML(
                '<p style="margin-bottom:0.75em">Recommended settings: Use from inpaint tab, inpaint at full res ON, denoise < 0.5</p>'
            )
        else:
            info = gr.HTML("")
        dd_prompt = None
        with gr.Group():
            if not is_img2img:
                with gr.Row():
                    dd_prompt = gr.Textbox(
                        label="dd_prompt",
                        elem_id="t2i_dd_prompt",
                        show_label=False,
                        lines=3,
                        placeholder="Ddetailer Prompt",
                    )

                with gr.Row():
                    dd_neg_prompt = gr.Textbox(
                        label="dd_neg_prompt",
                        elem_id="t2i_dd_neg_prompt",
                        show_label=False,
                        lines=2,
                        placeholder="Ddetailer Negative prompt",
                    )

            with gr.Row():
                dd_model_a = gr.Dropdown(
                    label="Primary detection model (A)",
                    choices=model_list,
                    value="None",
                    visible=True,
                    type="value",
                )

            with gr.Row():
                dd_conf_a = gr.Slider(
                    label="Detection confidence threshold % (A)",
                    minimum=0,
                    maximum=100,
                    step=1,
                    value=30,
                    visible=True,
                )
                dd_dilation_factor_a = gr.Slider(
                    label="Dilation factor (A)",
                    minimum=0,
                    maximum=255,
                    step=1,
                    value=4,
                    visible=True,
                )

            with gr.Row():
                dd_offset_x_a = gr.Slider(
                    label="X offset (A)",
                    minimum=-200,
                    maximum=200,
                    step=1,
                    value=0,
                    visible=True,
                )
                dd_offset_y_a = gr.Slider(
                    label="Y offset (A)",
                    minimum=-200,
                    maximum=200,
                    step=1,
                    value=0,
                    visible=True,
                )

            with gr.Row():
                dd_preprocess_b = gr.Checkbox(
                    label="Inpaint model B detections before model A runs",
                    value=False,
                    visible=True,
                )
                dd_bitwise_op = gr.Radio(
                    label="Bitwise operation",
                    choices=["None", "A&B", "A-B"],
                    value="None",
                    visible=True,
                )

        br = gr.HTML("<br>")

        with gr.Group():
            with gr.Row():
                dd_model_b = gr.Dropdown(
                    label="Secondary detection model (B) (optional)",
                    choices=model_list,
                    value="None",
                    visible=True,
                    type="value",
                )

            with gr.Row():
                dd_conf_b = gr.Slider(
                    label="Detection confidence threshold % (B)",
                    minimum=0,
                    maximum=100,
                    step=1,
                    value=30,
                    visible=True,
                )
                dd_dilation_factor_b = gr.Slider(
                    label="Dilation factor (B)",
                    minimum=0,
                    maximum=255,
                    step=1,
                    value=4,
                    visible=True,
                )

            with gr.Row():
                dd_offset_x_b = gr.Slider(
                    label="X offset (B)",
                    minimum=-200,
                    maximum=200,
                    step=1,
                    value=0,
                    visible=True,
                )
                dd_offset_y_b = gr.Slider(
                    label="Y offset (B)",
                    minimum=-200,
                    maximum=200,
                    step=1,
                    value=0,
                    visible=True,
                )

        with gr.Group():
            with gr.Row():
                dd_mask_blur = gr.Slider(
                    label="Mask blur ",
                    minimum=0,
                    maximum=64,
                    step=1,
                    value=4,
                    visible=(not is_img2img),
                )
                dd_denoising_strength = gr.Slider(
                    label="Denoising strength (Inpaint)",
                    minimum=0.0,
                    maximum=1.0,
                    step=0.01,
                    value=0.4,
                    visible=(not is_img2img),
                )

            with gr.Row():
                dd_inpaint_full_res = gr.Checkbox(
                    label="Inpaint at full resolution ",
                    value=True,
                    visible=(not is_img2img),
                )
                dd_inpaint_full_res_padding = gr.Slider(
                    label="Inpaint at full resolution padding, pixels ",
                    minimum=0,
                    maximum=256,
                    step=4,
                    value=32,
                    visible=(not is_img2img),
                )

            with gr.Row():
                dd_cfg_scale = gr.Slider(
                    label="CFG Scale",
                    minimum=0,
                    maximum=30,
                    step=0.5,
                    value=7,
                    visible=True,
                )

        dd_model_a.change(
            lambda modelname: {
                dd_model_b: gr_show(modelname != "None"),
                dd_conf_a: gr_show(modelname != "None"),
                dd_dilation_factor_a: gr_show(modelname != "None"),
                dd_offset_x_a: gr_show(modelname != "None"),
                dd_offset_y_a: gr_show(modelname != "None"),
            },
            inputs=[dd_model_a],
            outputs=[
                dd_model_b,
                dd_conf_a,
                dd_dilation_factor_a,
                dd_offset_x_a,
                dd_offset_y_a,
            ],
        )

        dd_model_b.change(
            lambda modelname: {
                dd_preprocess_b: gr_show(modelname != "None"),
                dd_bitwise_op: gr_show(modelname != "None"),
                dd_conf_b: gr_show(modelname != "None"),
                dd_dilation_factor_b: gr_show(modelname != "None"),
                dd_offset_x_b: gr_show(modelname != "None"),
                dd_offset_y_b: gr_show(modelname != "None"),
            },
            inputs=[dd_model_b],
            outputs=[
                dd_preprocess_b,
                dd_bitwise_op,
                dd_conf_b,
                dd_dilation_factor_b,
                dd_offset_x_b,
                dd_offset_y_b,
            ],
        )
        if dd_prompt:
            self.infotext_fields = (
                (dd_prompt, "DDetailer prompt"),
                (dd_neg_prompt, "DDetailer neg prompt"),
                (dd_model_a, "DDetailer model a"),
                (dd_conf_a, "DDetailer conf a"),
                (dd_dilation_factor_a, "DDetailer dilation a"),
                (dd_offset_x_a, "DDetailer offset x a"),
                (dd_offset_y_a, "DDetailer offset y a"),
                (dd_preprocess_b, "DDetailer preprocess b"),
                (dd_bitwise_op, "DDetailer bitwise"),
                (dd_model_b, "DDetailer model b"),
                (dd_conf_b, "DDetailer conf b"),
                (dd_dilation_factor_b, "DDetailer dilation b"),
                (dd_offset_x_b, "DDetailer offset x b"),
                (dd_offset_y_b, "DDetailer offset y b"),
                (dd_mask_blur, "DDetailer mask blur"),
                (dd_denoising_strength, "DDetailer denoising"),
                (dd_inpaint_full_res, "DDetailer inpaint full"),
                (dd_inpaint_full_res_padding, "DDetailer inpaint padding"),
                (dd_cfg_scale, "DDetailer cfg"),
            )

        ret = [
            info,
            dd_model_a,
            dd_conf_a,
            dd_dilation_factor_a,
            dd_offset_x_a,
            dd_offset_y_a,
            dd_preprocess_b,
            dd_bitwise_op,
            br,
            dd_model_b,
            dd_conf_b,
            dd_dilation_factor_b,
            dd_offset_x_b,
            dd_offset_y_b,
            dd_mask_blur,
            dd_denoising_strength,
            dd_inpaint_full_res,
            dd_inpaint_full_res_padding,
            dd_cfg_scale,
        ]
        if not is_img2img:
            ret += [dd_prompt, dd_neg_prompt]
        return ret

    def run(
        self,
        p,
        info,
        dd_model_a,
        dd_conf_a,
        dd_dilation_factor_a,
        dd_offset_x_a,
        dd_offset_y_a,
        dd_preprocess_b,
        dd_bitwise_op,
        br,
        dd_model_b,
        dd_conf_b,
        dd_dilation_factor_b,
        dd_offset_x_b,
        dd_offset_y_b,
        dd_mask_blur,
        dd_denoising_strength,
        dd_inpaint_full_res,
        dd_inpaint_full_res_padding,
        dd_cfg_scale,
        dd_prompt=None,
        dd_neg_prompt=None,
    ):
        processing.fix_seed(p)
        seed = p.seed
        subseed = p.subseed
        p.batch_size = 1
        ddetail_count = p.n_iter
        p.n_iter = 1
        p.do_not_save_grid = True
        p.do_not_save_samples = True
        is_txt2img = isinstance(p, StableDiffusionProcessingTxt2Img)
        info = ""

        # ddetailer info
        extra_generation_params = ddetailer_extra_generation_params(
            dd_prompt,
            dd_neg_prompt,
            dd_model_a,
            dd_conf_a,
            dd_dilation_factor_a,
            dd_offset_x_a,
            dd_offset_y_a,
            dd_preprocess_b,
            dd_bitwise_op,
            dd_model_b,
            dd_conf_b,
            dd_dilation_factor_b,
            dd_offset_x_b,
            dd_offset_y_b,
            dd_mask_blur,
            dd_denoising_strength,
            dd_inpaint_full_res,
            dd_inpaint_full_res_padding,
            dd_cfg_scale,
        )
        p.extra_generation_params.update(extra_generation_params)

        p_txt = copy(p)
        if not is_txt2img:
            orig_image = p.init_images[0]
        else:
            img2img_sampler_name = p_txt.sampler_name
            # PLMS/UniPC do not support img2img so we just silently switch to DDIM
            if p_txt.sampler_name in ["PLMS", "UniPC"]:
                img2img_sampler_name = "DDIM"
            p_txt_prompt = dd_prompt if dd_prompt else p_txt.prompt
            p_txt_neg_prompt = dd_neg_prompt if dd_neg_prompt else p_txt.negative_prompt
            p = StableDiffusionProcessingImg2Img(
                init_images=None,
                resize_mode=0,
                denoising_strength=dd_denoising_strength,
                mask=None,
                mask_blur=dd_mask_blur,
                inpainting_fill=1,
                inpaint_full_res=dd_inpaint_full_res,
                inpaint_full_res_padding=dd_inpaint_full_res_padding,
                inpainting_mask_invert=0,
                sd_model=p_txt.sd_model,
                outpath_samples=p_txt.outpath_samples,
                outpath_grids=p_txt.outpath_grids,
                prompt=p_txt_prompt,
                negative_prompt=p_txt_neg_prompt,
                styles=p_txt.styles,
                seed=p_txt.seed,
                subseed=p_txt.subseed,
                subseed_strength=p_txt.subseed_strength,
                seed_resize_from_h=p_txt.seed_resize_from_h,
                seed_resize_from_w=p_txt.seed_resize_from_w,
                sampler_name=img2img_sampler_name,
                n_iter=p_txt.n_iter,
                steps=p_txt.steps,
                cfg_scale=p_txt.cfg_scale,
                width=p_txt.width,
                height=p_txt.height,
                tiling=p_txt.tiling,
                extra_generation_params=p_txt.extra_generation_params,
            )
            p.do_not_save_grid = True
            p.do_not_save_samples = True
            p.cached_c = [None, None]
            p.cached_uc = [None, None]

            p.scripts = p_txt.scripts
            p.script_args = p_txt.script_args

        # output info
        all_prompts = []
        all_negative_prompts = []
        all_seeds = []
        all_subseeds = []
        infotexts = []
        output_images = []

        state.job_count = ddetail_count
        for n in range(ddetail_count):
            devices.torch_gc()
            start_seed = seed + n

            all_prompts.append(p_txt.prompt)
            all_negative_prompts.append(p_txt.negative_prompt)
            all_seeds.append(start_seed)
            all_subseeds.append(subseed + n)

            if is_txt2img:
                print(f"Processing initial image for output generation {n + 1}.")
                p_txt.seed = start_seed
                processed = processing.process_images(p_txt)
                init_image = processed.images[0]
                info = processed.info
                if not dd_prompt:
                    p.prompt = processed.all_prompts[0]
                if not dd_neg_prompt:
                    p.negative_prompt = processed.all_negative_prompts[0]
                all_prompts[n] = processed.all_prompts[0]
                all_negative_prompts[n] = processed.all_negative_prompts[0]
            else:
                init_image = orig_image
                p.prompt = p_txt.prompt
                p.negative_prompt = p_txt.negative_prompt
            p.cfg_scale = dd_cfg_scale

            if opts.enable_pnginfo:
                init_image.info["parameters"] = info

            infotexts.append(info)
            output_images.append(init_image)

            masks_a = []
            masks_b_pre = []

            # Optional secondary pre-processing run
            if dd_model_b != "None" and dd_preprocess_b:
                label_b_pre = "B"
                results_b_pre = inference(init_image, dd_model_b, dd_conf_b / 100.0, label_b_pre)
                masks_b_pre = create_segmasks(results_b_pre)
                masks_b_pre = dilate_masks(masks_b_pre, dd_dilation_factor_b, 1)
                masks_b_pre = offset_masks(masks_b_pre, dd_offset_x_b, dd_offset_y_b)
                if len(masks_b_pre) > 0:
                    results_b_pre = update_result_masks(results_b_pre, masks_b_pre)
                    segmask_preview_b = create_segmask_preview(results_b_pre, init_image)
                    shared.state.current_image = segmask_preview_b
                    if opts.dd_save_previews:
                        images.save_image(
                            segmask_preview_b,
                            opts.outdir_ddetailer_previews,
                            "",
                            start_seed,
                            p.prompt,
                            opts.samples_format,
                            p=p,
                        )
                    gen_count = len(masks_b_pre)
                    state.job_count += gen_count
                    print(f"Processing {gen_count} model {label_b_pre} detections for output generation {n + 1}.")
                    p.seed = start_seed
                    p.init_images = [init_image]

                    for i in range(gen_count):
                        p.image_mask = masks_b_pre[i]
                        if opts.dd_save_masks:
                            images.save_image(
                                masks_b_pre[i],
                                opts.outdir_ddetailer_masks,
                                "",
                                start_seed,
                                p.prompt,
                                opts.samples_format,
                                p=p,
                            )
                        processed = processing.process_images(p)
                        if not is_txt2img:
                            p.prompt = processed.all_prompts[0]
                            p.negative_prompt = processed.all_negative_prompts[0]
                        p.seed = processed.seed + 1
                        p.subseed = processed.subseed + 1
                        p.init_images = [processed.images[0]]

                    if gen_count > 0:
                        output_images[n] = processed.images[0]
                        init_image = processed.images[0]

                else:
                    print(f"No model B detections for output generation {n} with current settings.")

            # Primary run
            if dd_model_a != "None":
                label_a = "A"
                if dd_model_b != "None" and dd_bitwise_op != "None":
                    label_a = dd_bitwise_op
                results_a = inference(init_image, dd_model_a, dd_conf_a / 100.0, label_a)
                masks_a = create_segmasks(results_a)
                masks_a = dilate_masks(masks_a, dd_dilation_factor_a, 1)
                masks_a = offset_masks(masks_a, dd_offset_x_a, dd_offset_y_a)
                if dd_model_b != "None" and dd_bitwise_op != "None":
                    label_b = "B"
                    results_b = inference(init_image, dd_model_b, dd_conf_b / 100.0, label_b)
                    masks_b = create_segmasks(results_b)
                    masks_b = dilate_masks(masks_b, dd_dilation_factor_b, 1)
                    masks_b = offset_masks(masks_b, dd_offset_x_b, dd_offset_y_b)
                    if len(masks_b) > 0:
                        combined_mask_b = combine_masks(masks_b)
                        for i in reversed(range(len(masks_a))):
                            if dd_bitwise_op == "A&B":
                                masks_a[i] = bitwise_and_masks(masks_a[i], combined_mask_b)
                            elif dd_bitwise_op == "A-B":
                                masks_a[i] = subtract_masks(masks_a[i], combined_mask_b)
                            if is_allblack(masks_a[i]):
                                del masks_a[i]
                                for result in results_a:
                                    del result[i]

                    else:
                        print("No model B detections to overlap with model A masks")
                        results_a = []
                        masks_a = []

                if len(masks_a) > 0:
                    results_a = update_result_masks(results_a, masks_a)
                    segmask_preview_a = create_segmask_preview(results_a, init_image)
                    shared.state.current_image = segmask_preview_a
                    if opts.dd_save_previews:
                        images.save_image(
                            segmask_preview_a,
                            opts.outdir_ddetailer_previews,
                            "",
                            start_seed,
                            p.prompt,
                            opts.samples_format,
                            p=p,
                        )
                    gen_count = len(masks_a)
                    state.job_count += gen_count
                    print(f"Processing {gen_count} model {label_a} detections for output generation {n + 1}.")
                    p.seed = start_seed
                    p.init_images = [init_image]

                    for i in range(gen_count):
                        p.image_mask = masks_a[i]
                        if opts.dd_save_masks:
                            images.save_image(
                                masks_a[i],
                                opts.outdir_ddetailer_masks,
                                "",
                                start_seed,
                                p.prompt,
                                opts.samples_format,
                                p=p,
                            )

                        processed = processing.process_images(p)
                        if not is_txt2img:
                            p.prompt = processed.all_prompts[0]
                            p.negative_prompt = processed.all_negative_prompts[0]
                            info = processed.info
                            all_prompts[n] = processed.all_prompts[0]
                            all_negative_prompts[n] = processed.all_negative_prompts[0]
                        p.seed = processed.seed + 1
                        p.subseed = processed.subseed + 1
                        p.init_images = [processed.images[0]]

                    if gen_count > 0:
                        final_image = processed.images[0]

                        if opts.enable_pnginfo:
                            final_image.info["parameters"] = info
                        output_images[n] = final_image
                        infotexts[n] = info

                        if opts.samples_save:
                            images.save_image(
                                final_image,
                                p.outpath_samples,
                                "",
                                start_seed,
                                p.prompt,
                                opts.samples_format,
                                info=info,
                                p=p,
                            )

                else:
                    print(f"No model {label_a} detections for output generation {n} with current settings.")

                    if opts.samples_save:
                        images.save_image(
                            init_image,
                            p.outpath_samples,
                            "",
                            start_seed,
                            p.prompt,
                            opts.samples_format,
                            info=info,
                            p=p,
                        )

            state.job = f"Generation {n + 1} out of {state.job_count}"

        if dd_prompt or dd_neg_prompt:
            params_txt = os.path.join(data_path, "params.txt")
            with open(params_txt, "w", encoding="utf-8") as file:
                file.write(infotexts[0])

        return Processed(
            p,
            output_images,
            seed,
            infotexts[0],
            all_prompts=all_prompts,
            all_negative_prompts=all_negative_prompts,
            all_seeds=all_seeds,
            all_subseeds=all_subseeds,
            infotexts=infotexts,
        )


def modeldataset(model_shortname):
    path = modelpath(model_shortname)
    dataset = "coco" if "mmdet" in path and "segm" in path else "bbox"
    return dataset


def modelpath(model_shortname):
    model_list = modelloader.load_models(model_path=dd_models_path, ext_filter=[".pth"])
    model_h = model_shortname.split("[")[-1].split("]")[0]
    for path in model_list:
        if model_hash(path) == model_h:
            return path
    return None


def update_result_masks(results, masks):
    for i in range(len(masks)):
        boolmask = np.array(masks[i], dtype=bool)
        results[2][i] = boolmask
    return results


def create_segmask_preview(results, image):
    labels = results[0]
    bboxes = results[1]
    segms = results[2]
    scores = results[3]

    cv2_image = np.array(image)
    cv2_image = cv2_image[:, :, ::-1].copy()

    for i in range(len(segms)):
        color = np.full_like(cv2_image, np.random.randint(100, 256, (1, 3), dtype=np.uint8))
        alpha = 0.2
        color_image = cv2.addWeighted(cv2_image, alpha, color, 1 - alpha, 0)
        cv2_mask = segms[i].astype(np.uint8) * 255
        cv2_mask_bool = np.array(segms[i], dtype=bool)
        centroid = np.mean(np.argwhere(cv2_mask_bool), axis=0)
        centroid_x, centroid_y = int(centroid[1]), int(centroid[0])

        cv2_mask_rgb = cv2.merge((cv2_mask, cv2_mask, cv2_mask))
        cv2_image = np.where(cv2_mask_rgb == 255, color_image, cv2_image)
        text_color = tuple([int(x) for x in (color[0][0] - 100)])
        name = labels[i]
        score = scores[i]
        score = str(score)[:4]
        text = name + ":" + score
        cv2.putText(
            cv2_image,
            text,
            (centroid_x - 30, centroid_y),
            cv2.FONT_HERSHEY_DUPLEX,
            0.4,
            text_color,
            1,
            cv2.LINE_AA,
        )

    if len(segms) > 0:
        preview_image = Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))
    else:
        preview_image = image

    return preview_image


def is_allblack(mask):
    cv2_mask = np.array(mask)
    return cv2.countNonZero(cv2_mask) == 0


def bitwise_and_masks(mask1, mask2):
    cv2_mask1 = np.array(mask1)
    cv2_mask2 = np.array(mask2)
    cv2_mask = cv2.bitwise_and(cv2_mask1, cv2_mask2)
    mask = Image.fromarray(cv2_mask)
    return mask


def subtract_masks(mask1, mask2):
    cv2_mask1 = np.array(mask1)
    cv2_mask2 = np.array(mask2)
    cv2_mask = cv2.subtract(cv2_mask1, cv2_mask2)
    mask = Image.fromarray(cv2_mask)
    return mask


def dilate_masks(masks, dilation_factor, iter=1):
    if dilation_factor == 0:
        return masks
    dilated_masks = []
    kernel = np.ones((dilation_factor, dilation_factor), np.uint8)
    for i in range(len(masks)):
        cv2_mask = np.array(masks[i])
        dilated_mask = cv2.dilate(cv2_mask, kernel, iter)
        dilated_masks.append(Image.fromarray(dilated_mask))
    return dilated_masks


def offset_masks(masks, offset_x, offset_y):
    if offset_x == 0 and offset_y == 0:
        return masks
    offset_masks = []
    for i in range(len(masks)):
        cv2_mask = np.array(masks[i])
        offset_mask = cv2_mask.copy()
        offset_mask = np.roll(offset_mask, -offset_y, axis=0)
        offset_mask = np.roll(offset_mask, offset_x, axis=1)

        offset_masks.append(Image.fromarray(offset_mask))
    return offset_masks


def combine_masks(masks):
    initial_cv2_mask = np.array(masks[0])
    combined_cv2_mask = initial_cv2_mask
    for i in range(1, len(masks)):
        cv2_mask = np.array(masks[i])
        combined_cv2_mask = cv2.bitwise_or(combined_cv2_mask, cv2_mask)

    combined_mask = Image.fromarray(combined_cv2_mask)
    return combined_mask


def on_ui_settings():
    shared.opts.add_option(
        "dd_save_previews",
        shared.OptionInfo(False, "Save mask previews", section=("ddetailer", DETECTION_DETAILER)),
    )
    shared.opts.add_option(
        "outdir_ddetailer_previews",
        shared.OptionInfo(
            "extensions/dddetailer/outputs/masks-previews",
            "Output directory for mask previews",
            section=("ddetailer", DETECTION_DETAILER),
        ),
    )
    shared.opts.add_option(
        "dd_save_masks",
        shared.OptionInfo(False, "Save masks", section=("ddetailer", DETECTION_DETAILER)),
    )
    shared.opts.add_option(
        "outdir_ddetailer_masks",
        shared.OptionInfo(
            "extensions/dddetailer/outputs/masks",
            "Output directory for masks",
            section=("ddetailer", DETECTION_DETAILER),
        ),
    )


def create_segmasks(results):
    segms = results[2]
    segmasks = []
    for i in range(len(segms)):
        cv2_mask = segms[i].astype(np.uint8) * 255
        mask = Image.fromarray(cv2_mask)
        segmasks.append(mask)

    return segmasks


from mmdet.apis import inference_detector, init_detector
from mmdet.evaluation import get_classes


def get_device():
    device = devices.get_optimal_device_name()
    if device == "mps":
        return device
    if any(getattr(cmd_opts, vram, False) for vram in ["lowvram", "medvram"]):
        return "cpu"
    return device


def inference(image, modelname, conf_thres, label):
    path = modelpath(modelname)
    if "mmdet" in path and "bbox" in path:
        results = inference_mmdet_bbox(image, modelname, conf_thres, label)
    elif "mmdet" in path and "segm" in path:
        results = inference_mmdet_segm(image, modelname, conf_thres, label)
    return results


def inference_mmdet_segm(image, modelname, conf_thres, label):
    model_checkpoint = modelpath(modelname)
    model_config = os.path.splitext(model_checkpoint)[0] + ".py"
    model_device = get_device()
    model = init_detector(model_config, model_checkpoint, device=model_device)
    mmdet_results = inference_detector(model, np.array(image)).pred_instances
    bboxes = mmdet_results.bboxes.cpu().numpy()
    segms = mmdet_results.masks.cpu().numpy()
    scores = mmdet_results.scores.cpu().numpy()
    dataset = modeldataset(modelname)
    classes = get_classes(dataset)

    n, m = bboxes.shape
    if n == 0:
        return [[], [], [], []]
    labels = mmdet_results.labels
    filter_inds = np.where(scores > conf_thres)[0]
    results = [[], [], [], []]
    for i in filter_inds:
        results[0].append(label + "-" + classes[labels[i]])
        results[1].append(bboxes[i])
        results[2].append(segms[i])
        results[3].append(scores[i])

    return results


def inference_mmdet_bbox(image, modelname, conf_thres, label):
    model_checkpoint = modelpath(modelname)
    model_config = os.path.splitext(model_checkpoint)[0] + ".py"
    model_device = get_device()
    model = init_detector(model_config, model_checkpoint, device=model_device)
    output = inference_detector(model, np.array(image)).pred_instances
    cv2_image = np.array(image)
    cv2_image = cv2_image[:, :, ::-1].copy()
    cv2_gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)

    segms = []
    for x0, y0, x1, y1 in output.bboxes:
        cv2_mask = np.zeros((cv2_gray.shape), np.uint8)
        cv2.rectangle(cv2_mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
        cv2_mask_bool = cv2_mask.astype(bool)
        segms.append(cv2_mask_bool)

    n, m = output.bboxes.shape
    if n == 0:
        return [[], [], [], []]
    bboxes = output.bboxes.cpu().numpy()
    scores = output.scores.cpu().numpy()
    filter_inds = np.where(scores > conf_thres)[0]
    results = [[], [], [], []]
    for i in filter_inds:
        results[0].append(label)
        results[1].append(bboxes[i])
        results[2].append(segms[i])
        results[3].append(scores[i])

    return results


script_callbacks.on_ui_settings(on_ui_settings)
