"""
DICOM Preprocessing Pipeline for RSNA Knee MRI
Handles windowing, orientation correction, resampling, and normalization.
"""
import pydicom
import numpy as np
from pydicom.pixel_data_handlers.util import apply_voi_lut
from scipy import ndimage
from typing import Tuple, Optional, Dict, List
import cv2
from pathlib import Path


TARGET_SPACING = (0.5, 0.5)  # mm
TARGET_SIZE = (384, 384)
WINDOW_PRESETS = {
    "bone": {"center": 600, "width": 3000},
    "soft_tissue": {"center": 300, "width": 1500},
    "fluid": {"center": 800, "width": 2000},
}


def read_dicom_file(dicom_path: Path) -> pydicom.Dataset:
    """Read DICOM with error handling for various transfer syntaxes."""
    try:
        ds = pydicom.dcmread(dicom_path, force=True)
        return ds
    except Exception as e:
        raise ValueError(f"Failed to read {dicom_path}: {e}")


def get_pixel_array(ds: pydicom.Dataset, apply_voi: bool = True) -> np.ndarray:
    """Extract pixel array with proper scaling."""
    try:
        if apply_voi and hasattr(ds, 'VOILUTSequence') and ds.VOILUTSequence:
            arr = apply_voi_lut(ds.pixel_array, ds)
        else:
            arr = ds.pixel_array.astype(np.float32)
            if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                arr = arr * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        return arr
    except Exception:
        arr = ds.pixel_array.astype(np.float32)
        if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
            arr = arr * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        return arr


def window_image(image: np.ndarray, center: float, width: float) -> np.ndarray:
    """Apply windowing to image."""
    min_val = center - width / 2
    max_val = center + width / 2
    windowed = np.clip(image, min_val, max_val)
    windowed = (windowed - min_val) / (max_val - min_val)
    return windowed.astype(np.float32)


def percentile_window(image: np.ndarray, low: float = 1, high: float = 99) -> np.ndarray:
    """Percentile-based windowing (robust across scanners)."""
    p_low, p_high = np.percentile(image, (low, high))
    windowed = np.clip(image, p_low, p_high)
    windowed = (windowed - p_low) / (p_high - p_low + 1e-8)
    return windowed.astype(np.float32)


def get_orientation(ds: pydicom.Dataset) -> Tuple[np.ndarray, np.ndarray]:
    """Extract row/column direction cosines from ImageOrientationPatient."""
    if hasattr(ds, 'ImageOrientationPatient'):
        iop = np.array(ds.ImageOrientationPatient, dtype=np.float32)
        row_cos = iop[:3]
        col_cos = iop[3:]
        return row_cos, col_cos
    return np.array([1, 0, 0]), np.array([0, 1, 0])


def get_slice_position(ds: pydicom.Dataset) -> float:
    """Get slice position along normal direction."""
    if hasattr(ds, 'ImagePositionPatient'):
        ipp = np.array(ds.ImagePositionPatient, dtype=np.float32)
        row_cos, col_cos = get_orientation(ds)
        normal = np.cross(row_cos, col_cos)
        return np.dot(ipp, normal)
    return 0.0


def reorient_to_ras(image: np.ndarray, ds: pydicom.Dataset) -> np.ndarray:
    """Reorient image to RAS (Right-Anterior-Superior) coordinate system."""
    if not hasattr(ds, 'ImageOrientationPatient'):
        return image
    
    row_cos, col_cos = get_orientation(ds)
    normal = np.cross(row_cos, col_cos)
    
    row_flip = row_cos[0] < 0
    col_flip = col_cos[1] < 0
    
    if row_flip:
        image = np.flipud(image)
    if col_flip:
        image = np.fliplr(image)
    
    return image


def resample_image(
    image: np.ndarray,
    pixel_spacing: Tuple[float, float],
    target_spacing: Tuple[float, float] = TARGET_SPACING,
    order: int = 1
) -> np.ndarray:
    """Resample image to target pixel spacing."""
    if pixel_spacing == target_spacing:
        return image
    
    zoom_factors = (pixel_spacing[0] / target_spacing[0], pixel_spacing[1] / target_spacing[1])
    resampled = ndimage.zoom(image, zoom_factors, order=order)
    return resampled


def resize_image(image: np.ndarray, target_size: Tuple[int, int] = TARGET_SIZE) -> np.ndarray:
    """Resize image to target size using OpenCV."""
    return cv2.resize(image, target_size[::-1], interpolation=cv2.INTER_LINEAR)


def normalize_image(image: np.ndarray, method: str = "zscore") -> np.ndarray:
    """Normalize image."""
    if method == "zscore":
        mean, std = image.mean(), image.std()
        return (image - mean) / (std + 1e-8)
    elif method == "minmax":
        min_val, max_val = image.min(), image.max()
        return (image - min_val) / (max_val - min_val + 1e-8)
    elif method == "percentile":
        p1, p99 = np.percentile(image, (1, 99))
        clipped = np.clip(image, p1, p99)
        return (clipped - p1) / (p99 - p1 + 1e-8)
    return image


