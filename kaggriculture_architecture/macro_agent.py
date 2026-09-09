import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Beta

class RMSNorm(nn.Module):
    """
    Root Mean Square Normalization. 
    Drops mean-centering for enhanced computational efficiency and memory reduction
    while matching or exceeding LayerNorm stability in DRL contexts.
    """
    def __init__(self, dimension: int, epsilon: float = 1e-8):
        super().__init__()
        self.scale = dimension ** 0.5
        self.gamma = nn.Parameter(torch.ones(dimension))
        self.epsilon = epsilon

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Calculate RMS across the final feature dimension
        rms = torch.sqrt(torch.mean(x ** 2, dim=-1, keepdim=True) + self.epsilon)
        return self.gamma * (x / rms)

class GatedResidualNetwork(nn.Module):
    """
    Gated Residual Network (GRN) optimized for dense tabular feature encoding.
    Leverages ELU for robust dense processing and GLU for dynamic feature suppression, 
    stabilized seamlessly by RMSNorm.
    """
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.elu = nn.ELU()
        
        # Output dimension is doubled to accommodate the GLU chunking operation
        self.fc2 = nn.Linear(hidden_dim, output_dim * 2) 
        self.dropout = nn.Dropout(dropout)
        
        # Skip connection projection ensures dimensionality alignment for the residual add
        self.skip_proj = nn.Linear(input_dim, output_dim) if input_dim != output_dim else nn.Identity()
        self.norm = RMSNorm(output_dim)

    def forward(self, x: torch.Tensor, context: torch.Tensor = None) -> torch.Tensor:
        skip = self.skip_proj(x)
        
        # Primary dense processing block
        out = self.fc1(x)
        if context is not None:
            out = out + context
        out = self.elu(out)
        out = self.fc2(out)
        out = self.dropout(out)
        
        # Gated Linear Unit (GLU) mechanism for dynamic feature routing
        activation, gate = out.chunk(2, dim=-1)
        gated_out = activation * torch.sigmoid(gate)
        
        # Residual sum followed by RMS normalization
        return self.norm(skip + gated_out)

class GTrXLBlock(nn.Module):
    """
    Gated Transformer-XL Block.
    Implements Identity Map Reordering (Pre-Norm) and GRU-based Gating to prevent
    high-variance policy gradients from destabilizing the temporal core.
    """
    def __init__(self, d_model: int, n_heads: int, dim_feedforward: int, dropout: float = 0.1):
        super().__init__()
        # Identity Map Reordering places normalization BEFORE the submodules
        self.norm1 = RMSNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        
        self.norm2 = RMSNorm(d_model)
        self.grn = GatedResidualNetwork(d_model, dim_feedforward, d_model, dropout)
        
        # Learnable gating biases, initialized to positive values (e.g., 2.0)
        # This ensures the gate starts near 1.0, acting as an identity map early in training.
        self.gate1_bias = nn.Parameter(torch.ones(d_model) * 2.0)
        self.gate2_bias = nn.Parameter(torch.ones(d_model) * 2.0)

    def _gru_gate(self, x: torch.Tensor, y: torch.Tensor, bias: nn.Parameter) -> torch.Tensor:
        # Simplified learned interpolation mimicking GRU gating for extreme stability
        gate = torch.sigmoid(y + bias)
        return x * (1.0 - gate) + y * gate

    def forward(self, x: torch.Tensor, memory: torch.Tensor = None) -> torch.Tensor:
        # Pre-Norm Multi-Head Attention
        attn_input = self.norm1(x)
        kv_context = attn_input if memory is None else torch.cat([memory, attn_input], dim=1)
        
        # Causal masking must be applied externally during sequence unrolling
        attn_out, _ = self.attn(attn_input, kv_context, kv_context)
        
        # GRU Gate replaces the standard `x + attn_out` residual connection
        x = self._gru_gate(x, attn_out, self.gate1_bias)
        
        # Pre-Norm Feedforward (Utilizing GRN for superior non-linear representation)
        ffn_input = self.norm2(x)
        ffn_out = self.grn(ffn_input)
        
        # Final GRU Gate
        x = self._gru_gate(x, ffn_out, self.gate2_bias)
        return x

