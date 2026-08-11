"""
PyTorch Dataset and DataLoader for RSNA Knee MRI
Handles multi-series loading, MIL sampling, and label management.
"""
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import random
from src.data.preprocessing import (
    load_series_slices, SeriesSelector, create_three_channel_input,
    preprocess_slice
)


LABELS = [
    "ACL", "MCL", "Medial Meniscus", "Lateral Meniscus",
    "Medial OA", "Lateral OA", "PF OA",
    "Effusion", "Synovitis", "Baker's", "Contusion", "Fracture"
]

LABEL_TO_IDX = {label: i for i, label in enumerate(LABELS)}


class KneeMRIDataset(Dataset):
    """Dataset for knee MRI studies with multi-series support."""
    
    def __init__(
        self,
        data_root: Path,
        split: str = "train",
        max_series: int = 4,
        max_slices_per_series: int = 24,
        slice_sampling: str = "uniform",
        window_method: str = "percentile",
        three_channel: bool = True,
        channel_method: str = "adjacent",
        labeled_only: bool = False,
        pseudo_labels: Optional[Dict] = None,
        transform=None,
        return_metadata: bool = False
    ):
        self.data_root = Path(data_root)
        self.split = split
        self.max_series = max_series
        self.max_slices = max_slices_per_series
        self.slice_sampling = slice_sampling
        self.window_method = window_method
        self.three_channel = three_channel
        self.channel_method = channel_method
        self.transform = transform
        self.return_metadata = return_metadata
        
        if split == "train":
            self.df = pd.read_csv(self.data_root / "train.csv")
            self.series_df = pd.read_csv(self.data_root / "train_series.csv")
            self.series_dir = self.data_root / "train_series"
        else:
            self.df = pd.read_csv(self.data_root / "test.csv")
            self.series_df = pd.read_csv(self.data_root / "test_series.csv")
            self.series_dir = self.data_root / "test_series"
        
        self.study_uids = self.df["StudyInstanceUID"].tolist()
        
        if labeled_only and split == "train":
            labeled_mask = self.df[LABELS[0]] != -1
            self.df = self.df[labeled_mask].reset_index(drop=True)
            self.study_uids = self.df["StudyInstanceUID"].tolist()
        
        self.pseudo_labels = pseudo_labels or {}
        
        self.series_by_study = self.series_df.groupby("StudyInstanceUID").apply(
            lambda x: x.to_dict("records"), include_groups=False
        ).to_dict()
    
    def __len__(self) -> int:
        return len(self.study_uids)
    
    def _get_labels(self, study_uid: str) -> np.ndarray:
        """Get labels for a study (true or pseudo)."""
        if study_uid in self.pseudo_labels:
            return np.array(self.pseudo_labels[study_uid], dtype=np.float32)
        
        row = self.df[self.df["StudyInstanceUID"] == study_uid].iloc[0]
        labels = row[LABELS].values.astype(np.float32)
        
        if np.any(labels == -1):
            return np.full(len(LABELS), -1.0, dtype=np.float32)
        return labels
    
    def _load_study_series(self, study_uid: str) -> List[np.ndarray]:
        """Load all selected series for a study."""
        series_meta = self.series_by_study.get(study_uid, [])
        if not series_meta:
            return []
        
        selected = SeriesSelector.select_series(series_meta, self.max_series)
        
        series_arrays = []
        for meta in selected:
            series_dir = self.series_dir / study_uid / meta["SeriesInstanceUID"]
            if not series_dir.exists():
                continue
            try:
                slices = load_series_slices(
                    series_dir,
                    max_slices=self.max_slices,
                    sampling=self.slice_sampling,
                    window_method=self.window_method
                )
                if self.three_channel:
                    slices = create_three_channel_input(slices, self.channel_method)
                series_arrays.append(slices)
            except Exception as e:
                print(f"Warning: Failed to load {series_dir}: {e}")
                continue
        
        return series_arrays
    
    def __getitem__(self, idx: int) -> Dict:
        study_uid = self.study_uids[idx]
        labels = self._get_labels(study_uid)
        series_arrays = self._load_study_series(study_uid)
        
        if not series_arrays:
            dummy = np.zeros((1, self.max_slices, 384, 384, 3), dtype=np.float32)
            series_arrays = [dummy]
        
        if self.transform:
            series_arrays = [self.transform(s) for s in series_arrays]
        
        series_tensors = []
        for s in series_arrays:
            if s.ndim == 4:  # (N, H, W, C)
                series_tensors.append(torch.from_numpy(s).permute(0, 3, 1, 2))
            elif s.ndim == 5:  # (1, N, H, W, C) - batched
                series_tensors.append(torch.from_numpy(s.squeeze(0)).permute(0, 3, 1, 2))
            else:
                raise ValueError(f"Unexpected shape: {s.shape}")
        
        output = {
            "study_uid": study_uid,
            "series": series_tensors,
            "labels": torch.from_numpy(labels),
            "num_series": len(series_tensors),
        }
        
        if self.return_metadata:
            output["metadata"] = {
                "study_uid": study_uid,
                "has_true_labels": not np.any(labels == -1),
            }
        
        return output


