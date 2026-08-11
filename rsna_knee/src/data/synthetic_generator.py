"""
Synthetic RSNA Knee MRI DICOM Generator
Creates realistic knee MRI DICOMs matching competition structure for local development.
"""
import os
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from pydicom.sequence import Sequence
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
from datetime import datetime
import random


KNEE_ANATOMY = {
    "ACL": {"location": "central", "shape": "linear", "intensity": "low_on_fs"},
    "MCL": {"location": "medial", "shape": "linear", "intensity": "low_on_fs"},
    "Medial Meniscus": {"location": "medial_tibial", "shape": "c_shaped", "intensity": "low_on_fs"},
    "Lateral Meniscus": {"location": "lateral_tibial", "shape": "c_shaped", "intensity": "low_on_fs"},
    "Medial OA": {"location": "medial_compartment", "signs": ["narrowing", "osteophytes", "sclerosis"]},
    "Lateral OA": {"location": "lateral_compartment", "signs": ["narrowing", "osteophytes", "sclerosis"]},
    "PF OA": {"location": "patellofemoral", "signs": ["narrowing", "osteophytes", "sclerosis"]},
    "Effusion": {"location": "suprapatellar", "signs": ["high_signal_fluid"]},
    "Synovitis": {"location": "synovial_lining", "signs": ["thickening", "enhancement"]},
    "Baker's": {"location": "popliteal_fossa", "signs": ["fluid_collection"]},
    "Contusion": {"location": "subchondral", "signs": ["high_signal_edema"]},
    "Fracture": {"location": "cortex", "signs": ["cortical_break", "edema"]},
}

SERIES_TYPES = [
    {"name": "SAG_3D_DESS_WE", "plane": "Sagittal", "fluid_sensitive": 0, "fat_suppressed": 0, "desc": "T1-weighted cartilage"},
    {"name": "COR_T2_FS", "plane": "Coronal", "fluid_sensitive": 1, "fat_suppressed": 1, "desc": "T2 FS"},
    {"name": "SAG_PD_FS", "plane": "Sagittal", "fluid_sensitive": 1, "fat_suppressed": 1, "desc": "PD FS"},
    {"name": "AX_T2_FS", "plane": "Axial", "fluid_sensitive": 1, "fat_suppressed": 1, "desc": "T2 FS"},
    {"name": "SAG_T1", "plane": "Sagittal", "fluid_sensitive": 0, "fat_suppressed": 0, "desc": "T1"},
    {"name": "COR_PD", "plane": "Coronal", "fluid_sensitive": 0, "fat_suppressed": 0, "desc": "PD"},
]


