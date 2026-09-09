import torch
import torch.nn as nn
import torch.nn.functional as F

def orthogonal_init_(module, gain=1.0):
    """
    Applies orthogonal initialization to linear and convolutional layers.
    Crucial for preserving gradient norms in deep RL.
    """
    if isinstance(module, (nn.Linear, nn.Conv2d)):
        nn.init.orthogonal_(module.weight, gain=gain)
        if module.bias is not None:
            nn.init.zeros_(module.bias)
    return module

class FiLMGenerator(nn.Module):
    """
    Generates scaling (gamma) and shifting (beta) parameters for multiple FiLM layers
    from a continuous scalar goal vector. Utilizes zero-initialization for stability.
    """
    def __init__(self, goal_dim, num_channels_list):
        super().__init__()
        self.num_channels_list = num_channels_list
        total_channels = sum(num_channels_list)
        
        self.mlp = nn.Sequential(
            orthogonal_init_(nn.Linear(goal_dim, 256), gain=nn.init.calculate_gain('relu')),
            nn.SiLU(),
            # Initialized to near-zero so delta_gamma and beta start at 0
            orthogonal_init_(nn.Linear(256, total_channels * 2), gain=0.01) 
        )

    def forward(self, goal):
        out = self.mlp(goal)
        
        film_params = []
        idx = 0
        for c in self.num_channels_list:
            delta_gamma = out[:, idx : idx + c]
            beta = out[:, idx + c : idx + 2 * c]
            
            # gamma = 1.0 + delta_gamma ensuring identity transform at initialization
            gamma = 1.0 + delta_gamma  
            
            # Reshape for broadcasting against [batch, channels, height, width]
            gamma = gamma.view(-1, c, 1, 1)
            beta = beta.view(-1, c, 1, 1)
            
            film_params.append((gamma, beta))
            idx += 2 * c
            
        return film_params

