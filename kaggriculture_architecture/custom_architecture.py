import torch
import torch.nn as nn
import torch.nn.functional as F

class ResBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        res = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return F.relu(x + res)

class KaggricultureResNet(nn.Module):
    def __init__(self, scalar_dim=50, spatial_channels=4, action_dim=17):
        super().__init__()
        
        # Spatial Stream (ResNet)
        self.spatial_stem = nn.Sequential(
            nn.Conv2d(spatial_channels, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU()
        )
        self.res1 = ResBlock(32)
        self.res2 = ResBlock(32)
        self.spatial_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # Scalar Stream (MLP)
        self.scalar_mlp = nn.Sequential(
            nn.Linear(scalar_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.LayerNorm(128),
            nn.ReLU()
        )
        
        # Fusion Layer
        self.fusion = nn.Sequential(
            nn.Linear(32 + 128, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, action_dim),
            nn.Sigmoid() # Binds our 17D outputs to [0, 1] exactly like SB3
        )

    def forward(self, spatial, scalar):
        # 1. Process 10x10 Farm Grid
        x_sp = self.spatial_stem(spatial)
        x_sp = self.res1(x_sp)
        x_sp = self.res2(x_sp)
        x_sp = self.spatial_pool(x_sp).view(x_sp.size(0), -1)
        
        # 2. Process Bank Balance / Prices
        x_sc = self.scalar_mlp(scalar)
        
        # 3. Fuse and predict actions
        combined = torch.cat([x_sp, x_sc], dim=1)
        actions = self.fusion(combined)
        return actions
