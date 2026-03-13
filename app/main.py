from fastapi import FastAPI
from dotenv import load_dotenv
from app.routers import usuarios
from app.routers import planes
from app.routers import auth

load_dotenv()

app = FastAPI(
    title="Broker de Salud",
    description="Plataforma para contratar servicios de telemedicina",
    version="0.1.0"
)

app.include_router(usuarios.router)
app.include_router(planes.router)
app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mensaje": "Broker de Salud funcionando"
    }