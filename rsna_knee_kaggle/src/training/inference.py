"""
Inference and Submission Pipeline for RSNA Knee Competition
Handles TTA, model ensembling, and submission file generation.
"""
import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from tqdm import tqdm

from src.models.model import KneeAbnormalityModel, create_model
from src.data.dataloader import create_test_dataloader, LABELS, collate_fn
from src.data.preprocessing import load_series_slices, SeriesSelector, create_three_channel_input


def predict_single_model(
    model: KneeAbnormalityModel,
    dataloader,
    device: torch.device,
    tta: bool = True
) -> Tuple[List[str], np.ndarray]:
    """Run inference on test set with optional TTA."""
    model.eval()
    all_uids = []
    all_probs = []
    
    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Inference"):
            series = batch["series"].to(device, non_blocking=True)
            series_mask = batch["series_mask"].to(device, non_blocking=True)
            slice_masks = batch["slice_masks"].to(device, non_blocking=True)
            uids = batch["study_uids"]
            
            logits, _, _ = model(series, series_mask, slice_masks)
            probs = torch.sigmoid(logits).cpu().numpy()
            
            if tta:
                series_flipped = torch.flip(series, dims=[-1])
                logits_flip, _, _ = model(series_flipped, series_mask, slice_masks)
                probs_flip = torch.sigmoid(logits_flip).cpu().numpy()
                probs = (probs + probs_flip) / 2
            
            all_uids.extend(uids)
            all_probs.append(probs)
    
    return all_uids, np.vstack(all_probs)


def load_ensemble_models(
    model_paths: List[Path],
    config: Dict,
    device: torch.device
) -> List[KneeAbnormalityModel]:
    """Load multiple models for ensembling."""
    models = []
    for path in model_paths:
        model = create_model(
            backbone=config.get("backbone", "efficientnet_b3"),
            pretrained=False,
            feature_dim=config.get("feature_dim", 512),
            num_classes=len(LABELS),
            slice_aggregation=config.get("slice_aggregation", "attention"),
            series_fusion=config.get("series_fusion", "attention"),
            dropout=config.get("dropout", 0.2),
            in_channels=3
        )
        state = torch.load(path, map_location=device)
        model.load_state_dict(state["model"] if "model" in state else state)
        model.to(device)
        model.eval()
        models.append(model)
    return models


def predict_ensemble(
    models: List[KneeAbnormalityModel],
    dataloader,
    device: torch.device,
    weights: Optional[List[float]] = None,
    tta: bool = True
) -> Tuple[List[str], np.ndarray]:
    """Run ensemble inference with weighted averaging."""
    if weights is None:
        weights = [1.0] * len(models)
    weights = np.array(weights) / np.sum(weights)
    
    all_uids = None
    ensemble_probs = None
    
    for model, weight in zip(models, weights):
        uids, probs = predict_single_model(model, dataloader, device, tta)
        if all_uids is None:
            all_uids = uids
            ensemble_probs = probs * weight
        else:
            ensemble_probs += probs * weight
    
    return all_uids, ensemble_probs


def generate_submission(
    uids: List[str],
    probs: np.ndarray,
    output_path: Path,
    sample_submission_path: Optional[Path] = None
):
    """Generate submission.csv in competition format."""
    sub_df = pd.DataFrame(probs, columns=LABELS)
    sub_df.insert(0, "StudyInstanceUID", uids)
    
    if sample_submission_path and sample_submission_path.exists():
        sample = pd.read_csv(sample_submission_path)
        expected_uids = sample["StudyInstanceUID"].tolist()
        sub_df = sub_df.set_index("StudyInstanceUID").reindex(expected_uids).reset_index()
        assert sub_df["StudyInstanceUID"].isna().sum() == 0, "Missing UIDs in predictions"
    
    sub_df.to_csv(output_path, index=False)
    print(f"Submission saved to {output_path}")
    print(f"Shape: {sub_df.shape}")
    print(f"Mean probabilities per class:")
    for label in LABELS:
        print(f"  {label}: {sub_df[label].mean():.4f}")
    
    return sub_df


