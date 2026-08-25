"""Master 14-Animal Dispatcher Agent Submission - Project Maestro"""

from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

_agent_p0 = None
_agent_p1 = None

def agent(obs):
    global _agent_p0, _agent_p1
    player = obs["player"]
    if player == 0:
        if _agent_p0 is None or obs["step"] == 0:
            _agent_p0 = make_spatial_dispatcher_agent()
        return _agent_p0(obs)
    else:
        if _agent_p1 is None or obs["step"] == 0:
            _agent_p1 = make_spatial_dispatcher_agent()
        return _agent_p1(obs)
