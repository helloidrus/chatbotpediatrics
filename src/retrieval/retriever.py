import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer


class Retriever:
    def __init__(self,
                 index_path="index/faiss.index",
                 chunks_path="index/chunks.pkl",
                 embedding_model="BAAI/bge-m3"):

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

        for i, idx in enumerate(ids[0]):
            if idx < len(self.documents):
                results.append(self.documents[idx])

        return results, scores
