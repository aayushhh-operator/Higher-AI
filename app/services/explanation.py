def structured_explanation(jd, candidate):
    jd_skills = [skill["name"] for skill in jd["skills"]]
    cand_skills = candidate["skills"]

    jd_skill_set = set(jd_skills)
    cand_skill_set = set(cand_skills)

    matched = list(jd_skill_set.intersection(cand_skill_set))
    missing = list(jd_skill_set - cand_skill_set)
    extra = list(cand_skill_set - jd_skill_set)

    return {
        "matched": matched,
        "missing": missing,
        "extra": extra,
    }


def llm_explanation(jd, candidate, structured):
    name = candidate["name"]
    title = jd["title"]
    matched = structured["matched"]
    missing = structured["missing"]
    extra = structured["extra"]

    if matched:
        matched_text = (
            f"They match the following required skills: {', '.join(matched)}."
        )
    else:
        matched_text = "They matched no required skills."

    if missing:
        missing_text = f"They are missing the following skills: {', '.join(missing)}."
    else:
        missing_text = "They have all required skills."

    if extra:
        extra_text = (
            f" They also bring additional skills: {', '.join(extra)}."
        )
    else:
        extra_text = ""

    return f"{name} is a candidate for {title}. {matched_text} {missing_text}{extra_text}"
