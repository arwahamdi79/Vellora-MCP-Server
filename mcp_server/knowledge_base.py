class KnowledgeBase:

    def __init__(self):
        self.documents = []


    def add_document(self, text):
        self.documents.append(text)


    def search(self, query, top_k=3):

        query_words = query.lower().split()

        scores = []

        for doc in self.documents:

            score = 0

            for word in query_words:
                if word in doc.lower():
                    score += 1

            scores.append(
                (score, doc)
            )


        scores.sort(
            reverse=True,
            key=lambda x: x[0]
        )


        return [
            doc
            for score, doc in scores[:top_k]
            if score > 0
        ]