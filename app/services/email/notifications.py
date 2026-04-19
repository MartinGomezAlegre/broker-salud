import html
import logging
import os

from app.services.email.client import send_email
from app.services.email.layout import btn, frontend_url, wrap

logger = logging.getLogger(__name__)


def _escape(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def enviar_email_bienvenida(email: str, nombre: str):
    try:
        nombre_safe = _escape(nombre)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Bienvenido/a a CelDoctor, {nombre_safe}!</h2>
        <p style="color:#4B5563;line-height:1.7">
          Nos alegra que te hayas sumado a CelDoctor, la plataforma de telemedicina
          que te conecta con medicos y especialistas cuando mas lo necesitas,
          sin esperas y sin salir de casa.
        </p>
        <p style="color:#1F2937;font-weight:700;margin-bottom:8px">Que podes hacer con CelDoctor?</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0 24px">
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">-</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Videoconsultas 24/7</strong> - Medicos disponibles a toda hora, los 365 dias del ano
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">-</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Recetas digitales</strong> - Recibi tus recetas directamente en tu celular
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">-</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Especialistas sin espera</strong> - Cardiologos, dermatologos, pediatras y mas
            </td>
          </tr>
        </table>
        <p style="text-align:center;margin:32px 0">
          {btn("Elegir mi plan", frontend_url("/planes"))}
        </p>
        <p style="color:#9CA3AF;font-size:13px;margin-top:32px">
          Si no creaste esta cuenta, podes ignorar este email.
        </p>
        """
        send_email([email], f"Bienvenido/a a CelDoctor, {nombre_safe}!", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email bienvenida a %s: %s", email, exc)


def enviar_email_recuperacion(email: str, nombre: str, token: str):
    try:
        nombre_safe = _escape(nombre)
        token_safe = _escape(token)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recupera tu contrasena</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, recibimos una solicitud para resetear la
          contrasena de tu cuenta en CelDoctor.
        </p>
        <p style="text-align:center;margin:32px 0">
          {btn("Crear nueva contrasena", frontend_url(f"/nueva-contrasenia?token={token_safe}"))}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          Este link es valido por <strong>1 hora</strong>.
        </p>
        <p style="color:#9CA3AF;font-size:13px;margin-top:24px">
          Si no pediste esto, ignora este email. Tu contrasena no cambia.
        </p>
        """
        send_email([email], "Recupera tu contrasena de CelDoctor", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email recuperacion a %s: %s", email, exc)


def enviar_email_invitacion_cuenta(email: str, nombre: str, token: str, role: str):
    try:
        nombre_safe = _escape(nombre)
        token_safe = _escape(token)
        role_safe = _escape(role.replace("_", " "))
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu acceso a CelDoctor ya esta listo</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, te enviamos este link para activar tu cuenta
          de <strong>{role_safe}</strong> en CelDoctor.
        </p>
        <p style="color:#4B5563;line-height:1.7">
          Vas a poder definir tu propia contrasena y entrar directamente al panel que te corresponde.
        </p>
        <p style="text-align:center;margin:32px 0">
          {btn("Activar cuenta", frontend_url(f"/activar-cuenta?token={token_safe}"))}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          Este link vence en <strong>72 horas</strong>. Si ya activaste tu cuenta, podes ignorar este email.
        </p>
        """
        send_email([email], "Activa tu cuenta de CelDoctor", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email invitacion a %s: %s", email, exc)


def enviar_email_suscripcion_activa(
    email: str,
    nombre: str,
    plan_nombre: str,
    fecha_vencimiento: str,
    precio: float,
):
    try:
        nombre_safe = _escape(nombre)
        plan_nombre_safe = _escape(plan_nombre)
        fecha_vencimiento_safe = _escape(fecha_vencimiento)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu suscripcion esta activa</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, tu suscripcion fue activada correctamente.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                      padding:20px;margin:24px 0">
          <tr><td style="padding:8px 0">
            <span style="color:#6B7280">Plan:</span>
            <strong style="color:#1F2937;margin-left:8px">{plan_nombre_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Vencimiento:</span>
            <strong style="color:#1F2937;margin-left:8px">{fecha_vencimiento_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Precio:</span>
            <strong style="color:#1F2937;margin-left:8px">${precio:.2f} / mes</strong>
          </td></tr>
        </table>
        <p style="text-align:center;margin:32px 0">
          {btn("Ir a mi cuenta", frontend_url("/dashboard"))}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          Para usar el servicio, descarga la app <strong>Mediquo</strong> y
          accede con tus datos de CelDoctor.
        </p>
        """
        send_email([email], f"Tu plan {plan_nombre_safe} esta activo", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email suscripcion activa a %s: %s", email, exc)


def enviar_email_vencimiento_proximo(
    email: str,
    nombre: str,
    plan_nombre: str,
    dias_restantes: int,
    fecha_vencimiento: str,
):
    try:
        nombre_safe = _escape(nombre)
        plan_nombre_safe = _escape(plan_nombre)
        fecha_vencimiento_safe = _escape(fecha_vencimiento)
        urgente = dias_restantes <= 3
        alerta_html = ""
        if urgente:
            alerta_html = (
                '<p style="color:#DC2626;background:#FEF2F2;padding:12px 16px;'
                'border-radius:6px;border-left:3px solid #DC2626;font-weight:600;margin:16px 0">'
                "Atencion: tu plan vence muy pronto. No pierdas acceso a tus consultas.</p>"
            )
        dias_txt = "dia" if dias_restantes == 1 else "dias"
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan vence en {dias_restantes} {dias_txt}</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, tu plan <strong>{plan_nombre_safe}</strong>
          vence el <strong>{fecha_vencimiento_safe}</strong>.
        </p>
        {alerta_html}
        <p style="text-align:center;margin:32px 0">
          {btn("Renovar ahora", frontend_url("/planes"))}
        </p>
        <p style="color:#9CA3AF;font-size:13px">
          Si ya renovaste tu plan, ignora este email.
        </p>
        """
        send_email([email], f"Tu plan vence en {dias_restantes} {dias_txt}", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email vencimiento proximo a %s: %s", email, exc)


def enviar_email_plan_vencido(email: str, nombre: str, plan_nombre: str):
    try:
        nombre_safe = _escape(nombre)
        plan_nombre_safe = _escape(plan_nombre)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan CelDoctor vencio</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, tu plan <strong>{plan_nombre_safe}</strong> expiro.
        </p>
        <p style="color:#4B5563;line-height:1.7">
          Para seguir accediendo a videoconsultas, recetas digitales y especialistas,
          renovalo hoy.
        </p>
        <p style="text-align:center;margin:32px 0">
          {btn("Reactivar mi plan", frontend_url("/planes"))}
        </p>
        """
        send_email([email], "Tu plan CelDoctor vencio", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email plan vencido a %s: %s", email, exc)


def enviar_email_ticket_recibido(email: str, nombre: str, ticket_id: int, asunto: str):
    try:
        nombre_safe = _escape(nombre)
        asunto_safe = _escape(asunto)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recibimos tu ticket #{ticket_id}</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, recibimos tu mensaje sobre:
          <strong>{asunto_safe}</strong>.
        </p>
        <p style="color:#4B5563;line-height:1.7">
          Nuestro equipo lo va a revisar y te va a responder en las proximas
          <strong>24 horas habiles</strong>.
        </p>
        <p style="text-align:center;margin:32px 0">
          {btn("Ver mi ticket", frontend_url("/dashboard"))}
        </p>
        """
        send_email([email], f"Recibimos tu ticket #{ticket_id}", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email ticket recibido a %s: %s", email, exc)


def enviar_email_ticket_respondido(
    email: str,
    nombre: str,
    ticket_id: int,
    asunto: str,
    respuesta: str,
):
    try:
        nombre_safe = _escape(nombre)
        asunto_safe = _escape(asunto)
        respuesta_safe = _escape(respuesta)
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Respondimos tu ticket #{ticket_id}</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre_safe}</strong>, respondimos tu ticket:
          <strong>{asunto_safe}</strong>.
        </p>
        <div style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                    padding:20px;margin:24px 0">
          <p style="color:#6B7280;font-size:12px;margin:0 0 8px;
                    text-transform:uppercase;letter-spacing:0.5px">Respuesta</p>
          <p style="color:#1F2937;margin:0;line-height:1.7">{respuesta_safe}</p>
        </div>
        <p style="text-align:center;margin:32px 0">
          {btn("Ver respuesta completa", frontend_url("/dashboard"))}
        </p>
        """
        send_email([email], f"Respondimos tu ticket #{ticket_id}", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email ticket respondido a %s: %s", email, exc)


def enviar_email_lead_empresarial(
    nombre_contacto: str,
    empresa: str,
    email_contacto: str,
    telefono: str,
    empleados,
    mensaje: str,
):
    try:
        nombre_contacto_safe = _escape(nombre_contacto)
        empresa_safe = _escape(empresa or "-")
        email_contacto_safe = _escape(email_contacto)
        telefono_safe = _escape(telefono)
        empleados_safe = _escape(empleados if empleados is not None else "-")
        mensaje_safe = _escape(mensaje or "-")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@celdoctor.com")
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Nuevo lead empresarial</h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                      padding:20px;margin:16px 0">
          <tr><td style="padding:8px 0">
            <span style="color:#6B7280">Contacto:</span>
            <strong style="margin-left:8px">{nombre_contacto_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Empresa:</span>
            <strong style="margin-left:8px">{empresa_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Email:</span>
            <strong style="margin-left:8px">{email_contacto_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Telefono:</span>
            <strong style="margin-left:8px">{telefono_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Empleados:</span>
            <strong style="margin-left:8px">{empleados_safe}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Mensaje:</span>
            <strong style="margin-left:8px">{mensaje_safe}</strong>
          </td></tr>
        </table>
        """
        send_email([admin_email], f"Nuevo lead empresarial - {nombre_contacto_safe}", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email lead empresarial: %s", exc)