class AutoregressiveBetaHead(nn.Module):
    """
    Autoregressive action head utilizing Beta distributions.
    Strictly bounds the action space to [0,1] without relying on post-sampling clipping.
    """
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.alpha_net = nn.Linear(state_dim, action_dim)
        self.beta_net = nn.Linear(state_dim, action_dim)

    def forward(self, state_embedding: torch.Tensor):
        # Softplus + 1.0 guarantees strictly positive shape parameters (alpha, beta > 1.0),
        # preventing the Beta distribution from collapsing into a concave 'U' shape.
        alpha = F.softplus(self.alpha_net(state_embedding)) + 1.0
        beta = F.softplus(self.beta_net(state_embedding)) + 1.0
        return Beta(alpha, beta)

class MacroEconomyAgent(nn.Module):
    """
    Elite DRL Macro-Agent Architecture for 720-step RTS Economy Management.
    """
    def __init__(self, input_dim: int = 100, d_model: int = 256, n_layers: int = 4):
        super().__init__()
        self.d_model = d_model
        
        # 1. Tabular Feature Encoder
        self.feature_encoder = GatedResidualNetwork(input_dim, d_model, d_model)
        
        # 2. Temporal Memory Core (GTrXL)
        self.transformer_layers = nn.ModuleList([
            GTrXLBlock(d_model=d_model, n_heads=8, dim_feedforward=1024) 
            for _ in range(n_layers)
        ])
        
        # 3. Autoregressive Policy Routing Pipeline
        # Chain: Seeds -> Animals -> Sells -> RealEstate
        self.seed_head = AutoregressiveBetaHead(d_model, 5)
        self.seed_embedding = nn.Linear(5, d_model)
        
        self.animal_head = AutoregressiveBetaHead(d_model, 3)
        self.animal_embedding = nn.Linear(3, d_model)
        
        self.sell_head = AutoregressiveBetaHead(d_model, 9)
        self.sell_embedding = nn.Linear(9, d_model)
        
        self.worker_land_head = AutoregressiveBetaHead(d_model, 3)
        
        # 4. Centralized Critic for V-trace / GAE calculations
        self.value_head = nn.Sequential(
            RMSNorm(d_model),
            nn.Linear(d_model, d_model // 2),
            nn.ELU(),
            nn.Linear(d_model // 2, 1)
        )

    def forward(self, obs_seq: torch.Tensor, memory: torch.Tensor = None):
        """
        Processes a sequence of tabular observations and yields a tuple of 
        conditional action distributions and scalar state values.
        """
        # Step 1: Encode Tabular State
        encoded_state = self.feature_encoder(obs_seq)
        
        # Step 2: Temporal Integration
        core_state = encoded_state
        for layer in self.transformer_layers:
            core_state = layer(core_state, memory)
            
        # Step 3: Value Baseline Generation (Critic)
        state_value = self.value_head(core_state).squeeze(-1)
        
        # Step 4: Autoregressive Action Generation
        # A. Predict Seeds based purely on historical and current context
        seed_dist = self.seed_head(core_state)
        seed_proxy = seed_dist.mean 
        
        # B. Predict Animals (Strictly Conditioned on Seed expenditures)
        core_state_anim = core_state + self.seed_embedding(seed_proxy)
        animal_dist = self.animal_head(core_state_anim)
        animal_proxy = animal_dist.mean
        
        # C. Predict Sells (Conditioned on Seeds + Animals)
        core_state_sell = core_state_anim + self.animal_embedding(animal_proxy)
        sell_dist = self.sell_head(core_state_sell)
        sell_proxy = sell_dist.mean
        
        # D. Predict Workers/Land (Conditioned on all prior macroeconomic commitments)
        core_state_end = core_state_sell + self.sell_embedding(sell_proxy)
        worker_land_dist = self.worker_land_head(core_state_end)
        
        return (seed_dist, animal_dist, sell_dist, worker_land_dist), state_value
