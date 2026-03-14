from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers import usuarios
from app.routers import planes
from app.routers import auth
from app.routers import suscripciones
from app.routers import admin
from fastapi.security import HTTPBearer

load_dotenv()

security = HTTPBearer()
app = FastAPI(
    title="Broker de Salud",
    description="Plataforma para contratar servicios de telemedicina",
    version="0.1.0",
    swagger_ui_parameters={"persistAuthorization": True}
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://celdoctor.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usuarios.router)
app.include_router(planes.router)
app.include_router(auth.router)
app.include_router(suscripciones.router)
app.include_router(admin.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mensaje": "Broker de Salud funcionando"
    }