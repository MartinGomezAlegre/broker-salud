from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Broker de Salud",
    description="Plataforma para contratar servicios de telemedicina",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mensaje": "Broker de Salud funcionando"
    }