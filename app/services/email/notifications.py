import logging
import os

from app.services.email.client import send_email
from app.services.email.layout import btn, frontend_url, wrap

logger = logging.getLogger(__name__)


def enviar_email_bienvenida(email: str, nombre: str):
    try:
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">¡Bienvenido/a a CelDoctor, {nombre}!</h2>
        <p style="color:#4B5563;line-height:1.7">
          Nos alegra que te hayas sumado a CelDoctor, la plataforma de telemedicina
          que te conecta con medicos y especialistas cuando mas lo necesitas,
          sin esperas y sin salir de casa.
        </p>
        <p style="color:#1F2937;font-weight:700;margin-bottom:8px">¿Que podes hacer con CelDoctor?</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0 24px">
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Videoconsultas 24/7</strong> — Medicos disponibles a toda hora, los 365 dias del año
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Recetas digitales</strong> — Recibi tus recetas directamente en tu celular
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Especialistas sin espera</strong> — Cardiologos, dermatologos, pediatras y mas
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
        send_email([email], f"¡Bienvenido/a a CelDoctor, {nombre}!", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email bienvenida a %s: %s", email, exc)


def enviar_email_recuperacion(email: str, nombre: str, token: str):
    try:
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recupera tu contraseña</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, recibimos una solicitud para resetear la
          contraseña de tu cuenta en CelDoctor.
        </p>
        <p style="text-align:center;margin:32px 0">
          {btn("Crear nueva contraseña", frontend_url(f"/nueva-contrasenia?token={token}"))}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          ⏱ Este link es valido por <strong>1 hora</strong>.
        </p>
        <p style="color:#9CA3AF;font-size:13px;margin-top:24px">
          Si no pediste esto, ignora este email. Tu contraseña no cambia.
        </p>
        """
        send_email([email], "Recupera tu contraseña de CelDoctor", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email recuperacion a %s: %s", email, exc)


def enviar_email_suscripcion_activa(
    email: str,
    nombre: str,
    plan_nombre: str,
    fecha_vencimiento: str,
    precio: float,
):
    try:
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">¡Tu suscripcion esta activa! ✓</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu suscripcion fue activada correctamente.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                      padding:20px;margin:24px 0">
          <tr><td style="padding:8px 0">
            <span style="color:#6B7280">Plan:</span>
            <strong style="color:#1F2937;margin-left:8px">{plan_nombre}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Vencimiento:</span>
            <strong style="color:#1F2937;margin-left:8px">{fecha_vencimiento}</strong>
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
          💡 Para usar el servicio, descarga la app <strong>Mediquo</strong> y
          accede con tus datos de CelDoctor.
        </p>
        """
        send_email([email], f"Tu plan {plan_nombre} esta activo ✓", wrap(body))
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
        urgente = dias_restantes <= 3
        alerta_html = ""
        if urgente:
            alerta_html = (
                '<p style="color:#DC2626;background:#FEF2F2;padding:12px 16px;'
                'border-radius:6px;border-left:3px solid #DC2626;font-weight:600;margin:16px 0">'
                "⚠️ ¡Atencion! Tu plan vence muy pronto. No pierdas acceso a tus consultas.</p>"
            )
        dias_txt = "dia" if dias_restantes == 1 else "dias"
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan vence en {dias_restantes} {dias_txt} ⚠️</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu plan <strong>{plan_nombre}</strong>
          vence el <strong>{fecha_vencimiento}</strong>.
        </p>
        {alerta_html}
        <p style="text-align:center;margin:32px 0">
          {btn("Renovar ahora", frontend_url("/planes"))}
        </p>
        <p style="color:#9CA3AF;font-size:13px">
          Si ya renovaste tu plan, ignora este email.
        </p>
        """
        send_email([email], f"Tu plan vence en {dias_restantes} {dias_txt} ⚠️", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email vencimiento proximo a %s: %s", email, exc)


def enviar_email_plan_vencido(email: str, nombre: str, plan_nombre: str):
    try:
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan CelDoctor vencio</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu plan <strong>{plan_nombre}</strong> expiro.
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
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recibimos tu ticket #{ticket_id} ✓</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, recibimos tu mensaje sobre:
          <strong>{asunto}</strong>.
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
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Respondimos tu ticket #{ticket_id}</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, respondimos tu ticket:
          <strong>{asunto}</strong>.
        </p>
        <div style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                    padding:20px;margin:24px 0">
          <p style="color:#6B7280;font-size:12px;margin:0 0 8px;
                    text-transform:uppercase;letter-spacing:0.5px">Respuesta</p>
          <p style="color:#1F2937;margin:0;line-height:1.7">{respuesta}</p>
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
        admin_email = os.getenv("ADMIN_EMAIL", "admin@celdoctor.com")
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Nuevo lead empresarial</h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                      padding:20px;margin:16px 0">
          <tr><td style="padding:8px 0">
            <span style="color:#6B7280">Contacto:</span>
            <strong style="margin-left:8px">{nombre_contacto}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Empresa:</span>
            <strong style="margin-left:8px">{empresa or "—"}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Email:</span>
            <strong style="margin-left:8px">{email_contacto}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Telefono:</span>
            <strong style="margin-left:8px">{telefono}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Empleados:</span>
            <strong style="margin-left:8px">{empleados if empleados is not None else "—"}</strong>
          </td></tr>
          <tr><td style="padding:8px 0;border-top:1px solid #E9D5FF">
            <span style="color:#6B7280">Mensaje:</span>
            <strong style="margin-left:8px">{mensaje or "—"}</strong>
          </td></tr>
        </table>
        """
        send_email([admin_email], f"Nuevo lead empresarial - {nombre_contacto}", wrap(body))
    except Exception as exc:
        logger.error("Error enviando email lead empresarial: %s", exc)
