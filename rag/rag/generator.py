"""
LLM Generator
"""

from typing import List
from .models import RetrievedChunk


class LLMGenerator:

    def __init__(self, llm):

        self.llm = llm

    def build_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ):

        context = "\n\n".join(

            [
                f"[Document {i+1}]\n{chunk.content}"
                for i, chunk in enumerate(chunks)
            ]

        )

        prompt = f"""
You are an AI assistant.

Answer ONLY using the retrieved context.

If the answer does not exist in the context,
reply with:

"I couldn't find that information."

----------------------

Context

{context}

----------------------

Question

{query}

----------------------

Answer
"""

        return prompt

    def generate_answer(
        self,
        query,
        chunks
    ):

        prompt = self.build_prompt(
            query,
            chunks
        )

        response = self.llm.invoke(prompt)

        if hasattr(response, "content"):

            return response.content

        return str(response)