def create_synthetic_knee_slice(
    slice_idx: int,
    num_slices: int,
    series_type: Dict,
    abnormalities: Dict[str, int],
    image_size: Tuple[int, int] = (384, 384),
    seed: int = 42
) -> np.ndarray:
    """Generate a single synthetic knee MRI slice with realistic anatomy."""
    rng = np.random.RandomState(seed + slice_idx * 1000)
    h, w = image_size
    img = np.zeros((h, w), dtype=np.float32)
    
    center_y, center_x = h // 2, w // 2
    
    femur_radius = int(min(h, w) * 0.35)
    tibia_radius = int(min(h, w) * 0.25)
    
    y, x = np.ogrid[:h, :w]
    y = y.astype(np.float32)
    x = x.astype(np.float32)
    
    femur_mask = (y - center_y + int(femur_radius * 0.3))**2 + (x - center_x)**2 < femur_radius**2
    tibia_mask = (y - center_y - int(tibia_radius * 0.3))**2 + (x - center_x)**2 < tibia_radius**2
    patella_mask = (y - center_y + int(femur_radius * 0.8))**2 + (x - center_x)**2 < (int(femur_radius * 0.4))**2
    
    bone_mask = femur_mask | tibia_mask | patella_mask
    
    if series_type["fluid_sensitive"]:
        img[bone_mask] = rng.normal(200, 50, bone_mask.sum())
        img[~bone_mask] = rng.normal(800, 150, (~bone_mask).sum())
    else:
        img[bone_mask] = rng.normal(800, 100, bone_mask.sum())
        img[~bone_mask] = rng.normal(300, 80, (~bone_mask).sum())
    
    if series_type["fat_suppressed"]:
        fat_rows = (np.arange(h) < center_y - femur_radius) | (np.arange(h) > center_y + tibia_radius)
        if fat_rows.any():
            img[fat_rows, :] = rng.normal(50, 30, (fat_rows.sum(), w))
    
    slice_pos = slice_idx / max(1, num_slices - 1)
    
    if abnormalities.get("ACL", 0) and 0.3 < slice_pos < 0.6:
        acl_y = center_y - int(femur_radius * 0.1)
        acl_x = center_x
        acl_mask = (y - acl_y)**2 / (int(femur_radius*0.03))**2 + (x - acl_x)**2 / (int(femur_radius*0.08))**2 < 1
        if series_type["fluid_sensitive"]:
            img[acl_mask] = rng.normal(900, 100, acl_mask.sum())
        else:
            img[acl_mask] = rng.normal(600, 80, acl_mask.sum())
    
    if abnormalities.get("MCL", 0) and 0.2 < slice_pos < 0.7:
        mcl_x = center_x - int(w * 0.35)
        mcl_y = center_y
        mcl_mask = (np.abs(x - mcl_x) < 4) & (np.abs(y - mcl_y) < int(h * 0.3))
        if series_type["fluid_sensitive"]:
            img[mcl_mask] = rng.normal(900, 100, mcl_mask.sum())
    
    if abnormalities.get("Medial Meniscus", 0) and 0.4 < slice_pos < 0.8:
        mm_x = center_x - int(w * 0.25)
        mm_y = center_y + int(h * 0.1)
        theta = np.arctan2(y - mm_y, x - mm_x)
        r = np.sqrt((y - mm_y)**2 + (x - mm_x)**2)
        meniscus_mask = (r > tibia_radius * 0.7) & (r < tibia_radius * 1.1) & (theta > -0.5) & (theta < 2.0)
        if series_type["fluid_sensitive"]:
            img[meniscus_mask] = rng.normal(900, 100, meniscus_mask.sum())
    
    if abnormalities.get("Lateral Meniscus", 0) and 0.4 < slice_pos < 0.8:
        lm_x = center_x + int(w * 0.25)
        lm_y = center_y + int(h * 0.1)
        theta = np.arctan2(y - lm_y, x - lm_x)
        r = np.sqrt((y - lm_y)**2 + (x - lm_x)**2)
        meniscus_mask = (r > tibia_radius * 0.7) & (r < tibia_radius * 1.1) & (theta > -2.5) & (theta < 0.5)
        if series_type["fluid_sensitive"]:
            img[meniscus_mask] = rng.normal(900, 100, meniscus_mask.sum())
    
    if abnormalities.get("Effusion", 0) and 0.1 < slice_pos < 0.5:
        eff_y = center_y - int(femur_radius * 0.5)
        eff_mask = (y - eff_y)**2 + (x - center_x)**2 < (int(femur_radius * 0.6))**2
        eff_mask = eff_mask & (~bone_mask)
        if series_type["fluid_sensitive"]:
            img[eff_mask] = rng.normal(1200, 150, eff_mask.sum())
    
    if abnormalities.get("Baker's", 0) and 0.7 < slice_pos < 0.95:
        bk_y = center_y + int(tibia_radius * 1.2)
        bk_x = center_x
        bk_mask = (y - bk_y)**2 + (x - bk_x)**2 < (int(tibia_radius * 0.4))**2
        if series_type["fluid_sensitive"]:
            img[bk_mask] = rng.normal(1100, 150, bk_mask.sum())
    
    if abnormalities.get("Contusion", 0) and 0.4 < slice_pos < 0.7:
        cont_y = center_y + int(h * 0.05)
        cont_x = center_x + rng.randint(-int(w*0.15), int(w*0.15))
        cont_mask = (y - cont_y)**2 + (x - cont_x)**2 < (int(min(h,w)*0.05))**2
        if series_type["fluid_sensitive"]:
            img[cont_mask] = rng.normal(1000, 120, cont_mask.sum())
    
    if abnormalities.get("Fracture", 0) and 0.3 < slice_pos < 0.6:
        fx_y = center_y + rng.randint(-int(h*0.1), int(h*0.1))
        fx_x = center_x + rng.randint(-int(w*0.1), int(w*0.1))
        fx_mask = np.abs(x - fx_x) < 2
        img[fx_mask] = rng.normal(100, 50, fx_mask.sum())
    
    noise = rng.normal(0, 15, (h, w))
    img += noise
    
    img = np.clip(img, 0, 4095)
    
    return img.astype(np.uint16)


