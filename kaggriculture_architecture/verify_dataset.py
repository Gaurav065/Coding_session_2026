import numpy as np
import sys

def verify():
    print("Loading datasets...")
    try:
        X_scal = np.load("X_scalar.npy")
        X_spat = np.load("X_spatial.npy")
        Y = np.load("Y_actions.npy")
    except FileNotFoundError:
        print("Error: .npy files not found. Run parse_810_replays.py first.")
        sys.exit(1)
        
    print(f"\n--- Dataset Shape ---")
    print(f"X_scalar: {X_scal.shape}")
    print(f"X_spatial: {X_spat.shape}")
    print(f"Y_actions: {Y.shape}")
    
    print(f"\n--- 1. NaN / Inf Check ---")
    print("X_scalar NaNs:", np.isnan(X_scal).any())
    print("X_spatial NaNs:", np.isnan(X_spat).any())
    print("Y_actions NaNs:", np.isnan(Y).any())
    
    print(f"\n--- 2. Normalization Bounds ---")
    print(f"X_scalar Min/Max: {X_scal.min():.2f} / {X_scal.max():.2f}")
    print(f"X_spatial Min/Max: {X_spat.min():.2f} / {X_spat.max():.2f}")
    print(f"Y_actions Min/Max: {Y.min():.2f} / {Y.max():.2f}")
    if X_scal.max() > 20.0:
        print("WARNING: X_scalar has very large values. Neural network gradients may explode.")
        
    print(f"\n--- 3. Action Sparsity (Total Weighted Executions) ---")
    actions = ["Buy WHEAT", "Buy CARROT", "Buy TOMATO", "Buy STRAW", "Buy MELON", 
               "Buy GOOSE", "Buy COW", "Buy SHEEP", "HIRE",
               "Sell WHEAT", "Sell CARROT", "Sell TOMATO", "Sell STRAW", "Sell MELON", 
               "Sell EGG", "Sell MILK", "Sell WOOL"]
               
    sums = Y.sum(axis=0)
    for name, total in zip(actions, sums):
        if total == 0:
            print(f"{name:15s}: {total:.1f}  <-- WARNING: ZERO SAMPLES!")
        else:
            print(f"{name:15s}: {total:.1f}")
        
    print(f"\n--- 4. Visual Spatial Sanity Check (Random Frame) ---")
    idx = np.random.randint(0, len(X_scal))
    print("Crop Grid (Channel 0):")
    print(X_spat[idx, 0, :, :])
    print("\nWorker Grid (Channel 2):")
    print(X_spat[idx, 2, :, :])
    
    print("\nVerification Complete!")

if __name__ == "__main__":
    verify()
