"""Local image generation: SD1.5 + ControlNet (canny or lineart), tuned for 8 GB.

fp16 + attention/VAE slicing, resident on the GPU (SD1.5 + ControlNet fits 8 GB at our
sizes). `encode_prompt` uses compel to chunk/weight a prompt past CLIP's 77-token cap so
the full image-prompt detail reaches the model; pass the resulting embeds to `generate`.
"""

from __future__ import annotations

import torch
from diffusers import (
    ControlNetModel,
    StableDiffusionControlNetPipeline,
    UniPCMultistepScheduler,
)
from PIL import Image, ImageOps

BASE_ID = "stable-diffusion-v1-5/stable-diffusion-v1-5"
CONTROLNETS = {
    "canny": "lllyasviel/sd-controlnet-canny",
    "lineart": "lllyasviel/control_v11p_sd15_lineart",
}
DEFAULT_NEGATIVE = ("blurry, lowres, text, watermark, signature, deformed, distorted, "
                    "people, person, characters, figures, extra limbs")

# Locked defaults (from the cross-room + multi-seed conformity sweeps): lineart is the
# consistently better ControlNet, and 0.38 is the minimum conditioning scale that reliably
# copies the wireframe layout across rooms/seeds while staying organic. Revisit with the API.
DEFAULT_CONTROL_TYPE = "lineart"
DEFAULT_SCALE = 0.38


def load_pipeline(control_type: str, offload: bool = False) -> StableDiffusionControlNetPipeline:
    controlnet = ControlNetModel.from_pretrained(CONTROLNETS[control_type], torch_dtype=torch.float16)
    common = dict(controlnet=controlnet, torch_dtype=torch.float16,
                  safety_checker=None, requires_safety_checker=False)
    try:
        pipe = StableDiffusionControlNetPipeline.from_pretrained(BASE_ID, variant="fp16", **common)
    except Exception:
        pipe = StableDiffusionControlNetPipeline.from_pretrained(BASE_ID, **common)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()
    if offload:
        pipe.enable_model_cpu_offload()   # fallback for tighter memory
    else:
        pipe.to("cuda")
    return pipe


def to_control(image: Image.Image, size: tuple[int, int], invert: bool = True) -> Image.Image:
    """Our wireframes are black-on-white; canny/lineart ControlNets want white lines on
    black, so invert by default."""
    g = image.convert("L")
    if invert:
        g = ImageOps.invert(g)
    return g.convert("RGB").resize(size)


def encode_prompt(pipe, prompt: str, negative: str = DEFAULT_NEGATIVE):
    """Compel-encoded (positive, negative) embeddings — uses the FULL prompt past 77 tokens."""
    from compel import Compel

    compel = Compel(tokenizer=pipe.tokenizer, text_encoder=pipe.text_encoder,
                    truncate_long_prompts=False)
    pos = compel(prompt)
    neg = compel(negative)
    pos, neg = compel.pad_conditioning_tensors_to_same_length([pos, neg])
    return pos, neg


def generate(pipe, control: Image.Image, *, prompt: str | None = None,
             negative: str = DEFAULT_NEGATIVE, prompt_embeds=None, negative_prompt_embeds=None,
             scale: float = DEFAULT_SCALE, seed: int = 42, steps: int = 22, guidance: float = 7.5) -> Image.Image:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    text_kw = ({"prompt_embeds": prompt_embeds, "negative_prompt_embeds": negative_prompt_embeds}
               if prompt_embeds is not None
               else {"prompt": prompt, "negative_prompt": negative})
    return pipe(
        image=control,
        num_inference_steps=steps,
        guidance_scale=guidance,
        controlnet_conditioning_scale=scale,
        width=control.width,
        height=control.height,
        generator=generator,
        **text_kw,
    ).images[0]
