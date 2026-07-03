from .base import BaseRetriever


class FullPromptRetriever(BaseRetriever):
    """Return every skill as the Full Skill Prompt baseline."""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return [{**skill, "score": 1.0} for skill in self.skills]
