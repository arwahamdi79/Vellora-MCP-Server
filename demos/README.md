# Final Project demos

- `python demos/demo_hitl_pause.py --auto-approve`
- `python demos/demo_failure_ticket.py`
- `python demos/demo_crash_resume.py` then `python demos/demo_crash_resume.py --resume`

The first two demonstrate durable checkpoints and distinct HITL/ticket paths. The third persists a run, exits the process, then reloads it from SQLite.
