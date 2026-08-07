from rag.factory import RAGFactory


class VelloraAgent:

    def __init__(

        self,

        llm,

        architecture="agentic",

        bm25_chunks=None

    ):

        self.rag = RAGFactory.create(

            architecture,

            llm,

            bm25_chunks=bm25_chunks

        )

    def ask(

        self,

        question

    ):

        response = self.rag.process(

            question

        )

        return {

            "answer": response.answer,

            "verified":

            response.metadata.verified,

            "confidence":

            response.metadata.confidence,

            "sources":

            [

                chunk.source

                for chunk in response.retrieved_chunks

            ]

        }