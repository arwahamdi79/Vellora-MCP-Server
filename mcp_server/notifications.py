async def notify_tools_list_changed(ctx):
   
    try:
        await ctx.session.send_notification("notifications/tools/list_changed", {})
        return True
    except Exception as e:
        print(f"Failed to send tools/list_changed notification: {str(e)}")
        return False