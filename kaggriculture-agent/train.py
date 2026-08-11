import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from kaggle_environments import make

# ---------------------------------------------------------
# Default Genome
# ---------------------------------------------------------
# We map parameters to continuous genes [0.0, 1.0] to make mutation easy.
GENOME_DEF = {
    "buy_NE_thresh": {"min": 1000, "max": 4000},
    "buy_SW_thresh": {"min": 2000, "max": 6000},
    "buy_SE_thresh": {"min": 8000, "max": 25000},
    "max_hands_per_quadrant": {"min": 1, "max": 15},
    "wheat_ratio": {"min": 0.15, "max": 0.40},
    "cow_target": {"min": 0, "max": 10},
    "sheep_target": {"min": 0, "max": 10},
    "goose_target": {"min": 0, "max": 5},
    "stop_investment_day": {"min": 22, "max": 28}
}

def decode_genome(genome):
    params = {}
    for key, bounds in GENOME_DEF.items():
        val = genome[key]
        span = bounds["max"] - bounds["min"]
        decoded = bounds["min"] + (val * span)
        if isinstance(bounds["min"], int):
            decoded = int(round(decoded))
        params[key] = decoded
        
    return params

def create_random_genome():
    return {k: random.random() for k in GENOME_DEF.keys()}

def mutate(genome, mutation_rate=0.2, mutation_strength=0.1):
    new_genome = genome.copy()
    for k in new_genome.keys():
        if random.random() < mutation_rate:
            new_genome[k] = max(0.0, min(1.0, new_genome[k] + random.uniform(-mutation_strength, mutation_strength)))
    return new_genome

def crossover(g1, g2):
    return {k: g1[k] if random.random() < 0.5 else g2[k] for k in g1.keys()}

def evaluate_genome(genome):
    # This runs in a subprocess.
    params = decode_genome(genome)
    
    import strategy
    strategy.GLOBAL_PARAMS = params
    from main import agent
    
    env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=False)
    env.run([agent, 'starter'])
    
    # Return the reward (money) of our agent (player 0)
    score = env.steps[-1][0].reward
    return score, genome

def main():
    POPULATION_SIZE = 12
    GENERATIONS = 10
    
    population = [create_random_genome() for _ in range(POPULATION_SIZE)]
    
    for gen in range(GENERATIONS):
        print(f"--- Generation {gen+1} ---")
        start_t = time.time()
        
        # Evaluate concurrently
        with ProcessPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(evaluate_genome, population))
            
        results.sort(key=lambda x: x[0], reverse=True)
        
        best_score = results[0][0]
        avg_score = sum(r[0] for r in results) / len(results)
        print(f"Best Score: {best_score} | Avg Score: {avg_score:.1f} | Time: {time.time() - start_t:.1f}s")
        
        best_params = decode_genome(results[0][1])
        print(f"Best Params: {best_params}")
        
        # Save best to file
        with open('best_params.json', 'w') as f:
            json.dump(best_params, f, indent=4)
            
        # Elitism + Selection
        new_population = [results[0][1], results[1][1]]
        
        while len(new_population) < POPULATION_SIZE:
            parent1 = random.choice(results[:4])[1]
            parent2 = random.choice(results[:4])[1]
            child = crossover(parent1, parent2)
            child = mutate(child)
            new_population.append(child)
            
        population = new_population

if __name__ == '__main__':
    main()
