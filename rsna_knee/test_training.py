import sys
sys.path.append('src')
import torch
from pathlib import Path
from training.trainer import train_fold
from data.dataloader import create_dataloaders

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")

config = {
    "backbone": "efficientnet_b0",
    "pretrained": False,
    "feature_dim": 256,
    "slice_aggregation": "attention",
    "series_fusion": "attention",
    "dropout": 0.2,
    "loss": "asymmetric",
    "loss_kwargs": {"gamma_neg": 4, "gamma_pos": 1},
    "lr": 3e-4,
    "weight_decay": 1e-4,
    "epochs": 2,
    "scheduler": "cosine",
    "amp": False,
    "use_ema": True,
    "ema_decay": 0.999,
    "grad_clip": 1.0,
    "log_interval": 10,
    "save_interval": 1,
    "early_stopping": 10,
}

train_loader, val_loader = create_dataloaders(
    'data/synthetic', batch_size=2, num_workers=0,
    max_series=3, max_slices=16
)

output_dir = Path("outputs/test_train")
output_dir.mkdir(parents=True, exist_ok=True)

auc = train_fold(0, train_loader, val_loader, config, device, output_dir)
print(f"Test training completed. Best AUC: {auc:.4f}")