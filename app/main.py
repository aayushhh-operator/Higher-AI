from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.data_loader import get_candidates, get_jd_by_id, get_jds
from app.services.explanation import llm_explanation, structured_explanation
from app.services.scorer import final_score

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        structured = structured_explanation(jd, candidate)
        llm_text = llm_explanation(jd, candidate, structured)
        results.append(
            {
                "candidate_id": candidate["id"],
                "score": score,
                "explanation": {
                    "structured": structured,
                    "llm": llm_text,
                },
            }
        )
    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results
