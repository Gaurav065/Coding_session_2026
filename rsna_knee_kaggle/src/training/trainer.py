"""
Training Loop for RSNA Knee Abnormality Detection
Includes macro AUC tracking, class-balanced loss, mixed precision, and EMA.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, OneCycleLR
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
import json
import time
from collections import defaultdict

from src.models.model import KneeAbnormalityModel, ModelEMA, create_model
from src.data.dataloader import LABELS, get_class_weights


class MacroAUCMeter:
    """Tracks per-class and macro AUC during training."""
    
    def __init__(self, num_classes: int, class_names: List[str]):
        self.num_classes = num_classes
        self.class_names = class_names
        self.reset()
    
    def reset(self):
        self.predictions = []
        self.targets = []
    
    def update(self, preds: torch.Tensor, targets: torch.Tensor):
        self.predictions.append(preds.detach().cpu().numpy())
        self.targets.append(targets.detach().cpu().numpy())
    
    def compute(self) -> Dict[str, float]:
        if not self.predictions:
            return {}
        
        preds = np.vstack(self.predictions)
        targets = np.vstack(self.targets)
        
        results = {}
        valid_classes = 0
        macro_auc = 0.0
        
        for i in range(self.num_classes):
            mask = targets[:, i] != -1
            if mask.sum() < 2:
                results[f"auc_{self.class_names[i]}"] = 0.5
                continue
            
            y_true = targets[mask, i]
            y_pred = preds[mask, i]
            
            if len(np.unique(y_true)) < 2:
                results[f"auc_{self.class_names[i]}"] = 0.5
                continue
            
            try:
                auc = roc_auc_score(y_true, y_pred)
                results[f"auc_{self.class_names[i]}"] = auc
                macro_auc += auc
                valid_classes += 1
            except ValueError:
                results[f"auc_{self.class_names[i]}"] = 0.5
        
        results["macro_auc"] = macro_auc / max(valid_classes, 1)
        return results
    
    def log_results(self, prefix: str = "", logger: Optional[logging.Logger] = None):
        results = self.compute()
        msg = f"{prefix} " + " | ".join([f"{k}: {v:.4f}" for k, v in results.items()])
        if logger:
            logger.info(msg)
        else:
            print(msg)
        return results


class FocalLoss(nn.Module):
    """Focal Loss for handling class imbalance."""
    
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, reduction: str = "mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction="none")
        pt = torch.exp(-bce_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * bce_loss
        
        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss


class WeightedBCELoss(nn.Module):
    """BCE with per-class positive weights."""
    
    def __init__(self, pos_weight: torch.Tensor):
        super().__init__()
        self.register_buffer("pos_weight", pos_weight)
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        valid_mask = (targets != -1).float()
        loss = F.binary_cross_entropy_with_logits(
            inputs, targets.clamp(0, 1),
            pos_weight=self.pos_weight.to(inputs.device),
            reduction="none"
        )
        loss = (loss * valid_mask).sum() / valid_mask.sum().clamp(min=1)
        return loss


class AsymmetricLoss(nn.Module):
    """Asymmetric Loss Optimized for Multi-Label Classification."""
    
    def __init__(self, gamma_neg: float = 4, gamma_pos: float = 1, clip: float = 0.05, eps: float = 1e-8):
        super().__init__()
        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip = clip
        self.eps = eps
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        valid_mask = (targets != -1).float()
        targets = targets.clamp(0, 1)
        
        xs_pos = torch.sigmoid(inputs)
        xs_neg = 1 - xs_pos
        
        if self.clip > 0:
            xs_neg = (xs_neg + self.clip).clamp(max=1)
        
        los_pos = targets * torch.log(xs_pos.clamp(min=self.eps))
        los_neg = (1 - targets) * torch.log(xs_neg.clamp(min=self.eps))
        
        loss = los_pos + los_neg
        
        if self.gamma_neg > 0 or self.gamma_pos > 0:
            pt = xs_pos * targets + xs_neg * (1 - targets)
            one_sided_gamma = self.gamma_pos * targets + self.gamma_neg * (1 - targets)
            loss = loss * (1 - pt).pow(one_sided_gamma)
        
        loss = -loss * valid_mask
        return loss.sum() / valid_mask.sum().clamp(min=1)


def get_loss_fn(loss_type: str, pos_weight: Optional[torch.Tensor] = None, **kwargs) -> nn.Module:
    """Factory for loss functions."""
    if loss_type == "bce":
        return WeightedBCELoss(pos_weight) if pos_weight is not None else nn.BCEWithLogitsLoss()
    elif loss_type == "focal":
        return FocalLoss(**kwargs)
    elif loss_type == "asymmetric":
        return AsymmetricLoss(**kwargs)
    else:
        raise ValueError(f"Unknown loss: {loss_type}")


class Trainer:
    """Main training loop with validation, checkpointing, and logging."""
    
    def __init__(
        self,
        model: KneeAbnormalityModel,
        train_loader,
        val_loader,
        config: Dict,
        device: torch.device,
        output_dir: Path,
        logger: Optional[logging.Logger] = None
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)
        
        pos_weight = get_class_weights(
            train_loader.dataset.dataset.df if hasattr(train_loader.dataset, 'dataset') else train_loader.dataset.df
        )
        
        self.criterion = get_loss_fn(
            config.get("loss", "asymmetric"),
            pos_weight=pos_weight.to(device),
            **config.get("loss_kwargs", {})
        ).to(device)
        
        self.optimizer = AdamW(
            model.parameters(),
            lr=config["lr"],
            weight_decay=config.get("weight_decay", 1e-4),
            betas=(0.9, 0.999)
        )
        
        self.scaler = torch.amp.GradScaler('cuda') if config.get("amp", True) else None
        
        total_steps = config["epochs"] * len(train_loader)
        if config.get("scheduler") == "onecycle":
            self.scheduler = OneCycleLR(
                self.optimizer, max_lr=config["lr"],
                total_steps=total_steps, pct_start=0.1
            )
        else:
            self.scheduler = CosineAnnealingLR(
                self.optimizer, T_max=config["epochs"],
                eta_min=config["lr"] * 0.01
            )
        
        self.ema = ModelEMA(model, decay=config.get("ema_decay", 0.999)) if config.get("use_ema", True) else None
        
        self.best_macro_auc = 0.0
        self.best_epoch = 0
        self.history = defaultdict(list)
        
        self.train_meter = MacroAUCMeter(len(LABELS), LABELS)
        self.val_meter = MacroAUCMeter(len(LABELS), LABELS)
    
    def train_epoch(self, epoch: int) -> Dict[str, float]:
        self.model.train()
        self.train_meter.reset()
        
        total_loss = 0.0
        num_batches = 0
        accum_steps = self.config.get("accumulation_steps", 1)
        
        self.optimizer.zero_grad()
        
        for batch_idx, batch in enumerate(self.train_loader):
            series = batch["series"].to(self.device, non_blocking=True)
            series_mask = batch["series_mask"].to(self.device, non_blocking=True)
            slice_masks = batch["slice_masks"].to(self.device, non_blocking=True)
            labels = batch["labels"].to(self.device, non_blocking=True)
            
            if self.scaler:
                with torch.amp.autocast('cuda'):
                    logits, _, _ = self.model(series, series_mask, slice_masks)
                    loss = self.criterion(logits, labels) / accum_steps
                
                self.scaler.scale(loss).backward()
                
                if (batch_idx + 1) % accum_steps == 0 or (batch_idx + 1) == len(self.train_loader):
                    if self.config.get("grad_clip"):
                        self.scaler.unscale_(self.optimizer)
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config["grad_clip"])
                    
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                    self.optimizer.zero_grad()
            else:
                logits, _, _ = self.model(series, series_mask, slice_masks)
                loss = self.criterion(logits, labels) / accum_steps
                
                loss.backward()
                
                if (batch_idx + 1) % accum_steps == 0 or (batch_idx + 1) == len(self.train_loader):
                    if self.config.get("grad_clip"):
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config["grad_clip"])
                    
                    self.optimizer.step()
                    self.optimizer.zero_grad()
            
            if self.config.get("scheduler") == "onecycle":
                self.scheduler.step()
            
            if (batch_idx + 1) % accum_steps == 0:
                if self.ema:
                    self.ema.update(self.model)
            
            total_loss += loss.item() * accum_steps  # undo the division for logging
            num_batches += 1
            
            probs = torch.sigmoid(logits).detach()
            self.train_meter.update(probs, labels)
            
            if batch_idx % self.config.get("log_interval", 50) == 0:
                self.logger.info(f"Epoch {epoch} Batch {batch_idx}/{len(self.train_loader)} Loss: {loss.item() * accum_steps:.4f}")
        
        if self.config.get("scheduler") != "onecycle":
            self.scheduler.step()
        
        train_results = self.train_meter.compute()
        train_results["loss"] = total_loss / num_batches
        train_results["lr"] = self.optimizer.param_groups[0]["lr"]
        
        return train_results
    
    @torch.no_grad()
    def validate(self, epoch: int, use_ema: bool = True) -> Dict[str, float]:
        model = self.ema.module if (use_ema and self.ema) else self.model
        model.eval()
        self.val_meter.reset()
        
        total_loss = 0.0
        num_batches = 0
        
        for batch in self.val_loader:
            series = batch["series"].to(self.device, non_blocking=True)
            series_mask = batch["series_mask"].to(self.device, non_blocking=True)
            slice_masks = batch["slice_masks"].to(self.device, non_blocking=True)
            labels = batch["labels"].to(self.device, non_blocking=True)
            
            if self.scaler:
                with torch.amp.autocast('cuda'):
                    logits, _, _ = model(series, series_mask, slice_masks)
                    loss = self.criterion(logits, labels)
            else:
                logits, _, _ = model(series, series_mask, slice_masks)
                loss = self.criterion(logits, labels)
            
            total_loss += loss.item()
            num_batches += 1
            
            probs = torch.sigmoid(logits)
            self.val_meter.update(probs, labels)
        
        val_results = self.val_meter.compute()
        val_results["loss"] = total_loss / num_batches
        
        return val_results
    
    def save_checkpoint(self, epoch: int, is_best: bool = False):
        state = {
            "epoch": epoch,
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": self.scheduler.state_dict(),
            "best_macro_auc": self.best_macro_auc,
            "config": self.config,
            "history": dict(self.history),
        }
        if self.ema:
            state["ema"] = self.ema.module.state_dict()
        if self.scaler:
            state["scaler"] = self.scaler.state_dict()
        
        path = self.output_dir / f"checkpoint_epoch_{epoch}.pt"
        torch.save(state, path)
        
        if is_best:
            best_path = self.output_dir / "best_model.pt"
            torch.save(state, best_path)
            self.logger.info(f"Saved best model at epoch {epoch} with macro AUC: {self.best_macro_auc:.4f}")
    
    def load_checkpoint(self, path: Path):
        state = torch.load(path, map_location=self.device)
        self.model.load_state_dict(state["model"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.scheduler.load_state_dict(state["scheduler"])
        self.best_macro_auc = state["best_macro_auc"]
        self.history = defaultdict(list, state["history"])
        if self.ema and "ema" in state:
            self.ema.module.load_state_dict(state["ema"])
        if self.scaler and "scaler" in state:
            self.scaler.load_state_dict(state["scaler"])
        self.logger.info(f"Loaded checkpoint from epoch {state['epoch']}")
    
    def train(self):
        self.logger.info(f"Starting training for {self.config['epochs']} epochs")
        self.logger.info(f"Model parameters: {sum(p.numel() for p in self.model.parameters()) / 1e6:.2f}M")
        
        for epoch in range(1, self.config["epochs"] + 1):
            start_time = time.time()
            
            train_results = self.train_epoch(epoch)
            val_results = self.validate(epoch)
            
            epoch_time = time.time() - start_time
            
            for k, v in train_results.items():
                self.history[f"train_{k}"].append(v)
            for k, v in val_results.items():
                self.history[f"val_{k}"].append(v)
            
            self.logger.info(
                f"Epoch {epoch}/{self.config['epochs']} ({epoch_time:.1f}s) | "
                f"Train Loss: {train_results['loss']:.4f} Macro AUC: {train_results['macro_auc']:.4f} | "
                f"Val Loss: {val_results['loss']:.4f} Macro AUC: {val_results['macro_auc']:.4f}"
            )
            
            is_best = val_results["macro_auc"] > self.best_macro_auc
            if is_best:
                self.best_macro_auc = val_results["macro_auc"]
                self.best_epoch = epoch
            
            if epoch % self.config.get("save_interval", 5) == 0 or is_best:
                self.save_checkpoint(epoch, is_best)
            
            if epoch - self.best_epoch >= self.config.get("early_stopping", 15):
                self.logger.info(f"Early stopping at epoch {epoch}")
                break
        
        self.logger.info(f"Training complete. Best macro AUC: {self.best_macro_auc:.4f} at epoch {self.best_epoch}")
        
        with open(self.output_dir / "history.json", "w") as f:
            json.dump(self.history, f, indent=2)
        
        return self.best_macro_auc


def train_fold(
    fold: int,
    train_loader,
    val_loader,
    config: Dict,
    device: torch.device,
    output_dir: Path
) -> float:
    """Train a single fold."""
    model = create_model(
        backbone=config.get("backbone", "efficientnet_b3"),
        pretrained=config.get("pretrained", True),
        feature_dim=config.get("feature_dim", 512),
        num_classes=len(LABELS),
        slice_aggregation=config.get("slice_aggregation", "attention"),
        series_fusion=config.get("series_fusion", "attention"),
        dropout=config.get("dropout", 0.2),
        in_channels=3
    )
    
    fold_dir = output_dir / f"fold_{fold}"
    trainer = Trainer(model, train_loader, val_loader, config, device, fold_dir)
    best_auc = trainer.train()
    
    return best_auc


if __name__ == "__main__":
    import sys
    sys.path.append("C:\\Coding\\rsna_knee")
    
    from src.data.synthetic_generator import generate_synthetic_dataset
    from src.data.dataloader import create_dataloaders
    
    generate_synthetic_dataset("data/synthetic", num_studies=50)
    
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
        "epochs": 5,
        "scheduler": "cosine",
        "amp": True,
        "use_ema": True,
        "ema_decay": 0.999,
        "grad_clip": 1.0,
        "log_interval": 10,
        "save_interval": 2,
        "early_stopping": 10,
    }
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    train_loader, val_loader = create_dataloaders(
        "data/synthetic", batch_size=2, num_workers=0,
        max_series=3, max_slices=16
    )
    
    output_dir = Path("outputs/test_run")
    train_fold(0, train_loader, val_loader, config, device, output_dir)