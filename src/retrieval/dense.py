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
            from sklearn.preprocessing import normalize as sp_normalize
            from src.retrieval.bm25 import tokenize
            # 限制特征上限 + 保持稀疏矩阵，避免大规模语料下稠密化 OOM
            self._vectorizer = TfidfVectorizer(tokenizer=tokenize,
                                               max_features=60000, min_df=2)
            corpus = [c.text for c in chunks]
            self._matrix = sp_normalize(self._vectorizer.fit_transform(corpus))
            self._sparse = True

            def _encode(texts):
                return sp_normalize(self._vectorizer.transform(texts))
            self._encode = _encode
        else:
            raise ValueError(f"未知嵌入后端: {backend}")
        self._sparse = backend == "tfidf"

        if backend == "bge":
            self._matrix = self._encode([c.text for c in chunks])

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        q_vec = self._encode([query])
        if self._sparse:
            scores = (self._matrix @ q_vec.T).toarray().ravel()
        else:
            scores = self._matrix @ q_vec[0]
        idx = np.argsort(-scores)[:top_k]
        return [(self.chunks[i], float(scores[i])) for i in idx]
