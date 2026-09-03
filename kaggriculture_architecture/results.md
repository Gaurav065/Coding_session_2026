# BC Training Results: custom_bc_master.pth

**Architecture**: `KaggricultureResNet`
**Dataset**: 810 Grandmaster replays (198,306 action frames)
**Epochs**: 30
**Batch Size**: 256
**Optimizer**: AdamW (lr=1e-3, weight_decay=1e-5)
**Loss Function**: MSELoss

## Training Progression (Top Epochs)
- **Epoch 01**: Train Loss 0.0174 | Val Loss 0.0280
- **Epoch 10**: Train Loss 0.0061 | Val Loss 0.0078
- **Epoch 20**: Train Loss 0.0048 | Val Loss 0.0085
- **Epoch 29 (BEST)**: Train Loss 0.0042 | Val Loss 0.0066

## Conclusion
The model converged very smoothly without significant overfitting. The validation loss stabilized at ~`0.0066`, indicating the network has successfully learned to map the combined 50-dimensional scalar state and 10x10 spatial grid to the Grandmaster target action distributions. 

The best weights have been saved to `custom_bc_master.pth`.