def collate_fn(batch: List[Dict]) -> Dict:
    """Custom collate for variable number of series per study."""
    study_uids = [b["study_uid"] for b in batch]
    labels = torch.stack([b["labels"] for b in batch])
    num_series = [b["num_series"] for b in batch]
    
    max_series = max(len(b["series"]) for b in batch)
    max_slices = max(s.shape[0] for b in batch for s in b["series"])
    
    batch_size = len(batch)
    padded_series = torch.zeros(batch_size, max_series, max_slices, 3, 384, 384)
    series_mask = torch.zeros(batch_size, max_series, dtype=torch.bool)
    slice_masks = torch.zeros(batch_size, max_series, max_slices, dtype=torch.bool)
    
    for i, b in enumerate(batch):
        for j, series in enumerate(b["series"]):
            n_slices = series.shape[0]
            padded_series[i, j, :n_slices] = series
            series_mask[i, j] = True
            slice_masks[i, j, :n_slices] = True
    
    output = {
        "study_uids": study_uids,
        "series": padded_series,
        "series_mask": series_mask,
        "slice_masks": slice_masks,
        "labels": labels,
        "num_series": torch.tensor(num_series),
    }
    
    if "metadata" in batch[0]:
        output["metadata"] = [b["metadata"] for b in batch]
    
    return output


def get_class_weights(labels_df: pd.DataFrame, labeled_only: bool = True) -> torch.Tensor:
    """Calculate positive class weights for BCEWithLogitsLoss."""
    if labeled_only:
        df = labels_df[labels_df[LABELS[0]] != -1]
    else:
        df = labels_df
    
    pos_weights = []
    for label in LABELS:
        pos = (df[label] == 1).sum()
        neg = (df[label] == 0).sum()
        if pos > 0:
            pos_weights.append(neg / pos)
        else:
            pos_weights.append(1.0)
    
    return torch.tensor(pos_weights, dtype=torch.float32)


def get_weighted_sampler(dataset) -> WeightedRandomSampler:
    """Create sampler that oversamples studies with rare findings."""
    # Handle Subset
    if hasattr(dataset, 'dataset'):
        base_dataset = dataset.dataset
        indices = dataset.indices
    else:
        base_dataset = dataset
        indices = list(range(len(dataset)))
    
    weights = np.ones(len(indices))
    
    for idx, i in enumerate(indices):
        study_uid = base_dataset.study_uids[i]
        labels = base_dataset._get_labels(study_uid)
        if np.any(labels == -1):
            continue
        
        rare_findings = (labels == 1) & (np.array([0.12, 0.08, 0.25, 0.15, 0.30, 0.18, 0.22, 0.35, 0.12, 0.05, 0.08, 0.03]) < 0.15)
        if np.any(rare_findings):
            weights[idx] = 3.0
    
    return WeightedRandomSampler(weights, len(weights), replacement=True)


def create_dataloaders(
    data_root: Union[str, Path],
    batch_size: int = 4,
    num_workers: int = 4,
    max_series: int = 4,
    max_slices: int = 24,
    labeled_fraction: float = 1.0,
    use_pseudo_labels: bool = False,
    pseudo_label_path: Optional[str] = None,
    **kwargs
) -> Tuple[DataLoader, DataLoader]:
    """Create train and validation dataloaders."""
    data_root = Path(data_root)
    
    pseudo_labels = None
    if use_pseudo_labels and pseudo_label_path:
        pseudo_df = pd.read_csv(pseudo_label_path)
        pseudo_labels = pseudo_df.set_index("StudyInstanceUID")[LABELS].to_dict("index")
    
    train_dataset = KneeMRIDataset(
        data_root, split="train",
        max_series=max_series,
        max_slices_per_series=max_slices,
        pseudo_labels=pseudo_labels,
        **kwargs
    )
    
    train_size = int(0.85 * len(train_dataset))
    val_size = len(train_dataset) - train_size
    train_indices, val_indices = torch.utils.data.random_split(
        range(len(train_dataset)), [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    train_subset = torch.utils.data.Subset(train_dataset, train_indices.indices)
    val_subset = torch.utils.data.Subset(train_dataset, val_indices.indices)
    
    sampler = get_weighted_sampler(train_subset)
    
    train_loader = DataLoader(
        train_subset, batch_size=batch_size,
        sampler=sampler,
        num_workers=num_workers, collate_fn=collate_fn, pin_memory=True, drop_last=True
    )
    
    val_loader = DataLoader(
        val_subset, batch_size=batch_size,
        shuffle=False, num_workers=num_workers,
        collate_fn=collate_fn, pin_memory=True
    )
    
    return train_loader, val_loader


def create_test_dataloader(
    data_root: Union[str, Path],
    batch_size: int = 4,
    num_workers: int = 4,
    max_series: int = 4,
    max_slices: int = 24,
    **kwargs
) -> DataLoader:
    """Create test dataloader."""
    data_root = Path(data_root)
    
    test_dataset = KneeMRIDataset(
        data_root, split="test",
        max_series=max_series,
        max_slices_per_series=max_slices,
        **kwargs
    )
    
    return DataLoader(
        test_dataset, batch_size=batch_size,
        shuffle=False, num_workers=num_workers,
        collate_fn=collate_fn, pin_memory=True
    )


if __name__ == "__main__":
    from src.data.synthetic_generator import generate_synthetic_dataset
    generate_synthetic_dataset("data/synthetic", num_studies=20)
    
    train_loader, val_loader = create_dataloaders(
        "data/synthetic", batch_size=2, num_workers=0
    )
    
    for batch in train_loader:
        print(f"Series shape: {batch['series'].shape}")
        print(f"Labels shape: {batch['labels'].shape}")
        print(f"Series mask: {batch['series_mask'].shape}")
        print(f"Labels: {batch['labels'][0]}")
        break