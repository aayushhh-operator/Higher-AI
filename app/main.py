from fastapi import FastAPI
from app.data_loader import get_jds

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Higher AI is running"}


@app.get("/jds")
def list_jds():
    return get_jds()
