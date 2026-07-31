"""
Conversation Memory
"""

from dataclasses import dataclass, field


@dataclass
class ConversationMemory:

    messages: list = field(default_factory=list)

    # ------------------------------------

    def add_user(self, text: str):

        self.messages.append(
            {
                "role": "user",
                "text": text,
            }
        )

    # ------------------------------------

    def add_assistant(self, text: str):

        self.messages.append(
            {
                "role": "assistant",
                "text": text,
            }
        )

    # ------------------------------------

    def add_tool(
        self,
        tool_name: str,
        result,
    ):

        self.messages.append(
            {
                "role": "tool",
                "tool": tool_name,
                "result": str(result),
            }
        )

    # ------------------------------------

    def history(self):

        return self.messages

    # ------------------------------------

    def last_messages(
        self,
        count: int = 10,
    ):

        return self.messages[-count:]

    # ------------------------------------

    def clear(self):

        self.messages.clear()

    # ------------------------------------

    def __len__(self):

        return len(self.messages)
