from datetime import date
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field


class EmpresaCrear(BaseModel):
    razon_social: str
    cuit: str
    nombre_comercial: Optional[str] = None
    rubro: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    responsabilidad_iva: Optional[str] = None
    telefono: Optional[str] = Field(default=None, validation_alias=AliasChoices("telefono", "contacto_telefono"))
    email_contacto: str = Field(validation_alias=AliasChoices("email_contacto", "contacto_email"))
    contacto_nombre: str
    contacto_cargo: Optional[str] = None
    admin_access_email: Optional[str] = None
    admin_access_password: Optional[str] = None
    visible_para_gestores: bool = False


class EmpresaActualizar(BaseModel):
    razon_social: Optional[str] = None
    cuit: Optional[str] = None
    nombre_comercial: Optional[str] = None
    rubro: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    responsabilidad_iva: Optional[str] = None
    telefono: Optional[str] = Field(default=None, validation_alias=AliasChoices("telefono", "contacto_telefono"))
    email_contacto: Optional[str] = Field(default=None, validation_alias=AliasChoices("email_contacto", "contacto_email"))
    contacto_nombre: Optional[str] = None
    contacto_cargo: Optional[str] = None
    admin_access_email: Optional[str] = None
    admin_access_password: Optional[str] = None
    visible_para_gestores: Optional[bool] = None


class CambiarEstadoEmpresa(BaseModel):
    activo: bool
    motivo: Optional[str] = None


class SuscripcionEmpresarialCrear(BaseModel):
    plan_id: int
    cantidad_empleados: int
    precio_por_empleado: float
    periodicidad: str
    fecha_inicio: date


class CambiarEstadoSuscripcionEmpresarial(BaseModel):
    estado: str
    motivo: Optional[str] = None


class EmpleadoCrear(BaseModel):
    nombre: str
    apellido: str
    dni: str
    email: str
    cargo: Optional[str] = None
    telefono: Optional[str] = None


class EmpleadoActualizar(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    dni: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    telefono: Optional[str] = None


class CambiarEstadoEmpleado(BaseModel):
    activo: bool
    motivo: Optional[str] = None


class EmpresaAcuerdoCrear(BaseModel):
    tipo: str
    titulo: str
    descripcion: Optional[str] = None
    estado: Optional[str] = "vigente"
    fecha_firma: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    archivo_url: Optional[str] = None
    notas: Optional[str] = None


class EmpresaAcuerdoActualizar(BaseModel):
    tipo: Optional[str] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[str] = None
    fecha_firma: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    archivo_url: Optional[str] = None
    notas: Optional[str] = None


class BulkEmpleados(BaseModel):
    datos: Optional[str] = None
    empleados: Optional[List[EmpleadoCrear]] = None


ESTADOS_SUSCRIPCION_EMPRESA = {"activa", "pendiente_pago", "cancelada", "vencida"}
