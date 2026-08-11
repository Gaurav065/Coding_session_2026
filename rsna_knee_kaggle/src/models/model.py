"""
Model Architecture for RSNA Knee Abnormality Detection
Multi-series MIL with attention-based aggregation.
"""
import copy
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
from typing import List, Optional, Tuple
import math


class AttentionMIL(nn.Module):
    """Attention-based Multiple Instance Learning aggregation."""
    
    def __init__(self, feature_dim: int, hidden_dim: int = 128, dropout: float = 0.1):
        super().__init__()
        self.feature_dim = feature_dim
        self.hidden_dim = hidden_dim
        
        self.attention = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1)
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, feature_dim)
        )
    
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [B, N, D] - batch of bags with N instances each
            mask: [B, N] - boolean mask for valid instances
        Returns:
            aggregated: [B, D]
            attention_weights: [B, N]
        """
        B, N, D = x.shape
        
        attn_scores = self.attention(x).squeeze(-1)  # [B, N]
        
        if mask is not None:
            attn_scores = attn_scores.masked_fill(~mask, -1e9)
        
        attn_weights = F.softmax(attn_scores, dim=1)  # [B, N]
        
        aggregated = torch.sum(attn_weights.unsqueeze(-1) * x, dim=1)  # [B, D]
        
        return aggregated, attn_weights


class SeriesEncoder(nn.Module):
    """Encodes a single MRI series (multiple slices) into a feature vector."""
    
    def __init__(
        self,
        backbone: str = "efficientnet_b3",
        pretrained: bool = True,
        feature_dim: int = 512,
        slice_aggregation: str = "attention",
        dropout: float = 0.1,
        in_channels: int = 3,
        backbone_chunk_size: int = 6
    ):
        super().__init__()
        self.slice_aggregation = slice_aggregation
        self.feature_dim = feature_dim
        self.backbone_chunk_size = backbone_chunk_size
        
        self.backbone = timm.create_model(
            backbone, pretrained=pretrained, num_classes=0, global_pool="",
            in_chans=in_channels
        )
        backbone_feat_dim = self.backbone.num_features
        
        if slice_aggregation == "attention":
            self.slice_attention = AttentionMIL(backbone_feat_dim, hidden_dim=256, dropout=dropout)
        elif slice_aggregation == "max":
            self.slice_attention = None
        elif slice_aggregation == "mean":
            self.slice_attention = None
        elif slice_aggregation == "transformer":
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=backbone_feat_dim, nhead=8, dim_feedforward=1024,
                dropout=dropout, batch_first=True
            )
            self.slice_transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
            self.slice_attention = None
        else:
            raise ValueError(f"Unknown slice_aggregation: {slice_aggregation}")
        
        self.projection = nn.Sequential(
            nn.Linear(backbone_feat_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
    
    def forward(self, slices: torch.Tensor, slice_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            slices: [B, N_slices, C, H, W] or [N_slices, C, H, W]
            slice_mask: [B, N_slices] or [N_slices]
        Returns:
            features: [B, feature_dim] or [feature_dim]
        """
        if slices.dim() == 4:
            slices = slices.unsqueeze(0)
            if slice_mask is not None:
                slice_mask = slice_mask.unsqueeze(0)
        
        B, N, C, H, W = slices.shape
        slices_flat = slices.contiguous().reshape(B * N, C, H, W)
        
        # Process through backbone in chunks to reduce peak VRAM
        chunk_size = self.backbone_chunk_size
        feat_chunks = []
        for start in range(0, B * N, chunk_size):
            end = min(start + chunk_size, B * N)
            chunk_feat = self.backbone(slices_flat[start:end])
            
            if isinstance(chunk_feat, dict):
                chunk_feat = chunk_feat["features"] if "features" in chunk_feat else list(chunk_feat.values())[0]
            if chunk_feat.dim() == 4:
                chunk_feat = F.adaptive_avg_pool2d(chunk_feat, 1).flatten(1)
            
            feat_chunks.append(chunk_feat)
        
        feat = torch.cat(feat_chunks, dim=0)
        feat = feat.reshape(B, N, -1)  # [B, N, D_backbone]
        
        if self.slice_aggregation == "attention":
            agg_feat, _ = self.slice_attention(feat, slice_mask)
        elif self.slice_aggregation == "max":
            if slice_mask is not None:
                feat = feat.masked_fill(~slice_mask.unsqueeze(-1), -1e9)
            agg_feat = feat.max(dim=1)[0]
        elif self.slice_aggregation == "mean":
            if slice_mask is not None:
                feat = feat * slice_mask.unsqueeze(-1).float()
                valid_counts = slice_mask.sum(dim=1, keepdim=True).float().clamp(min=1)
                agg_feat = feat.sum(dim=1) / valid_counts
            else:
                agg_feat = feat.mean(dim=1)
        elif self.slice_aggregation == "transformer":
            if slice_mask is not None:
                src_key_padding_mask = ~slice_mask
            else:
                src_key_padding_mask = None
            feat = self.slice_transformer(feat, src_key_padding_mask=src_key_padding_mask)
            agg_feat = feat[:, 0]  # Use CLS-like token (first slice)
        
        output = self.projection(agg_feat)  # [B, feature_dim]
        
        if output.shape[0] == 1 and slices.shape[0] == 1:
            return output.squeeze(0)
        return output


