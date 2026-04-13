from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


model = SentenceTransformer("all-MiniLM-L6-v2")


def get_similarity(text1, text2):
    vec1 = model.encode(text1)
    vec2 = model.encode(text2)
    return float(cosine_similarity([vec1], [vec2])[0][0])
