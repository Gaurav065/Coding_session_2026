import sys
sys.path.append('src')
from data.dataloader import create_dataloaders

train_loader, val_loader = create_dataloaders('data/synthetic', batch_size=2, num_workers=0, max_series=3, max_slices=16)
batch = next(iter(train_loader))
print(f'Series shape: {batch["series"].shape}')
print(f'Labels shape: {batch["labels"].shape}')
print(f'Series mask: {batch["series_mask"].shape}')
print(f'Slice masks: {batch["slice_masks"].shape}')
print('Dataloader test successful')