class StudyFusion(nn.Module):
    """Fuses multiple series embeddings into study-level prediction."""
    
    def __init__(
        self,
        feature_dim: int,
        num_classes: int = 12,
        fusion: str = "attention",
        hidden_dim: int = 256,
        dropout: float = 0.2
    ):
        super().__init__()
        self.fusion = fusion
        self.feature_dim = feature_dim
        self.num_classes = num_classes
        
        if fusion == "attention":
            self.series_attention = AttentionMIL(feature_dim, hidden_dim, dropout)
        elif fusion == "transformer":
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=feature_dim, nhead=8, dim_feedforward=1024,
                dropout=dropout, batch_first=True
            )
            self.series_transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        elif fusion == "concat":
            self.concat_fc = nn.Linear(feature_dim * 6, hidden_dim)  # max 6 series
        elif fusion == "max":
            pass
        elif fusion == "mean":
            pass
        else:
            raise ValueError(f"Unknown fusion: {fusion}")
        
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim if fusion != "concat" else hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_classes)
        )
    
    def forward(
        self,
        series_features: torch.Tensor,
        series_mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Args:
            series_features: [B, N_series, D]
            series_mask: [B, N_series]
        Returns:
            logits: [B, num_classes]
            attention_weights: [B, N_series] or None
        """
        if self.fusion == "attention":
            fused, attn = self.series_attention(series_features, series_mask)
        elif self.fusion == "transformer":
            if series_mask is not None:
                src_key_padding_mask = ~series_mask
            else:
                src_key_padding_mask = None
            fused = self.series_transformer(series_features, src_key_padding_mask=src_key_padding_mask)
            fused = fused[:, 0]  # First token
            attn = None
        elif self.fusion == "concat":
            B, N, D = series_features.shape
            max_n = 6
            if N < max_n:
                pad = torch.zeros(B, max_n - N, D, device=series_features.device)
                series_features = torch.cat([series_features, pad], dim=1)
            fused = self.concat_fc(series_features.flatten(1))
            attn = None
        elif self.fusion == "max":
            if series_mask is not None:
                series_features = series_features.masked_fill(~series_mask.unsqueeze(-1), -1e9)
            fused = series_features.max(dim=1)[0]
            attn = None
        elif self.fusion == "mean":
            if series_mask is not None:
                series_features = series_features * series_mask.unsqueeze(-1).float()
                valid_counts = series_mask.sum(dim=1, keepdim=True).float().clamp(min=1)
                fused = series_features.sum(dim=1) / valid_counts
            else:
                fused = series_features.mean(dim=1)
            attn = None
        
        logits = self.classifier(fused)
        return logits, attn


class KneeAbnormalityModel(nn.Module):
    """Complete model for knee abnormality detection."""
    
    def __init__(
        self,
        backbone: str = "efficientnet_b3",
        pretrained: bool = True,
        feature_dim: int = 512,
        num_classes: int = 12,
        slice_aggregation: str = "attention",
        series_fusion: str = "attention",
        dropout: float = 0.2,
        in_channels: int = 3
    ):
        super().__init__()
        
        self.series_encoder = SeriesEncoder(
            backbone=backbone,
            pretrained=pretrained,
            feature_dim=feature_dim,
            slice_aggregation=slice_aggregation,
            dropout=dropout,
            in_channels=in_channels
        )
        
        self.study_fusion = StudyFusion(
            feature_dim=feature_dim,
            num_classes=num_classes,
            fusion=series_fusion,
            dropout=dropout
        )
        
        self.num_classes = num_classes
    
    def forward(
        self,
        series_batch: torch.Tensor,
        series_mask: torch.Tensor,
        slice_masks: torch.Tensor
    ) -> Tuple[torch.Tensor, List[torch.Tensor], Optional[torch.Tensor]]:
        """
        Args:
            series_batch: [B, N_series, N_slices, C, H, W]
            series_mask: [B, N_series]
            slice_masks: [B, N_series, N_slices]
        Returns:
            logits: [B, num_classes]
            series_features: List of [B, feature_dim] for each series
            study_attention: [B, N_series] or None
        """
        B, N_series, N_slices, C, H, W = series_batch.shape
        
        series_features = []
        for i in range(N_series):
            slices = series_batch[:, i]  # [B, N_slices, C, H, W]
            slice_mask = slice_masks[:, i] if slice_masks is not None else None
            feat = self.series_encoder(slices, slice_mask)  # [B, feature_dim]
            series_features.append(feat)
        
        series_features = torch.stack(series_features, dim=1)  # [B, N_series, feature_dim]
        
        logits, study_attention = self.study_fusion(series_features, series_mask)
        
        return logits, series_features, study_attention


def create_model(
    backbone: str = "efficientnet_b3",
    pretrained: bool = True,
    **kwargs
) -> KneeAbnormalityModel:
    """Factory function to create model."""
    return KneeAbnormalityModel(backbone=backbone, pretrained=pretrained, **kwargs)


class ModelEMA(nn.Module):
    """Exponential Moving Average of model weights."""
    
    def __init__(self, model: nn.Module, decay: float = 0.999):
        super().__init__()
        self.module = copy.deepcopy(model)
        self.module.eval()
        self.decay = decay
        
        for p in self.module.parameters():
            p.requires_grad = False
    
    @torch.no_grad()
    def update(self, model: nn.Module):
        for ema_p, p in zip(self.module.parameters(), model.parameters()):
            ema_p.data.mul_(self.decay).add_(p.data, alpha=1 - self.decay)
    
    def forward(self, *args, **kwargs):
        return self.module(*args, **kwargs)


if __name__ == "__main__":
    model = create_model(
        backbone="efficientnet_b3",
        pretrained=False,
        feature_dim=512,
        num_classes=12,
        slice_aggregation="attention",
        series_fusion="attention",
        dropout=0.2
    )
    
    B, N_series, N_slices = 2, 3, 16
    series_batch = torch.randn(B, N_series, N_slices, 3, 384, 384)
    series_mask = torch.ones(B, N_series, dtype=torch.bool)
    slice_masks = torch.ones(B, N_series, N_slices, dtype=torch.bool)
    
    logits, series_feats, study_attn = model(series_batch, series_mask, slice_masks)
    print(f"Logits shape: {logits.shape}")
    print(f"Series features: {len(series_feats)} x {series_feats[0].shape}")
    print(f"Study attention: {study_attn.shape if study_attn is not None else None}")
    print(f"Parameters: {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M")