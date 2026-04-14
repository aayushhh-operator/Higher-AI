from app.services.embeddings import get_similarity
from app.services.skill_engine import expand


def skill_overlap_score(jd, candidate):
    jd_skills = [skill["name"] for skill in jd["skills"]]
    cand_skills = expand(candidate["skills"])
    overlap = set(jd_skills).intersection(set(cand_skills))
    score = len(overlap) / len(jd_skills)
    return float(score)


def semantic_score(jd, candidate):
    jd_text = jd["description"]
    cand_text = " ".join(candidate["skills"])
    return get_similarity(jd_text, cand_text)


def penalty_bonus(jd, candidate):
    jd_skill_map = {skill["name"]: skill for skill in jd["skills"]}
    cand_skills = set(candidate["skills"])
    penalty = 0

    for skill_name, meta in jd_skill_map.items():
        if meta["required"] is True and skill_name not in cand_skills:
            penalty += 0.1

    bonus = 0
    extra = cand_skills - set(jd_skill_map.keys())
    bonus = min(len(extra) * 0.02, 0.1)

    return (penalty, bonus)


def final_score(jd, candidate):
    skill = skill_overlap_score(jd, candidate)
    semantic = semantic_score(jd, candidate)
    exp = min(candidate["experience"] / jd["experience"], 1.0)
    score = (skill * 0.5) + (semantic * 0.3) + (exp * 0.2)
    penalty, bonus = penalty_bonus(jd, candidate)
    score = score - penalty + bonus
    score = max(0.0, min(1.0, score))
    return float(score)
