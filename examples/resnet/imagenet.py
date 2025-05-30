# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
#
# Modifications Copyright(C) 2025 Advanced Micro Devices, Inc. All rights reserved.
#
from logging import getLogger
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms as transforms
import transformers
from torch import from_numpy
from torch.utils.data import Dataset

from olive.data.registry import Registry

logger = getLogger(__name__)


class ImagenetDataset(Dataset):
    def __init__(self, data):
        self.images = from_numpy(data["images"])
        self.labels = from_numpy(data["labels"])

    def __len__(self):
        return min(len(self.images), len(self.labels))

    def __getitem__(self, idx):
        return {"pixel_values": self.images[idx]}, self.labels[idx]


@Registry.register_post_process()
def imagenet_post_fun(output):
    return (
        output.logits.argmax(axis=1)
        if isinstance(output, transformers.modeling_outputs.ModelOutput)
        else output.argmax(axis=1)
    )


preprocess = transforms.Compose(
    [
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


@Registry.register_pre_process()
def dataset_pre_process(output_data, **kwargs):
    cache_key = kwargs.get("cache_key")
    size = kwargs.get("size", 256)
    transpose = kwargs.get("transpose", False)
    cache_file = None
    if cache_key:
        suffix = "nhwc" if transpose else "nchw"
        cache_file = Path(f"./cache/data/{cache_key}_{size}_{suffix}.npz")
        if cache_file.exists():
            with np.load(Path(cache_file), allow_pickle=True) as data:
                return ImagenetDataset(data)

    labels = []
    images = []
    for i, sample in enumerate(output_data):
        if i >= size:
            break
        image = sample["image"]
        label = sample["label"]
        image = image.convert("RGB")
        image = preprocess(image)
        if transpose:
            image = torch.permute(image, (1, 2, 0))
        images.append(image)
        labels.append(label)

    result_data = ImagenetDataset({"images": np.array(images), "labels": np.array(labels)})

    if cache_file:
        cache_file.parent.resolve().mkdir(parents=True, exist_ok=True)
        np.savez(cache_file, images=np.array(images), labels=np.array(labels))

    return result_data