def run_inference_pipeline(
    data_root: Path,
    model_dir: Path,
    output_dir: Path,
    config: Dict,
    fold_weights: Optional[Dict[int, float]] = None,
    use_tta: bool = True,
    batch_size: int = 4,
    num_workers: int = 4
):
    """Complete inference pipeline for competition submission."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    test_loader = create_test_dataloader(
        data_root, batch_size=batch_size, num_workers=num_workers,
        max_series=config.get("max_series", 4),
        max_slices=config.get("max_slices", 24)
    )
    
    if fold_weights:
        model_paths = []
        weights = []
        for fold, weight in fold_weights.items():
            model_path = model_dir / f"fold_{fold}" / "best_model.pt"
            if model_path.exists():
                model_paths.append(model_path)
                weights.append(weight)
            else:
                print(f"Warning: Model not found: {model_path}")
        
        if not model_paths:
            raise ValueError("No valid model paths found")
        
        models = load_ensemble_models(model_paths, config, device)
        uids, probs = predict_ensemble(models, test_loader, device, weights, use_tta)
    else:
        model_path = model_dir / "best_model.pt"
        model = create_model(
            backbone=config.get("backbone", "efficientnet_b3"),
            pretrained=False,
            feature_dim=config.get("feature_dim", 512),
            num_classes=len(LABELS),
            slice_aggregation=config.get("slice_aggregation", "attention"),
            series_fusion=config.get("series_fusion", "attention"),
            dropout=config.get("dropout", 0.2),
            in_channels=3
        )
        state = torch.load(model_path, map_location=device)
        model.load_state_dict(state["model"] if "model" in state else state)
        model.to(device)
        uids, probs = predict_single_model(model, test_loader, device, use_tta)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    submission_path = output_dir / "submission.csv"
    sample_path = data_root / "sample_submission.csv"
    
    generate_submission(uids, probs, submission_path, sample_path)
    
    return submission_path


def calibrate_predictions(
    probs: np.ndarray,
    calibration_data: Dict[str, np.ndarray]
) -> np.ndarray:
    """Apply Platt scaling / isotonic regression per class."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression
    
    calibrated = np.zeros_like(probs)
    for i in range(probs.shape[1]):
        if i in calibration_data:
            y_true, y_pred = calibration_data[i]
            calibrator = CalibratedClassifierCV(LogisticRegression(), cv=3)
            calibrator.fit(y_pred.reshape(-1, 1), y_true)
            calibrated[:, i] = calibrator.predict_proba(probs[:, i].reshape(-1, 1))[:, 1]
        else:
            calibrated[:, i] = probs[:, i]
    return calibrated


def pseudo_label_generation(
    data_root: Path,
    model_dir: Path,
    config: Dict,
    output_path: Path,
    confidence_threshold: float = 0.9
):
    """Generate high-confidence pseudo-labels for training set."""
    from src.data.dataloader import KneeMRIDataset, create_dataloaders
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    train_dataset = KneeMRIDataset(data_root, split="train", labeled_only=False)
    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=4, shuffle=False, num_workers=4, collate_fn=collate_fn
    )
    
    model = create_model(
        backbone=config.get("backbone", "efficientnet_b3"),
        pretrained=False,
        feature_dim=config.get("feature_dim", 512),
        num_classes=len(LABELS),
        slice_aggregation=config.get("slice_aggregation", "attention"),
        series_fusion=config.get("series_fusion", "attention"),
        dropout=config.get("dropout", 0.2),
        in_channels=3
    )
    state = torch.load(model_dir / "best_model.pt", map_location=device)
    model.load_state_dict(state["model"] if "model" in state else state)
    model.to(device)
    model.eval()
    
    all_uids = []
    all_probs = []
    
    with torch.no_grad():
        for batch in tqdm(train_loader, desc="Pseudo-labeling"):
            series = batch["series"].to(device)
            series_mask = batch["series_mask"].to(device)
            slice_masks = batch["slice_masks"].to(device)
            uids = batch["study_uids"]
            
            logits, _, _ = model(series, series_mask, slice_masks)
            probs = torch.sigmoid(logits).cpu().numpy()
            
            all_uids.extend(uids)
            all_probs.append(probs)
    
    all_probs = np.vstack(all_probs)
    
    pseudo_df = pd.DataFrame(all_probs, columns=LABELS)
    pseudo_df.insert(0, "StudyInstanceUID", all_uids)
    
    high_conf = (all_probs > confidence_threshold) | (all_probs < (1 - confidence_threshold))
    pseudo_df_high = pseudo_df.copy()
    for label in LABELS:
        pseudo_df_high.loc[~high_conf[:, LABELS.index(label)], label] = -1
    
    pseudo_df.to_csv(output_path, index=False)
    pseudo_df_high.to_csv(output_path.with_name("pseudo_labels_high_conf.csv"), index=False)
    
    print(f"Pseudo-labels saved to {output_path}")
    print(f"High-confidence pseudo-labels saved to {output_path.with_name('pseudo_labels_high_conf.csv')}")


if __name__ == "__main__":
    import sys
    sys.path.append("C:\\Coding\\rsna_knee")
    
    config = {
        "backbone": "efficientnet_b0",
        "feature_dim": 256,
        "slice_aggregation": "attention",
        "series_fusion": "attention",
        "dropout": 0.2,
        "max_series": 3,
        "max_slices": 16,
    }
    
    data_root = Path("data/synthetic")
    model_dir = Path("outputs/test_run/fold_0")
    output_dir = Path("outputs/submission")
    
    if not (model_dir / "best_model.pt").exists():
        print("No trained model found. Run training first.")
    else:
        run_inference_pipeline(data_root, model_dir, output_dir, config)