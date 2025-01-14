import os

import lightning as L
import torch
from flytekit import PodTemplate, Resources, logger, task, workflow
from flytekit.types.directory import FlyteDirectory
from flytekitplugins.kfpytorch import PyTorch, Worker
from kubernetes.client.models import (
    V1Container,
    V1PersistentVolumeClaimVolumeSource,
    V1PodSpec,
    V1Volume,
    V1VolumeMount,
)
from lightning.pytorch.callbacks import Callback, RichProgressBar
from lightning.pytorch.loggers import CSVLogger
from lightning.pytorch.strategies import DDPStrategy
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import CIFAR100
from torchvision.models import ResNet50_Weights, resnet50

torch.set_float32_matmul_precision("high")

# Pod template configuration
pullTemplate = PodTemplate(
    primary_container_name="default",
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="default",
                image_pull_policy="Always",
                volume_mounts=[
                    V1VolumeMount(mount_path="/shared", name="shared", read_only=False)
                ],
                working_dir="/shared",
            )
        ],
        volumes=[
            V1Volume(
                name="shared",
                persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                    claim_name="flyte-pvc"
                ),
            )
        ],
    ),
)


class EpochProgressCallback(Callback):
    def on_train_epoch_start(self, trainer, pl_module):
        logger.info(f"Starting epoch {trainer.current_epoch + 1}/{trainer.max_epochs}")

    def on_train_epoch_end(self, trainer, pl_module):
        metrics = trainer.callback_metrics
        logger.info(
            f"Epoch {trainer.current_epoch + 1}: "
            f"loss: {metrics['train_loss_epoch']:.4f}, "
            f"acc: {metrics['train_acc_epoch']:.4f}"
        )


class CIFAR100Model(L.LightningModule):
    def __init__(self, weights_dir):
        super().__init__()
        # Set torch hub directory to our writable path
        torch.hub.set_dir(weights_dir)
        weights = ResNet50_Weights.DEFAULT
        model_weights_path = os.path.join(
            torch.hub.get_dir(), "checkpoints", os.path.basename(weights.url)
        )

        if os.path.exists(model_weights_path):
            # Weights already exist, just load the model
            self.model = resnet50(weights=weights)
        else:
            # Need to download weights
            if (
                not torch.distributed.is_initialized()
                or torch.distributed.get_rank() == 0
            ):
                self.model = resnet50(weights=weights)
            else:
                self.model = resnet50(weights=None)

        # Modify for CIFAR-100
        self.model.conv1 = nn.Conv2d(
            3, 64, kernel_size=3, stride=1, padding=1, bias=False
        )
        self.model.fc = nn.Linear(self.model.fc.in_features, 100)

        if torch.distributed.is_initialized():
            torch.distributed.barrier()

    def training_step(self, batch, batch_idx):
        x, y = batch
        logits = self.model(x)
        loss = nn.functional.cross_entropy(logits, y)
        acc = (logits.argmax(dim=1) == y).float().mean()
        self.log(
            "train_loss",
            loss,
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            logger=True,
            sync_dist=True,
        )
        self.log(
            "train_acc",
            acc,
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            logger=True,
            sync_dist=True,
        )
        return loss

    def configure_optimizers(self):
        optimizer = optim.AdamW(self.parameters(), lr=1e-3, weight_decay=0.05)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
        return [optimizer], [scheduler]


class CIFAR100DataModule(L.LightningDataModule):
    def __init__(self, root_dir, batch_size, dataloader_num_workers):
        super().__init__()
        self.root_dir = root_dir
        self.batch_size = batch_size
        self.dataloader_num_workers = dataloader_num_workers
        self.transform = transforms.Compose(
            [
                transforms.RandomCrop(32, padding=4),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(15),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.5071, 0.4867, 0.4408], std=[0.2675, 0.2565, 0.2761]
                ),
            ]
        )

    def prepare_data(self):
        if self.trainer.is_global_zero:
            CIFAR100(self.root_dir, train=True, download=True)

    def setup(self, stage=None):
        self.dataset = CIFAR100(
            self.root_dir, train=True, download=False, transform=self.transform
        )

    def train_dataloader(self):
        persistent_workers = self.dataloader_num_workers > 0
        return DataLoader(
            self.dataset,
            batch_size=self.batch_size,
            num_workers=self.dataloader_num_workers,
            persistent_workers=persistent_workers,
            pin_memory=True,
            shuffle=True,
        )


@task(
    cache=True,
    cache_version="1.0",
    environment={"TORCH_HOME": "/shared/data"},
    container_image="ghcr.io/tylertitsworth/jetson-flyte:latest",
    pod_template=pullTemplate,
)
def download_dataset() -> FlyteDirectory:
    """Download CIFAR-100 dataset."""
    root_dir = os.getcwd()
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Download dataset
    CIFAR100(data_dir, train=True, download=True)

    # Download model weights
    weights_dir = os.path.join(data_dir, "weights")
    os.makedirs(weights_dir, exist_ok=True)
    torch.hub.set_dir(weights_dir)
    _ = resnet50(weights=ResNet50_Weights.DEFAULT)

    return FlyteDirectory(path=str(data_dir))


@task(
    cache=False,
    environment={
        "TOKENIZERS_PARALLELISM": "true",
        "FLYTE_SDK_LOGGING_LEVEL": "20",
        "NCCL_DEBUG": "INFO",
        "TORCH_HOME": "/shared/data",
        "FLYTE_SDK_LOGGING_FORMAT": "%(message)s",
    },
    retries=0,
    task_config=PyTorch(worker=Worker(replicas=1)),
    container_image="ghcr.io/tylertitsworth/ai-cluster:jetson-flyte",
    limits=Resources(cpu="6", gpu="1", mem="6000Mi"),
    pod_template=pullTemplate,
    requests=Resources(cpu="4", gpu="1", mem="4000Mi"),
)
def train_model(
    data_dir: FlyteDirectory, dataloader_num_workers: int, batch_size: int, epochs: int
) -> FlyteDirectory:
    """Train ResNet50 on CIFAR-100."""

    root_dir = os.getcwd()

    model = CIFAR100Model(os.path.join(str(data_dir), "weights"))
    data = CIFAR100DataModule(
        str(data_dir),  # Use the downloaded data directory
        batch_size=batch_size,
        dataloader_num_workers=dataloader_num_workers,
    )

    model_dir = os.path.join(root_dir, "model")
    progress_bar = RichProgressBar(
        refresh_rate=1,
        leave=True,
    )
    trainer = L.Trainer(
        callbacks=[
            progress_bar,
            EpochProgressCallback(),
        ],
        default_root_dir=model_dir,
        max_epochs=epochs,
        accelerator="gpu",
        strategy=DDPStrategy(
            process_group_backend="gloo",
            find_unused_parameters=False,
        ),
        logger=CSVLogger("logs"),
        precision="16-mixed",
        gradient_clip_val=1.0,
    )
    trainer.fit(model=model, datamodule=data)
    return FlyteDirectory(path=str(model_dir))


@workflow
def train_workflow(
    dataloader_num_workers: int = 2, batch_size: int = 64, epochs: int = 3
) -> FlyteDirectory:
    data_dir = download_dataset()
    return train_model(
        data_dir=data_dir,
        dataloader_num_workers=dataloader_num_workers,
        batch_size=batch_size,
        epochs=epochs,
    )