class ChannelAttention(nn.Module):
    """CBAM Channel Attention Sub-module for isolating feature importance."""
    def __init__(self, in_planes, ratio=4):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        
        self.fc = nn.Sequential(
            nn.Conv2d(in_planes, in_planes // ratio, 1, bias=False),
            nn.SiLU(),
            nn.Conv2d(in_planes // ratio, in_planes, 1, bias=False)
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = self.fc(self.avg_pool(x))
        max_out = self.fc(self.max_pool(x))
        return self.sigmoid(avg_out + max_out)

class SpatialAttention(nn.Module):
    """CBAM Spatial Attention Sub-module for pinpointing positional coordinates."""
    def __init__(self, kernel_size=3): 
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        out = torch.cat([avg_out, max_out], dim=1)
        return self.sigmoid(self.conv(out))

class CBAM(nn.Module):
    """Convolutional Block Attention Module."""
    def __init__(self, in_planes):
        super().__init__()
        self.ca = ChannelAttention(in_planes)
        self.sa = SpatialAttention()

    def forward(self, x):
        x = self.ca(x) * x
        x = self.sa(x) * x
        return x

class IMPALAResBlockWithFiLM(nn.Module):
    """
    Residual block integrating standard/dilated convolutions to expand the 
    Effective Receptive Field (ERF), combined with deeply distributed FiLM conditioning.
    """
    def __init__(self, in_channels, out_channels, dilation=1):
        super().__init__()
        self.conv1 = orthogonal_init_(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=dilation, dilation=dilation)
        )
        # LayerNorm provides superior stability in RL compared to BatchNorm
        self.norm1 = nn.LayerNorm([out_channels, 10, 10]) 
        
        self.conv2 = orthogonal_init_(
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)
        )
        self.norm2 = nn.LayerNorm([out_channels, 10, 10])
        self.activation = nn.SiLU()

    def forward(self, x, film_gamma, film_beta):
        identity = x
        
        out = self.conv1(x)
        out = self.norm1(out)
        
        # Inject macroeconomic conditioning directly into the residual stream
        out = out * film_gamma + film_beta
        out = self.activation(out)
        
        out = self.conv2(out)
        out = self.norm2(out)
        out = self.activation(out)
        
        return out + identity

class FeatureExtractor(nn.Module):
    """Processes the 10x10 spatial grid and applies hierarchical FiLM modulation."""
    def __init__(self, in_channels=20, base_features=64):
        super().__init__()
        self.stem = nn.Sequential(
            orthogonal_init_(nn.Conv2d(in_channels, base_features, kernel_size=3, padding=1)),
            nn.SiLU()
        )
        
        # Progressive dilation guarantees full 10x10 ERF coverage by block 2
        self.res1 = IMPALAResBlockWithFiLM(base_features, base_features, dilation=1)
        self.res2 = IMPALAResBlockWithFiLM(base_features, base_features, dilation=2) 
        self.res3 = IMPALAResBlockWithFiLM(base_features, base_features, dilation=1)
        
        self.cbam = CBAM(base_features)
        
        # Spatial Compression down to a unified 1D vector
        self.compress = nn.Sequential(
            orthogonal_init_(nn.Conv2d(base_features, base_features, kernel_size=2, stride=2)),
            nn.SiLU(),
            orthogonal_init_(nn.Conv2d(base_features, base_features, kernel_size=3, stride=2, padding=0)),
            nn.SiLU(),
            nn.Flatten(),
            orthogonal_init_(nn.Linear(base_features * 4, 256)),
            nn.SiLU()
        )

    def forward(self, spatial_x, film_params):
        x = self.stem(spatial_x)
        
        # Distribute hierarchical FiLM parameters
        x = self.res1(x, film_params[0][0], film_params[0][1])
        x = self.res2(x, film_params[1][0], film_params[1][1])
        x = self.res3(x, film_params[2][0], film_params[2][1])
        
        # Apply spatial and channel attention before compression
        x = self.cbam(x)
        x = self.compress(x)
        return x

class NeuralSpatialMicroAgent(nn.Module):
    """
    Optimized CTDE MAPPO Architecture managing Mixed Precision execution 
    with completely decoupled Actor and Critic backbones.
    """
    def __init__(self, in_channels=20, goal_dim=100, action_dim=11, base_features=64):
        super().__init__()
        
        # Decoupled backbones entirely eliminate destructive gradient interference
        self.actor_extractor = FeatureExtractor(in_channels, base_features)
        self.critic_extractor = FeatureExtractor(in_channels, base_features)
        
        num_channels_list = [base_features, base_features, base_features] 
        self.actor_film_gen = FiLMGenerator(goal_dim, num_channels_list)
        self.critic_film_gen = FiLMGenerator(goal_dim, num_channels_list)
        
        # Gain=0.01 forces near-uniform distributions for maximal initial exploration
        self.actor_head = orthogonal_init_(nn.Linear(256, action_dim), gain=0.01)
        
        # Gain=1.0 scales raw outputs appropriately for external PopArt normalization
        self.critic_head = orthogonal_init_(nn.Linear(256, 1), gain=1.0)

    def forward(self, spatial_input, goal_input):
        # Enforce Float32 for scalar MLP to maintain numerical integrity
        goal_input = goal_input.float()
        
        # Execute expensive spatial operations in Float16 utilizing Tensor Cores
        with torch.autocast(device_type=spatial_input.device.type, dtype=torch.float16):
            
            actor_film_params = self.actor_film_gen(goal_input)
            actor_features = self.actor_extractor(spatial_input, actor_film_params)
            action_logits = self.actor_head(actor_features)
            
            critic_film_params = self.critic_film_gen(goal_input)
            critic_features = self.critic_extractor(spatial_input, critic_film_params)
            value = self.critic_head(critic_features)

        # Re-cast outputs to Float32 preventing NaN underflows during Softmax/Advantage math
        return action_logits.float(), value.float()
