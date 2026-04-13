def skill_overlap_score(jd, candidate):
    jd_skills = [skill["name"] for skill in jd["skills"]]
    cand_skills = candidate["skills"]
    overlap = set(jd_skills).intersection(set(cand_skills))
    score = len(overlap) / len(jd_skills)
    return float(score)
