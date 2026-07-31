from .instance import mcp


@mcp.prompt()
def batch_analysis_prompt(batch_id:int):
    
    """
    Analyze a manufacturing batch quality status.
    """

    return f"""
Analyze manufacturing batch {batch_id}.

Check:
- batch status
- quality tests
- possible risks
- recommended action

Use only available Vellora company data.
"""



@mcp.prompt()
def recall_explanation_prompt(batch_id: int):
    """
    Generate a professional product recall explanation.
    """

    return f"""
Prepare a professional explanation
for recalling manufacturing batch {batch_id}.

Include:
- recall reason
- affected batch
- safety actions
- recommended next steps
"""