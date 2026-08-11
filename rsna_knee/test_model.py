import sys
sys.path.append('src')
import torch
from models.model import create_model
from data.dataloader import create_dataloaders

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")

model = create_model(
    backbone="efficientnet_b0",
    pretrained=False,
    feature_dim=256,
    num_classes=12,
    slice_aggregation="attention",
    series_fusion="attention",
    dropout=0.2
).to(device)

train_loader, val_loader = create_dataloaders(
    'data/synthetic', batch_size=2, num_workers=0,
    max_series=3, max_slices=16
)

batch = next(iter(train_loader))
series = batch["series"].to(device)
series_mask = batch["series_mask"].to(device)
slice_masks = batch["slice_masks"].to(device)

print(f"Input series shape: {series.shape}")

logits, series_feats, study_attn = model(series, series_mask, slice_masks)
print(f"Logits shape: {logits.shape}")
print(f"Series features: {len(series_feats)} x {series_feats[0].shape}")
print(f"Study attention: {study_attn.shape if study_attn is not None else None}")
print(f"Parameters: {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M")

print("Model test successful")