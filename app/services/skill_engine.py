SKILL_MAP = {
    "FastAPI": ["Backend", "Python"],
    "Docker": ["DevOps", "Containerization"],
    "Python": ["Backend", "Scripting"],
    "React": ["Frontend", "JavaScript"],
    "PostgreSQL": ["SQL", "Database"],
}


def expand(skills):
    expanded = set(skills)
    for skill in skills:
        expanded.update(SKILL_MAP.get(skill, []))
    return expanded
