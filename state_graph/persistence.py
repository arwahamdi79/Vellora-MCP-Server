"""Durable state/checkpoint layer for all state graphs."""
from pathlib import Path
import json, sqlite3, uuid
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "vellora_therapeutics.db"

def now(): return datetime.now(timezone.utc).isoformat()

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def create_run(graph_name, state):
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    t=now()
    with db() as c:
        c.execute("INSERT INTO state_runs VALUES (?,?,?,?,?,?,?,?)",
                  (run_id, graph_name, "running", state.get("current_state","start"),
                   json.dumps(state), t,t,None))
    return run_id

def save_checkpoint(run_id, state, current_state):
    checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}"
    t=now()
    with db() as c:
        c.execute("UPDATE state_runs SET current_state=?, state_data=?, updated_at=? WHERE run_id=?",
                  (current_state,json.dumps(state),t,run_id))
        c.execute("INSERT INTO checkpoints VALUES (?,?,?,?,?)",
                  (checkpoint_id,run_id,json.dumps(state),current_state,t))
    return checkpoint_id

def load_latest_checkpoint(run_id):
    with db() as c:
        row=c.execute("""SELECT checkpoint_id,state_data,current_state
                         FROM checkpoints WHERE run_id=? ORDER BY created_at DESC LIMIT 1""",(run_id,)).fetchone()
    if not row: return None
    return {"checkpoint_id":row[0],"state":json.loads(row[1]),"current_state":row[2]}

def set_run_status(run_id,status,error=None):
    with db() as c:
        c.execute("UPDATE state_runs SET status=?, error=?, updated_at=? WHERE run_id=?",
                  (status,error,now(),run_id))

def create_hitl(run_id, checkpoint_id, reason, state):
    task=f"hitl_{uuid.uuid4().hex[:10]}"
    with db() as c:
        c.execute("""INSERT INTO hitl_tasks
          (task_id,run_id,checkpoint_id,status,reason,state_data,created_at)
          VALUES (?,?,?,?,?,?,?)""",
          (task,run_id,checkpoint_id,"pending",reason,json.dumps(state),now()))
    set_run_status(run_id,"waiting_hitl")
    return task

def resolve_hitl(task_id, decision, actor="admin"):
    with db() as c:
        row=c.execute("SELECT run_id FROM hitl_tasks WHERE task_id=?",(task_id,)).fetchone()
        if not row: raise ValueError("Unknown HITL task")
        c.execute("""UPDATE hitl_tasks SET status=?,decision=?,resolved_at=?,resolved_by=?
                     WHERE task_id=?""",("resolved",decision,now(),actor,task_id))
    set_run_status(row[0],"running")
    return row[0]

def create_ticket(run_id, checkpoint_id, error, state):
    ticket=f"ticket_{uuid.uuid4().hex[:10]}"
    with db() as c:
        c.execute("""INSERT INTO tickets
          (ticket_id,run_id,checkpoint_id,status,error,state_data,created_at)
          VALUES (?,?,?,?,?,?,?)""",
          (ticket,run_id,checkpoint_id,"open",str(error),json.dumps(state),now()))
    set_run_status(run_id,"failed",str(error))
    return ticket

def resolve_ticket(ticket_id, resolution="retry", actor="admin"):
    with db() as c:
        row=c.execute("SELECT run_id FROM tickets WHERE ticket_id=?",(ticket_id,)).fetchone()
        if not row: raise ValueError("Unknown ticket")
        c.execute("""UPDATE tickets SET status=?,resolved_at=?,resolved_by=?,resolution=?
                     WHERE ticket_id=?""",("resolved",now(),actor,resolution,ticket_id))
    set_run_status(row[0],"running")
    return row[0]
