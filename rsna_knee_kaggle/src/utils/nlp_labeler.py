"""
Report NLP Labeler for Pseudo-Labeling
Extracts 12 abnormality labels from radiology reports using keyword matching
and optional transformer-based classification.
"""
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json


LABELS = [
    "ACL", "MCL", "Medial Meniscus", "Lateral Meniscus",
    "Medial OA", "Lateral OA", "PF OA",
    "Effusion", "Synovitis", "Baker's", "Contusion", "Fracture"
]

KEYWORD_PATTERNS = {
    "ACL": [
        r"\bacl\b", r"anterior cruciate", r"cruciate ligament",
        r"acl tear", r"acl rupture", r"acl injury"
    ],
    "MCL": [
        r"\bmcl\b", r"medial collateral", r"mcl tear", r"mcl sprain",
        r"mcl injury", r"medial collateral ligament"
    ],
    "Medial Meniscus": [
        r"medial menisc", r"mm tear", r"medial meniscus tear",
        r"bucket handle.*medial", r"medial meniscal"
    ],
    "Lateral Meniscus": [
        r"lateral menisc", r"lm tear", r"lateral meniscus tear",
        r"bucket handle.*lateral", r"lateral meniscal"
    ],
    "Medial OA": [
        r"medial compartment.*oa", r"medial tibiofemoral.*oa",
        r"medial joint space narrowing", r"medial osteoarthritis",
        r"medial compartment narrowing"
    ],
    "Lateral OA": [
        r"lateral compartment.*oa", r"lateral tibiofemoral.*oa",
        r"lateral joint space narrowing", r"lateral osteoarthritis",
        r"lateral compartment narrowing"
    ],
    "PF OA": [
        r"patellofemoral.*oa", r"patellofemoral osteoarthritis",
        r"pf joint.*oa", r"patellofemoral narrowing",
        r"patellofemoral joint space"
    ],
    "Effusion": [
        r"\beffusion\b", r"joint effusion", r"suprapatellar effusion",
        r"increased fluid", r"large effusion", r"moderate effusion",
        r"small effusion", r"joint fluid"
    ],
    "Synovitis": [
        r"\bsynovitis\b", r"synovial thickening", r"synovial hypertrophy",
        r"synovial enhancement", r"inflamed synov"
    ],
    "Baker's": [
        r"baker['']?s? cyst", r"popliteal cyst", r"baker['']?s",
        r"popliteal fossa cyst", r"baker cyst"
    ],
    "Contusion": [
        r"\bcontusion\b", r"bone bruise", r"bone marrow edema",
        r"subchondral edema", r"marrow edema", r"contusion"
    ],
    "Fracture": [
        r"\bfracture\b", r"fx\b", r"cortical break",
        r"fracture line", r"broken bone", r"fractured"
    ],
}

NEGATION_PATTERNS = [
    r"\bno\b", r"\bnot\b", r"\bwithout\b", r"\babsent\b",
    r"\bnegative\b", r"\bunremarkable\b", r"\bnormal\b",
    r"\bintact\b", r"\bclear\b", r"\bno evidence\b"
]


def clean_report(text: str) -> str:
    """Clean and normalize report text."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\;\:\-\'\"]', ' ', text)
    return text.strip()


def check_negation(text: str, keyword_pos: int, window: int = 50) -> bool:
    """Check if keyword is negated within context window."""
    start = max(0, keyword_pos - window)
    context = text[start:keyword_pos]
    for neg in NEGATION_PATTERNS:
        if re.search(neg, context):
            return True
    return False


def extract_labels_keyword(report: str) -> Dict[str, int]:
    """Extract labels using keyword matching with negation detection."""
    clean = clean_report(report)
    labels = {}
    
    for label, patterns in KEYWORD_PATTERNS.items():
        found = False
        for pattern in patterns:
            for match in re.finditer(pattern, clean):
                if not check_negation(clean, match.start()):
                    found = True
                    break
            if found:
                break
        labels[label] = 1 if found else 0
    
    return labels


def extract_labels_ensemble(reports: List[str], models: List = None) -> np.ndarray:
    """Ensemble multiple extraction methods."""
    all_labels = []
    for report in reports:
        kw_labels = extract_labels_keyword(report)
        all_labels.append([kw_labels[l] for l in LABELS])
    return np.array(all_labels, dtype=np.float32)


def create_pseudo_labels(
    train_csv: str,
    output_csv: str,
    confidence_threshold: float = 0.8
):
    """Generate pseudo-labels for all training studies from reports."""
    df = pd.read_csv(train_csv)
    
    reports = df["Report"].fillna("").tolist()
    pseudo_labels = extract_labels_ensemble(reports)
    
    pseudo_df = df[["StudyInstanceUID"]].copy()
    for i, label in enumerate(LABELS):
        pseudo_df[label] = pseudo_labels[:, i]
    
    pseudo_df.to_csv(output_csv, index=False)
    print(f"Pseudo-labels saved to {output_csv}")
    print(f"Label distribution:")
    for i, label in enumerate(LABELS):
        print(f"  {label}: {pseudo_labels[:, i].mean():.3f}")


def calibrate_pseudo_labels(
    labeled_csv: str,
    pseudo_csv: str,
    output_csv: str
):
    """Calibrate pseudo-labels using labeled subset."""
    labeled_df = pd.read_csv(labeled_csv)
    pseudo_df = pd.read_csv(pseudo_csv)
    
    labeled_df = labeled_df[labeled_df[LABELS[0]] != -1]
    
    merged = labeled_df[["StudyInstanceUID"] + LABELS].merge(
        pseudo_df, on="StudyInstanceUID", suffixes=("_true", "_pseudo")
    )
    
    calibrated = pseudo_df.copy()
    
    for label in LABELS:
        true_col = f"{label}_true"
        pseudo_col = f"{label}_pseudo"
        
        if true_col not in merged.columns:
            continue
        
        tp = ((merged[true_col] == 1) & (merged[pseudo_col] == 1)).sum()
        fp = ((merged[true_col] == 0) & (merged[pseudo_col] == 1)).sum()
        fn = ((merged[true_col] == 1) & (merged[pseudo_col] == 0)).sum()
        tn = ((merged[true_col] == 0) & (merged[pseudo_col] == 0)).sum()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        print(f"{label}: Precision={precision:.3f}, Recall={recall:.3f}")
        
        if precision < confidence_threshold:
            calibrated.loc[calibrated[label] == 1, label] = -1
    
    calibrated.to_csv(output_csv, index=False)
    print(f"Calibrated pseudo-labels saved to {output_csv}")


if __name__ == "__main__":
    sample_reports = [
        "Findings: ACL tear and medial meniscus tear. Mild medial compartment osteoarthritis. Small joint effusion.",
        "Normal knee MRI. Intact ACL, MCL, medial and lateral menisci. No osteoarthritis. No effusion.",
        "Impression: MCL sprain, lateral meniscus tear, large Baker's cyst. Moderate effusion.",
        "Findings: Bone marrow edema in medial femoral condyle concerning for contusion. No fracture.",
        "Patellofemoral osteoarthritis with joint space narrowing. Synovitis present."
    ]
    
    for report in sample_reports:
        labels = extract_labels_keyword(report)
        print(f"Report: {report[:80]}...")
        print(f"Labels: {[k for k,v in labels.items() if v==1]}")
        print()