from app.services.embeddings import get_similarity


def skill_overlap_score(jd, candidate):
    jd_skills = [skill["name"] for skill in jd["skills"]]
    cand_skills = candidate["skills"]
    overlap = set(jd_skills).intersection(set(cand_skills))
    score = len(overlap) / len(jd_skills)
    return float(score)


def semantic_score(jd, candidate):
    jd_text = jd["description"]
    cand_text = " ".join(candidate["skills"])
    return get_similarity(jd_text, cand_text)


def final_score(jd, candidate):
    skill = skill_overlap_score(jd, candidate)
    semantic = semantic_score(jd, candidate)
    exp = min(candidate["experience"] / jd["experience"], 1.0)
    score = (skill * 0.5) + (semantic * 0.3) + (exp * 0.2)
    return float(score)
