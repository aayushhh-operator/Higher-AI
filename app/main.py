from fastapi import FastAPI
from app.data_loader import get_candidates, get_jd_by_id, get_jds
from app.services.scorer import final_score

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Higher AI is running"}


@app.get("/jds")
def list_jds():
    return get_jds()


@app.get("/match/{jd_id}")
def match(jd_id: str):
    jd = get_jd_by_id(jd_id)
    candidates = get_candidates()
    results = []
    for candidate in candidates:
        score = final_score(jd, candidate)
        results.append({"candidate_id": candidate["id"], "score": score})
    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results
