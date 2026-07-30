from dataclasses import dataclass, field


@dataclass
class ConversationMemory:

    messages: list = field(default_factory=list)

    def add_user(self, text: str):

        self.messages.append(
            {
                "role": "user",
                "text": text
            }
        )

    def add_assistant(self, text: str):

        self.messages.append(
            {
                "role": "assistant",
                "text": text
            }
        )

    def add_tool(self, tool: str, result):

        self.messages.append(
            {
                "role": "tool",
                "tool": tool,
                "result": result
            }
        )

    def history(self):

        return self.messages

    def clear(self):

        self.messages.clear()
