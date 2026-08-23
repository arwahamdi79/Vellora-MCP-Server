"""Small, durable state-graph engine used by the three business workflows."""
from .persistence import create_run, save_checkpoint, load_latest_checkpoint, set_run_status, create_hitl, create_ticket

TECHNIQUES = {
 "batch_release": ("task_decomposition","rag"),
 "recall_coordination": ("constrained_react","tree_of_thoughts"),
 "supplier_capa": ("task_decomposition","rag"),
}

class StateGraph:
    name="base"
    states=()
    def __init__(self, state=None, run_id=None):
        self.state=state or {"current_state":"start","completed_steps":[]}
        self.run_id=run_id or create_run(self.name,self.state)
    def checkpoint(self,state):
        self.state=state
        return save_checkpoint(self.run_id,state,state["current_state"])
    def finish(self):
        set_run_status(self.run_id,"completed")
        return self.state

class BatchReleaseGraph(StateGraph):
    name="batch_release"; states=("start","verify_quality","check_regulatory","awaiting_approval","release","complete")
    def run_until_hitl(self):
        for s in ["start","verify_quality","check_regulatory"]:
            self.state["current_state"]=s
            self.state["completed_steps"].append(s)
            self.checkpoint(self.state)
        self.state["current_state"]="awaiting_approval"
        cp=self.checkpoint(self.state)
        task=create_hitl(self.run_id,cp,"New supplier requires regulatory approval",self.state)
        return {"status":"waiting_hitl","run_id":self.run_id,"checkpoint_id":cp,"task_id":task,"state":self.state}
    def resume(self, decision="approved"):
        if decision != "approved": set_run_status(self.run_id,"rejected"); return self.state
        for s in ["release","complete"]:
            self.state["current_state"]=s; self.state["completed_steps"].append(s); self.checkpoint(self.state)
        return self.finish()

class RecallCoordinationGraph(StateGraph):
    name="recall_coordination"; states=("start","investigate","supplier_response","recovery_plan","complete")
    def run(self, fail=False):
        for s in ["start","investigate"]:
            self.state["current_state"]=s; self.state["completed_steps"].append(s); self.checkpoint(self.state)
        self.state["current_state"]="supplier_response"; cp=self.checkpoint(self.state)
        if fail:
            ticket=create_ticket(self.run_id,cp,"Supplier API timeout",self.state)
            return {"status":"failed","ticket_id":ticket,"checkpoint_id":cp,"run_id":self.run_id}
        for s in ["recovery_plan","complete"]:
            self.state["current_state"]=s; self.state["completed_steps"].append(s); self.checkpoint(self.state)
        return self.finish()

class SupplierCAPAGraph(StateGraph):
    name="supplier_capa"; states=("start","investigate","draft_capa","awaiting_approval","implement","complete")
    def run_until_checkpoint(self):
        for s in ["start","investigate","draft_capa"]:
            self.state["current_state"]=s; self.state["completed_steps"].append(s); self.checkpoint(self.state)
        return self.run_id, load_latest_checkpoint(self.run_id)
    def resume(self):
        for s in ["implement","complete"]:
            self.state["current_state"]=s; self.state["completed_steps"].append(s); self.checkpoint(self.state)
        return self.finish()
