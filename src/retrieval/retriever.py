import numpy as np
import pickle


MIN_RELEVANCE_SCORE = 0.35  # BGE-M3 cosine similarity threshold


class Retriever:
    def __init__(self,
                 index_path="index/faiss.index",
                 chunks_path="index/chunks.pkl",
                 embedding_model="BAAI/bge-m3"):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError(
                "Package 'faiss' is not installed. Install it first, for example: "
                "pip install faiss-cpu"
            ) from exc

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Package 'sentence-transformers' is not installed. Install it first, "
                "for example: pip install sentence-transformers"
            ) from exc

        self.model = SentenceTransformer(embedding_model) # Load the embedding model
        self.index = faiss.read_index(index_path) # Load the FAISS index

        with open(chunks_path, "rb") as f:
            self.documents = pickle.load(f)

    def search(self, query, top_k=3):

        query = "Represent this sentence for searching relevant passages: " + query

        q_emb = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        scores, ids = self.index.search(
            np.array(q_emb).astype("float32"),
            top_k
        )

        results = []
        filtered_scores = []

        for i, idx in enumerate(ids[0]):
            score = float(scores[0][i])
            if 0 <= idx < len(self.documents) and score >= MIN_RELEVANCE_SCORE:
                results.append(self.documents[idx])
                filtered_scores.append(score)

        return results, np.array([filtered_scores], dtype=np.float32)