def preprocess_slice(
    dicom_path: Path,
    window_method: str = "percentile",
    target_size: Tuple[int, int] = TARGET_SIZE,
    normalize: str = "zscore"
) -> np.ndarray:
    """Full preprocessing pipeline for a single slice."""
    ds = read_dicom_file(dicom_path)
    image = get_pixel_array(ds)
    image = reorient_to_ras(image, ds)
    
    if hasattr(ds, 'PixelSpacing'):
        spacing = tuple(float(x) for x in ds.PixelSpacing[:2])
        image = resample_image(image, spacing)
    
    if window_method == "percentile":
        image = percentile_window(image)
    elif window_method in WINDOW_PRESETS:
        preset = WINDOW_PRESETS[window_method]
        image = window_image(image, preset["center"], preset["width"])
    elif window_method == "multi":
        channels = []
        for preset_name in ["bone", "soft_tissue", "fluid"]:
            preset = WINDOW_PRESETS[preset_name]
            channels.append(window_image(image, preset["center"], preset["width"]))
        image = np.stack(channels, axis=-1)
        return resize_image(image, target_size)
    
    image = resize_image(image, target_size)
    image = normalize_image(image, normalize)
    
    if image.ndim == 2:
        image = image[..., np.newaxis]
    
    return image.astype(np.float32)


def load_series_slices(
    series_dir: Path,
    max_slices: int = 24,
    sampling: str = "uniform",
    window_method: str = "percentile"
) -> np.ndarray:
    """Load and preprocess all slices in a series with smart sampling."""
    dicom_files = sorted(series_dir.glob("*.dcm"))
    if not dicom_files:
        raise ValueError(f"No DICOM files in {series_dir}")
    
    slices_with_pos = []
    for f in dicom_files:
        ds = read_dicom_file(f)
        pos = get_slice_position(ds)
        slices_with_pos.append((pos, f))
    
    slices_with_pos.sort(key=lambda x: x[0])
    sorted_files = [f for _, f in slices_with_pos]
    
    n_total = len(sorted_files)
    if n_total <= max_slices:
        selected = sorted_files
    else:
        if sampling == "uniform":
            indices = np.linspace(0, n_total - 1, max_slices, dtype=int)
        elif sampling == "central":
            center = n_total // 2
            half = max_slices // 2
            start = max(0, center - half)
            end = min(n_total, start + max_slices)
            indices = np.arange(start, end)
        else:
            indices = np.random.choice(n_total, max_slices, replace=False)
            indices.sort()
        selected = [sorted_files[i] for i in indices]
    
    processed = []
    for f in selected:
        try:
            img = preprocess_slice(f, window_method=window_method)
            processed.append(img)
        except Exception as e:
            print(f"Warning: Failed to process {f}: {e}")
            continue
    
    if not processed:
        raise ValueError(f"No valid slices in {series_dir}")
    
    return np.stack(processed, axis=0)


class SeriesSelector:
    """Select optimal series for each study based on metadata."""
    
    PRIORITY = {
        ("Sagittal", 1, 1): 1,  # Sagittal FS - best for ACL, menisci
        ("Coronal", 1, 1): 2,   # Coronal FS - ACL, MCL, cartilage
        ("Axial", 1, 1): 3,     # Axial FS - PF OA, effusion, Baker's
        ("Sagittal", 0, 0): 4,  # Sagittal T1 - anatomy, fracture
        ("Coronal", 0, 0): 5,
        ("Axial", 0, 0): 6,
    }
    
    @classmethod
    def select_series(cls, series_meta: List[Dict], max_series: int = 4) -> List[Dict]:
        """Select best series for abnormality detection."""
        scored = []
        for meta in series_meta:
            key = (meta["Anatomical_Plane"], meta["Fluid_Sensitive"], meta["Fat_Suppression"])
            priority = cls.PRIORITY.get(key, 10)
            scored.append((priority, meta))
        
        scored.sort(key=lambda x: x[0])
        return [m for _, m in scored[:max_series]]


def create_three_channel_input(slices: np.ndarray, method: str = "adjacent") -> np.ndarray:
    """Convert single-channel slices to 3-channel for ImageNet pretrained models."""
    n_slices = slices.shape[0]
    if method == "adjacent":
        three_ch = np.zeros((n_slices, *slices.shape[1:3], 3), dtype=np.float32)
        for i in range(n_slices):
            prev_idx = max(0, i - 1)
            next_idx = min(n_slices - 1, i + 1)
            three_ch[i, :, :, 0] = slices[prev_idx, :, :, 0]
            three_ch[i, :, :, 1] = slices[i, :, :, 0]
            three_ch[i, :, :, 2] = slices[next_idx, :, :, 0]
        return three_ch
    elif method == "repeat":
        return np.repeat(slices, 3, axis=-1)
    else:
        return slices


if __name__ == "__main__":
    from src.data.synthetic_generator import generate_synthetic_dataset
    generate_synthetic_dataset("data/synthetic", num_studies=5)
    print("Test preprocessing...")
    series_dir = Path("data/synthetic/train_series")
    for study in series_dir.iterdir():
        for series in study.iterdir():
            try:
                slices = load_series_slices(series, max_slices=16)
                print(f"{series.name}: {slices.shape}")
                break
            except Exception as e:
                print(f"Error: {e}")
        break