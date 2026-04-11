from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers import usuarios
from app.routers import planes
from app.routers import auth
from app.routers import suscripciones
from app.routers import admin
from app.routers import empresas
from app.routers import facturacion
from app.routers import catalogo
from app.routers import soporte
from app.routers import leads
from app.routers import beneficiarios
from app.routers import upsells
from app.routers import credenciales
from app.routers import comercial
from fastapi.security import HTTPBearer
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

load_dotenv()

security = HTTPBearer()
app = FastAPI(
    title="Broker de Salud",
    description="Plataforma para contratar servicios de telemedicina",
    version="0.1.0",
    swagger_ui_parameters={"persistAuthorization": True},
    redirect_slashes=False
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://celdoctor-waitlist.vercel.app",
        "https://celdoctor.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(usuarios.router)
app.include_router(planes.router)
app.include_router(auth.router)
app.include_router(suscripciones.router)
app.include_router(admin.router)
app.include_router(empresas.router)
app.include_router(facturacion.router)
app.include_router(catalogo.router)
app.include_router(catalogo.cupones_alias_router)
app.include_router(soporte.router)
app.include_router(soporte.admin_router)
app.include_router(leads.router)
app.include_router(leads.admin_router)
app.include_router(beneficiarios.router)
app.include_router(upsells.router)
app.include_router(upsells.admin_router)
app.include_router(credenciales.router)
app.include_router(credenciales.public_router)
app.include_router(comercial.admin_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mensaje": "Broker de Salud funcionando"
    }
