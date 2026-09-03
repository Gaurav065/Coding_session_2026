import torch
import torch.nn as nn
import torch.nn.functional as F

BOARD_SIZE = 10

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

class KaggricultureLSTM(nn.Module):
    # Action Dim reduced to 13 (Removed Tomato, Goose, Egg)
    def __init__(self, scalar_dim=50, spatial_channels=4, action_dim=13, hidden_size=256):
        super().__init__()
        self.hidden_size = hidden_size
        
        # Spatial Stream
        self.spatial_stem = nn.Sequential(nn.Conv2d(spatial_channels, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
        self.res1 = ResBlock(32)
        self.res2 = ResBlock(32)
        self.spatial_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # Scalar Stream
        self.scalar_mlp = nn.Sequential(
            nn.Linear(scalar_dim, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Linear(128, 128), nn.LayerNorm(128), nn.ReLU()
        )
        
        # Feature Fusion
        self.fusion = nn.Sequential(nn.Linear(32 + 128, 256), nn.LayerNorm(256), nn.ReLU())
        
        # LSTM Memory Bank
        self.lstm = nn.LSTM(input_size=256, hidden_size=hidden_size, num_layers=1, batch_first=True)
        
        # Heads
        self.actor_head = nn.Sequential(nn.Linear(hidden_size, action_dim), nn.Sigmoid())
        self.critic_head = nn.Linear(hidden_size, 1)

    def forward(self, spatial, scalar, hidden_state=None):
        is_sequence = len(spatial.shape) == 5
        
        if is_sequence:
            B, S, C, H, W = spatial.shape
            spatial = spatial.view(B*S, C, H, W)
            scalar = scalar.view(B*S, -1)
            
        x_sp = self.spatial_pool(self.res2(self.res1(self.spatial_stem(spatial)))).view(spatial.size(0), -1)
        x_sc = self.scalar_mlp(scalar)
        fused_features = self.fusion(torch.cat([x_sp, x_sc], dim=1))
        
        if is_sequence:
            fused_features = fused_features.view(B, S, -1)
        else:
            fused_features = fused_features.unsqueeze(1)
            
        lstm_out, hidden_state = self.lstm(fused_features, hidden_state)
        
        if is_sequence:
            lstm_out = lstm_out.view(B*S, -1)
        else:
            lstm_out = lstm_out.squeeze(1)
            
        actions = self.actor_head(lstm_out)
        values = self.critic_head(lstm_out)
        
        if is_sequence:
            actions = actions.view(B, S, -1)
            values = values.view(B, S, -1)
            
        return actions, values, hidden_state
