import json
import pandas as pd

from rag.rag.factory import RAGFactory
from rag.rag.retrieval_eval.metrics import RetrievalMetrics


class RetrievalEvaluator:

    def __init__(

        self,

        llm,

        architecture,

        bm25_chunks=None

    ):

        self.rag = RAGFactory.create(

            architecture,

            llm,

            bm25_chunks=bm25_chunks

        )

    def evaluate(

        self,

        questions_file

    ):

        with open(

            questions_file,

            "r",

            encoding="utf8"

        ) as f:

            questions = json.load(f)

        rows = []

        for item in questions:

            response = self.rag.process(

                item["question"]

            )

            rows.append(

                {

                    "Question": item["question"],

                    "Architecture":

                    response.metadata.architecture,

                    "Accuracy":

                    RetrievalMetrics.retrieval_accuracy(

                        response,

                        item["expected_source"]

                    ),

                    "Similarity":

                    RetrievalMetrics.average_similarity(

                        response

                    ),

                    "Latency(ms)":

                    RetrievalMetrics.latency(

                        response

                    ),

                    "Confidence":

                    RetrievalMetrics.confidence(

                        response

                    ),

                    "Tokens":

                    RetrievalMetrics.token_usage(

                        response

                    )

                }

            )

        df = pd.DataFrame(rows)

        df.to_csv(

            "retrieval_results.csv",

            index=False

        )

        print(df)

        print()

        print(df.mean(numeric_only=True))