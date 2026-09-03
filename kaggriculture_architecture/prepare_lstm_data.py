import numpy as np

def generate_lstm_sequences(seq_length=10):
    print("Loading raw tensors...")
    X_scal = np.load("X_scalar.npy")
    X_spat = np.load("X_spatial.npy")
    Y_act = np.load("Y_actions.npy")
    
    print(f"Loaded {len(X_scal)} total frames.")
    
    # Feature 0 is step/2000.0. When it drops, a new game started.
    steps = X_scal[:, 0]
    drops = np.where(np.diff(steps) < 0)[0] + 1
    game_boundaries = [0] + drops.tolist() + [len(X_scal)]
    
    X_scal_seq, X_spat_seq, Y_act_seq = [], [], []
    
    print(f"Found {len(game_boundaries)-1} games. Generating sequences of length {seq_length}...")
    
    for i in range(len(game_boundaries)-1):
        start = game_boundaries[i]
        end = game_boundaries[i+1]
        
        # We need at least 'seq_length' frames in a game to make a sequence
        if end - start < seq_length: continue
        
        for j in range(start, end - seq_length + 1):
            X_scal_seq.append(X_scal[j:j+seq_length])
            X_spat_seq.append(X_spat[j:j+seq_length])
            Y_act_seq.append(Y_act[j:j+seq_length])
            
    X_scal_seq = np.array(X_scal_seq, dtype=np.float32)
    X_spat_seq = np.array(X_spat_seq, dtype=np.float32)
    Y_act_seq = np.array(Y_act_seq, dtype=np.float32)
    
    print(f"Generated {len(X_scal_seq)} LSTM sequences.")
    print(f"X_scalar_seq shape: {X_scal_seq.shape}")
    print(f"X_spatial_seq shape: {X_spat_seq.shape}")
    
    np.save("X_scalar_seq.npy", X_scal_seq)
    np.save("X_spatial_seq.npy", X_spat_seq)
    np.save("Y_actions_seq.npy", Y_act_seq)
    print("Saved sequential tensors!")

if __name__ == "__main__":
    generate_lstm_sequences()
