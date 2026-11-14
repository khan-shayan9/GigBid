# source: synthetic · persona: ai_ml_engineer · repo: cv-matcher
import numpy as np


def top_sentences(cv_vectors: np.ndarray, job_vector: np.ndarray, k: int = 3) -> list[int]:
    scores = cv_vectors @ job_vector / (
        np.linalg.norm(cv_vectors, axis=1) * np.linalg.norm(job_vector) + 1e-9
    )
    return list(np.argsort(-scores)[:k])


def score_candidate(cv_vectors: np.ndarray, job_vector: np.ndarray) -> float:
    # mean of the best three sentences beats whole-document similarity on long CVs
    best = top_sentences(cv_vectors, job_vector)
    sims = cv_vectors[best] @ job_vector
    return float(np.mean(sims))