def create_dicom_dataset(
    pixel_array: np.ndarray,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    series_type: Dict,
    slice_idx: int,
    num_slices: int,
    patient_sex: str = "M",
    patient_age: str = "045Y"
) -> pydicom.Dataset:
    """Create a valid DICOM dataset with required metadata."""
    ds = Dataset()
    
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = sop_uid
    ds.file_meta.ImplementationClassUID = generate_uid()
    
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = study_uid[:8]
    ds.PatientSex = patient_sex
    ds.PatientAge = patient_age
    ds.StudyDate = datetime.now().strftime("%Y%m%d")
    ds.StudyTime = datetime.now().strftime("%H%M%S")
    ds.SeriesDate = datetime.now().strftime("%Y%m%d")
    ds.SeriesTime = datetime.now().strftime("%H%M%S")
    ds.AccessionNumber = "ACC" + study_uid[:6]
    ds.Modality = "MR"
    ds.Manufacturer = "SyntheticMRI"
    ds.ManufacturerModelName = "KneeSimulator"
    ds.StationName = "SYNTHETIC"
    ds.SoftwareVersions = "1.0"
    ds.BodyPartExamined = "KNEE"
    ds.PatientPosition = "HFS"
    
    ds.SeriesNumber = hash(series_uid) % 1000
    ds.InstanceNumber = slice_idx + 1
    ds.SeriesDescription = series_type["desc"]
    ds.ProtocolName = series_type["name"]
    
    ds.Rows, ds.Columns = pixel_array.shape
    ds.PixelSpacing = [0.5, 0.5]
    ds.SliceThickness = 3.0
    ds.SpacingBetweenSlices = 3.5
    
    if series_type["plane"] == "Sagittal":
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [0, 0, slice_idx * 3.5 - 50]
    elif series_type["plane"] == "Coronal":
        ds.ImageOrientationPatient = [1, 0, 0, 0, 0, 1]
        ds.ImagePositionPatient = [0, slice_idx * 3.5 - 50, 0]
    else:
        ds.ImageOrientationPatient = [0, 1, 0, 0, 0, 1]
        ds.ImagePositionPatient = [slice_idx * 3.5 - 50, 0, 0]
    
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    
    ds.WindowCenter = 2048
    ds.WindowWidth = 4096
    
    ds.MagneticFieldStrength = 3.0
    ds.SequenceName = series_type["name"]
    ds.RepetitionTime = 3000 if series_type["fluid_sensitive"] else 500
    ds.EchoTime = 80 if series_type["fluid_sensitive"] else 15
    ds.FlipAngle = 120 if series_type["fluid_sensitive"] else 90
    
    ds.Rows = pixel_array.shape[0]
    ds.Columns = pixel_array.shape[1]
    ds.PixelData = pixel_array.tobytes()
    
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    return ds


def generate_synthetic_study(
    study_uid: str,
    output_dir: Path,
    abnormalities: Dict[str, int],
    patient_sex: str = "M",
    patient_age: str = "045Y",
    num_series: int = 4,
    slices_per_series: int = 30
):
    """Generate a complete synthetic study with multiple series."""
    study_dir = output_dir / study_uid
    study_dir.mkdir(parents=True, exist_ok=True)
    
    selected_series = random.sample(SERIES_TYPES, min(num_series, len(SERIES_TYPES)))
    
    for series_type in selected_series:
        series_uid = generate_uid()
        series_dir = study_dir / series_uid
        series_dir.mkdir(exist_ok=True)
        
        num_slices = random.randint(20, 45)
        
        for slice_idx in range(num_slices):
            sop_uid = generate_uid()
            seed_val = abs(hash(study_uid + series_uid)) % (2**32)
            pixel_array = create_synthetic_knee_slice(
                slice_idx, num_slices, series_type, abnormalities, seed=seed_val
            )
            
            ds = create_dicom_dataset(
                pixel_array, study_uid, series_uid, sop_uid,
                series_type, slice_idx, num_slices, patient_sex, patient_age
            )
            
            ds.save_as(series_dir / f"{sop_uid}.dcm", write_like_original=False)


