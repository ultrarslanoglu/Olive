# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
import argparse
import random
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
from torchvision.models import ResNet50_Weights, resnet50

# ruff: noqa: PLW2901, T201


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_epochs", type=int, default=1)
    return parser.parse_args()


def get_directories():
    current_dir = Path(__file__).resolve().parent

    # models directory for resnet sample
    models_dir = current_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # data directory for resnet sample
    data_dir = current_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # cache directory for resnet sample
    cache_dir = current_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    return current_dir, models_dir, data_dir, cache_dir


def load_resnet_model():
    weights = ResNet50_Weights.DEFAULT
    resnet = resnet50(weights=weights)
    resnet.fc = torch.nn.Sequential(torch.nn.Linear(2048, 64), torch.nn.ReLU(inplace=True), torch.nn.Linear(64, 10))
    return resnet


# For updating learning rate
def update_lr(optimizer, lr):
    for param_group in optimizer.param_groups:
        param_group["lr"] = lr


def prepare_model(num_epochs=1, models_dir="models", data_dir="data"):
    seed = 0
    # seed everything to 0 for reproducibility, https://pytorch.org/docs/stable/notes/randomness.html
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    # the following are needed only for GPU
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Hyper-parameters
    learning_rate = 0.001

    # Image preprocessing modules
    transform = transforms.Compose(
        [transforms.Pad(4), transforms.RandomHorizontalFlip(), transforms.RandomCrop(32), transforms.ToTensor()]
    )

    # CIFAR-10 dataset
    train_dataset = torchvision.datasets.CIFAR10(root=data_dir, train=True, transform=transform, download=False)
    test_dataset = torchvision.datasets.CIFAR10(root=data_dir, train=False, transform=transforms.ToTensor())

    # Data loader
    train_loader = torch.utils.data.DataLoader(dataset=train_dataset, batch_size=100, shuffle=True)
    test_loader = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=100, shuffle=False)

    model = load_resnet_model().to(device)

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # Train the model
    total_step = len(train_loader)
    curr_lr = learning_rate
    for epoch in range(num_epochs):
        for i, (images, labels) in enumerate(train_loader):
            images = images.to(device)
            labels = labels.to(device)
            # Forward pass
            outputs = model(images)
            loss = criterion(outputs, labels)
            # Backward and optimize
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            if (i + 1) % 100 == 0:
                print(f"Epoch [{epoch + 1}/{num_epochs}], Step [{i + 1}/{total_step}] Loss: {loss.item():.4f}")
        # Decay learning rate
        if (epoch + 1) % 20 == 0:
            curr_lr /= 3
            update_lr(optimizer, curr_lr)

    # Test the model
    model.eval()
    if num_epochs:
        with torch.no_grad():
            correct = 0
            total = 0
            for images, labels in test_loader:
                images = images.to(device)
                labels = labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

            print(f"Accuracy of the model on the test images: {100 * correct / total} %")

    # Save the model
    model.to("cpu")
    torch.save(model, str(models_dir / "resnet_trained_for_cifar10.pt"))
    dummy_input = torch.randn(1, 3, 32, 32)
    torch.onnx.export(
        model,
        dummy_input,
        str(models_dir / "resnet_trained_for_cifar10.onnx"),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )


def main():
    _, models_dir, data_dir, _ = get_directories()
    args = get_args()

    data_download_path = data_dir / "cifar-10-python.tar.gz"
    urllib.request.urlretrieve("https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz", data_download_path)
    with tarfile.open(data_download_path) as tar:
        tar.extractall(data_dir)  # lgtm

    prepare_model(args.num_epochs, models_dir, data_dir)


if __name__ == "__main__":
    main()
