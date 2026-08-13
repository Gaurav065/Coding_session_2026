# Data Stewardship Agent - Project Architecture

Welcome to the automated agent repository for dynamic market stewardship.

## Project Structure

*   **`src/`**
    *   **`main.py`**: The core controller. This houses our current agent logic, which uses a fixed-heuristic Marginal Action Value (MAV) strategy. It is highly optimized for static markets but vulnerable to adversarial price manipulation.
    *   **`test.py`**: The local evaluation harness (run `python test.py -o opponent_script.py` to benchmark).
    *   **`run_eval.py`**: Batch evaluation script that pits our agent against all historical adversarial logs in the `replays/` folder.
    *   **`replay_agent.py`**: A specialized proxy agent used by `run_eval.py` to parse transaction logs and simulate historical opponents in our test harness.
*   **`replays/`**
    *   Contains the historical transaction logs (JSON format) of the top-performing adversarial models.
*   **`context_handoff.md`**
    *   Detailed architectural findings, constraints, and the roadmap for the next phase of development (moving from fixed heuristics to Reinforcement Learning / Minimax algorithms).

## Current Status & Roadmap
Our fixed-heuristic approach has reached its ceiling. It is highly efficient at capitalizing on high-yield assets (producing 100k+ value against naive markets). However, batch testing has revealed that top-tier adversaries use aggressive market manipulation (flooding the market to crash our asset prices). 

**Next Phase:** Implement an advanced, dynamic algorithmic model (RL, Minimax, or MCTS) in `src/main.py` capable of projecting price elasticity and countering adversarial market dumps. Please read `context_handoff.md` for full details.
