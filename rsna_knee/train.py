#!/usr/bin/env python
"""
Main training script for RSNA Knee Abnormality Detection.
Run locally for development, or on Kaggle for full training.
"""
import argparse
import json
import sys
from pathlib import Path

import torch
import numpy as np

sys.path.append(str(Path(__file__).parent / "src"))

from data.synthetic_generator import generate_synthetic_dataset
from data.dataloader import create_dataloaders
from models.model import create_model
from training.trainer import train_fold
from training.inference import run_inference_pipeline
from utils.nlp_labeler import create_pseudo_labels, calibrate_pseudo_labels


def parse_args():
    parser = argparse.ArgumentParser(description="RSNA Knee Abnormality Detection")
    parser.add_argument("--mode", choices=["generate", "train", "inference", "pseudo"], default="train")
    parser.add_argument("--data-root", type=str, default="data/synthetic")
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument("--config", type=str, default="configs/train_config.json")
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--num-folds", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    
    print(f"Using device: {device}")
    
    with open(args.config) as f:
        config = json.load(f)
    
    config.update({
        "batch_size": args.batch_size,
        "epochs": args.epochs,
    })
    
    data_root = Path(args.data_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    
    if args.mode == "generate":
        print("Generating synthetic dataset...")
        generate_synthetic_dataset(
            str(data_root),
            num_studies=200,
            labeled_fraction=0.15,
            seed=args.seed
        )
        print("Done!")
        
    elif args.mode == "pseudo":
        print("Generating pseudo-labels from reports...")
        create_pseudo_labels(
            data_root / "train.csv",
            output_dir / "pseudo_labels.csv",
            confidence_threshold=0.85
        )
        calibrate_pseudo_labels(
            data_root / "train.csv",
            output_dir / "pseudo_labels.csv",
            output_dir / "pseudo_labels_calibrated.csv"
        )
        print("Done!")
        
    elif args.mode == "train":
        print(f"Training fold {args.fold}...")
        train_loader, val_loader = create_dataloaders(
            data_root,
            batch_size=config["batch_size"],
            num_workers=4,
            max_series=config["max_series"],
            max_slices=config["max_slices"],
            use_pseudo_labels=config.get("use_pseudo_labels", False),
            pseudo_label_path=str(output_dir / "pseudo_labels_calibrated.csv") if config.get("use_pseudo_labels") else None,
        )
        
        fold_dir = output_dir / f"fold_{args.fold}"
        auc = train_fold(args.fold, train_loader, val_loader, config, device, output_dir)
        print(f"Fold {args.fold} best AUC: {auc:.4f}")
        
    elif args.mode == "inference":
        print("Running inference...")
        fold_weights = {i: 1.0 for i in range(args.num_folds)}
        run_inference_pipeline(
            data_root,
            output_dir,
            output_dir / "submission",
            config,
            fold_weights=fold_weights,
            use_tta=True,
        )
        print("Done!")


if __name__ == "__main__":
    main()