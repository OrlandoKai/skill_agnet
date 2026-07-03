from pathlib import Path

import numpy as np

from config import SKILL_LIBRARY_PATH
from .base import BaseRetriever, skill_to_document


class EmbeddingSkillRetriever(BaseRetriever):
    def __init__(
        self,
        library_path: str | Path = SKILL_LIBRARY_PATH,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        super().__init__(library_path)
        self.model_name = model_name
        self.device = device

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. Install dependencies with: pip install -r requirements.txt"
            ) from exc

        try:
            self.model = SentenceTransformer(model_name, device=device)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load embedding model "
                f"{model_name!r}. This may require internet access on first use, "
                "or a pre-downloaded local Hugging Face cache."
            ) from exc

        self.skill_texts = [skill_to_document(skill) for skill in self.skills]
        self.skill_embeddings = self.model.encode(
            self.skill_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.skills:
            return []
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        scores = np.dot(self.skill_embeddings, query_embedding)
        ranked = np.argsort(scores)[::-1][: max(0, top_k)]
        return [
            {**self.skills[index], "score": float(scores[index])}
            for index in ranked
        ]
