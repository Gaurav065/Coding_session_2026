import torch
import numpy as np
import json
import time
from spatial_micro_agent import NeuralSpatialMicroAgent

def evaluate_model(model_path, test_chunk_path):
    print(f"Loading Model: {model_path}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    model = NeuralSpatialMicroAgent(in_channels=20, goal_dim=100, action_dim=11).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    print(f"Loading Validation Data: {test_chunk_path}")
    data = np.load(test_chunk_path)
    spatial = torch.tensor(data['spatial'], dtype=torch.float32).to(device)
    scalar = torch.tensor(data['scalar'], dtype=torch.float32).to(device)
    micro_strs = data['micro']
    
    action_to_idx = {
        "NORTH": 0, "SOUTH": 1, "EAST": 2, "WEST": 3,
        "PICKUP": 4, "DROP": 5, "PLANT": 6, "WATER": 7, 
        "DIG": 8, "FERTILIZE": 9
    }
    
    print("Parsing Grandmaster Ground Truth...")
    targets = []
    for m_str in micro_strs:
        try:
            d = json.loads(m_str)
            idx = 10 # NOOP
            if isinstance(d, dict) and "farmer" in d and len(d["farmer"]) > 0:
                atype = d["farmer"][0]
                idx = action_to_idx.get(atype, 10)
        except:
            idx = 10
        targets.append(idx)
        
    targets = torch.tensor(targets, dtype=torch.long).to(device)
    
    print(f"Running Forward Pass on {len(targets)} frames...")
    start_t = time.time()
    
    # Process in batches to avoid RAM OOM on CPU
    batch_size = 512
    predictions = []
    
    with torch.no_grad():
        for i in range(0, len(targets), batch_size):
            spat_b = spatial[i:i+batch_size]
            scal_b = scalar[i:i+batch_size]
            
            # Autocast prevents Float16/Float32 mismatch issues depending on CPU support
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16 if device.type == 'cpu' else torch.float16, enabled=torch.cuda.is_available()):
                logits, _ = model(spat_b, scal_b)
                preds = torch.argmax(logits, dim=1)
                predictions.extend(preds.cpu().numpy())
                
    predictions = torch.tensor(predictions, dtype=torch.long).to(device)
    inf_time = time.time() - start_t
    print(f"Inference finished in {inf_time:.2f} seconds.")
    
    # Calculate Metrics
    correct = (predictions == targets).sum().item()
    total = targets.size(0)
    accuracy = (correct / total) * 100
    
    print(f"\n" + "="*40)
    print(f"      EVALUATION RESULTS")
    print(f"="*40)
    print(f"Total Test Frames  : {total}")
    print(f"Validation Accuracy: {accuracy:.2f}%")
    print(f"="*40)
    
    print("\nACTION DISTRIBUTION (Predicted vs Real Grandmaster)")
    print("-" * 55)
    idx_to_action = {v: k for k, v in action_to_idx.items()}
    idx_to_action[10] = "NOOP"
    
    pred_counts = torch.bincount(predictions, minlength=11).cpu().numpy()
    target_counts = torch.bincount(targets, minlength=11).cpu().numpy()
    
    print(f"{'ACTION'.ljust(12)} | {'AI PREDICTED'.ljust(15)} | {'REAL PRO'.ljust(15)}")
    print("-" * 55)
    for i in range(11):
        action_name = idx_to_action[i]
        p_c = str(pred_counts[i])
        t_c = str(target_counts[i])
        print(f"{action_name.ljust(12)} | {p_c.ljust(15)} | {t_c.ljust(15)}")
        
if __name__ == "__main__":
    evaluate_model("training_weights/micro_agent_bc_epoch_3.pth", "data/elite_1900_chunk_99.npz")
