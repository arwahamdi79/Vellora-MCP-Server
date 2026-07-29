async def request_human_confirmation(ctx, action_description: str) -> bool:
   
    client_caps = getattr(ctx.session, "client_capabilities", {})
    if not client_caps.get("elicitation"):
        raise PermissionError(
            "Client does not support Elicitation protocol. High-risk actions are blocked."
        )

    prompt_message = (
        f"HIGH-RISK ACTION REQUIRED\n"
        f"Action: {action_description}\n"
        f"Do you explicitly authorize this database state change? (yes/no)"
    )

    result = await ctx.session.create_elicitation(message=prompt_message)
    user_response = result.get("answer", "").strip().lower()

    return user_response in ["yes", "y", "true"]