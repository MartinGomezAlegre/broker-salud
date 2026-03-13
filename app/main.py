from fastapi import FastAPI
from dotenv import load_dotenv
from app.routers import usuarios  # ← línea nueva
from app.routers import planes

load_dotenv()

app = FastAPI(
    title="Broker de Salud",
    description="Plataforma para contratar servicios de telemedicina",
    version="0.1.0"
)

app.include_router(usuarios.router)  # ← línea nueva
app.include_router(planes.router)  # ← línea nueva


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mensaje": "Broker de Salud funcionando"
    }