def generate_synthetic_dataset(
    output_dir: str = "data/synthetic",
    num_studies: int = 100,
    labeled_fraction: float = 0.15,
    seed: int = 42
):
    """Generate complete synthetic dataset matching competition structure."""
    random.seed(seed)
    np.random.seed(seed)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    train_series_dir = output_path / "train_series"
    train_series_dir.mkdir(exist_ok=True)
    
    labels = list(KNEE_ANATOMY.keys())
    prevalence = {
        "ACL": 0.12, "MCL": 0.08, "Medial Meniscus": 0.25, "Lateral Meniscus": 0.15,
        "Medial OA": 0.30, "Lateral OA": 0.18, "PF OA": 0.22,
        "Effusion": 0.35, "Synovitis": 0.12, "Baker's": 0.05,
        "Contusion": 0.08, "Fracture": 0.03
    }
    
    train_rows = []
    train_series_rows = []
    
    for i in range(num_studies):
        study_uid = f"1.2.826.0.1.3680043.{1000000 + i}"
        
        abnormalities = {}
        for label in labels:
            abnormalities[label] = 1 if random.random() < prevalence[label] else 0
        
        patient_sex = random.choice(["M", "F"])
        patient_age = f"{random.randint(20, 85):03d}Y"
        
        has_labels = random.random() < labeled_fraction
        
        train_rows.append({
            "StudyInstanceUID": study_uid,
            "PatientSex": patient_sex,
            "Report": generate_synthetic_report(abnormalities),
            **({label: abnormalities[label] for label in labels} if has_labels else {label: -1 for label in labels})
        })
        
        selected_series = random.sample(SERIES_TYPES, k=random.randint(3, 5))
        for series_type in selected_series:
            series_uid = generate_uid()
            num_slices = random.randint(20, 45)
            
            train_series_rows.append({
                "StudyInstanceUID": study_uid,
                "SeriesInstanceUID": series_uid,
                "Fluid_Sensitive": series_type["fluid_sensitive"],
                "Fat_Suppression": series_type["fat_suppressed"],
                "Anatomical_Plane": series_type["plane"]
            })
        
        generate_synthetic_study(
            study_uid, train_series_dir, abnormalities,
            patient_sex, patient_age,
            num_series=len(selected_series)
        )
        
        if (i + 1) % 10 == 0:
            print(f"Generated {i + 1}/{num_studies} studies...")
    
    train_df = pd.DataFrame(train_rows)
    train_series_df = pd.DataFrame(train_series_rows)
    
    train_df.to_csv(output_path / "train.csv", index=False)
    train_series_df.to_csv(output_path / "train_series.csv", index=False)
    
    test_studies = 20
    test_rows = []
    test_series_rows = []
    
    for i in range(test_studies):
        study_uid = f"1.2.826.0.1.3680043.{2000000 + i}"
        test_rows.append({"StudyInstanceUID": study_uid})
        
        selected_series = random.sample(SERIES_TYPES, k=random.randint(3, 5))
        for series_type in selected_series:
            series_uid = generate_uid()
            test_series_rows.append({
                "StudyInstanceUID": study_uid,
                "SeriesInstanceUID": series_uid,
                "Fluid_Sensitive": series_type["fluid_sensitive"],
                "Fat_Suppression": series_type["fat_suppressed"],
                "Anatomical_Plane": series_type["plane"]
            })
    
    test_df = pd.DataFrame(test_rows)
    test_series_df = pd.DataFrame(test_series_rows)
    
    test_df.to_csv(output_path / "test.csv", index=False)
    test_series_df.to_csv(output_path / "test_series.csv", index=False)
    
    sample_sub = pd.DataFrame([{
        "StudyInstanceUID": row["StudyInstanceUID"],
        **{label: 0.5 for label in labels}
    } for _, row in test_df.iterrows()])
    sample_sub.to_csv(output_path / "sample_submission.csv", index=False)
    
    print(f"\nDataset generated at {output_path}")
    print(f"Train studies: {len(train_df)}")
    print(f"Test studies: {len(test_df)}")
    print(f"Labeled studies: {(train_df[labels[0]] != -1).sum()}")


def generate_synthetic_report(abnormalities: Dict[str, int]) -> str:
    """Generate a synthetic radiology report."""
    findings = []
    for label, val in abnormalities.items():
        if val == 1:
            findings.append(label.lower().replace("'", ""))
    
    if not findings:
        return "Normal knee MRI. No acute abnormality identified. Intact ACL, MCL, medial and lateral menisci. No osteoarthritis. No effusion. No Baker's cyst. No contusion or fracture."
    
    templates = [
        f"Findings: {'; '.join(findings)} identified. Remaining structures unremarkable.",
        f"Impression: {'; '.join(findings)}. Clinical correlation recommended.",
        f"There is evidence of {'; '.join(findings)}. Other structures appear normal."
    ]
    return random.choice(templates)


if __name__ == "__main__":
    generate_synthetic_dataset("data/synthetic", num_studies=50, labeled_fraction=0.2)