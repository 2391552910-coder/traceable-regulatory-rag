"""
稠密向量检索

默认 BGE-M3（sentence-transformers 本地加载，1024 维，归一化后点积=余弦）。
embedding_backend=tfidf 时降级为 TF-IDF 余弦（供无 GPU/无法下载模型时的冒烟测试）。
"""
import numpy as np

from src.data.clause_splitter import Chunk


class DenseRetriever:
    def __init__(self, chunks: list[Chunk], backend: str = "bge",
                 model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self.chunks = chunks
        self.backend = backend
        if backend == "bge":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name, device=device)
            self._encode = lambda texts: self._model.encode(
                texts, normalize_embeddings=True)
        elif backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            from src.retrieval.bm25 import tokenize
            self._vectorizer = TfidfVectorizer(tokenizer=tokenize)
            corpus = [c.text for c in chunks]
            self._matrix = self._vectorizer.fit_transform(corpus).toarray()
            norms = np.linalg.norm(self._matrix, axis=1, keepdims=True)
            self._matrix = self._matrix / np.clip(norms, 1e-9, None)

            def _encode(texts):
                m = self._vectorizer.transform(texts).toarray()
                norms = np.linalg.norm(m, axis=1, keepdims=True)
                return m / np.clip(norms, 1e-9, None)
            self._encode = _encode
        else:
            raise ValueError(f"未知嵌入后端: {backend}")

        if backend == "bge":
            self._matrix = self._encode([c.text for c in chunks])

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        q_vec = self._encode([query])[0]
        scores = self._matrix @ q_vec
        idx = np.argsort(-scores)[:top_k]
        return [(self.chunks[i], float(scores[i])) for i in idx]
