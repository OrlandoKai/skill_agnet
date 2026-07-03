from pathlib import Path

from config import SKILL_LIBRARY_PATH
from .base import BaseRetriever, skill_to_document, tokenize


class BM25SkillRetriever(BaseRetriever):
    def __init__(self, library_path: str | Path = SKILL_LIBRARY_PATH) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise ImportError(
                "rank-bm25 is not installed. Install dependencies with: pip install -r requirements.txt"
            ) from exc

        super().__init__(library_path)
        self.documents = [skill_to_document(skill) for skill in self.skills]
        self.tokenized_documents = [tokenize(document) for document in self.documents]
        self.bm25 = BM25Okapi(self.tokenized_documents)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.skills:
            return []
        tokens = tokenize(query)
        if not tokens:
            return [
                {**skill, "score": 0.0}
                for skill in self.skills[: max(0, min(top_k, len(self.skills)))]
            ]

        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return [
            {**self.skills[index], "score": float(score)}
            for index, score in ranked[: max(0, top_k)]
        ]
