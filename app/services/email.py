import os
import logging

logger = logging.getLogger(__name__)

FROM = "CelDoctor <noreply@celdoctor.com>"


def _get_resend():
    """Retorna el módulo resend configurado, o None si no hay API key."""
    import resend as _resend
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY no configurada — emails desactivados")
        return None
    _resend.api_key = api_key
    return _resend


def _btn(label: str, url: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:14px 28px;'
        f'background:#4C1D95;color:#fff;font-weight:600;text-decoration:none;'
        f'border-radius:8px;font-size:15px">{label}</a>'
    )


def _wrap(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F5F3FF;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F3FF;padding:32px 0">
<tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
    <tr><td style="background:#4C1D95;padding:24px 32px">
      <h1 style="margin:0;color:#fff;font-size:24px;font-weight:800;letter-spacing:2px">CELDOCTOR.</h1>
    </td></tr>
    <tr><td style="padding:32px">
      {body}
    </td></tr>
    <tr><td style="background:#F5F3FF;padding:20px 32px;text-align:center;border-top:1px solid #E9D5FF">
      <p style="margin:0;color:#6B7280;font-size:13px">
        © 2026 CelDoctor Argentina · Todos los derechos reservados
      </p>
    </td></tr>
  </table>
</td></tr>
</table>
</body></html>"""


# ── FEATURE: Bienvenida ────────────────────────────────────────────────────────

def enviar_email_bienvenida(email: str, nombre: str):
    try:
        resend = _get_resend()
        if not resend:
            return
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">¡Bienvenido/a a CelDoctor, {nombre}!</h2>
        <p style="color:#4B5563;line-height:1.7">
          Nos alegra que te hayas sumado a CelDoctor, la plataforma de telemedicina
          que te conecta con médicos y especialistas cuando más lo necesitás,
          sin esperas y sin salir de casa.
        </p>
        <p style="color:#1F2937;font-weight:700;margin-bottom:8px">¿Qué podés hacer con CelDoctor?</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0 24px">
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Videoconsultas 24/7</strong> — Médicos disponibles a toda hora, los 365 días del año
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Recetas digitales</strong> — Recibí tus recetas directamente en tu celular
            </td>
          </tr>
          <tr>
            <td style="width:28px;color:#4C1D95;font-size:18px;font-weight:700;vertical-align:top;padding-top:4px">✓</td>
            <td style="padding:8px 0;color:#374151;line-height:1.6">
              <strong>Especialistas sin espera</strong> — Cardiólogos, dermatólogos, pediatras y más
            </td>
          </tr>
        </table>
        <p style="text-align:center;margin:32px 0">
          {_btn("Elegir mi plan", "https://celdoctor.com/planes")}
        </p>
        <p style="color:#9CA3AF;font-size:13px;margin-top:32px">
          Si no creaste esta cuenta, podés ignorar este email.
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": f"¡Bienvenido/a a CelDoctor, {nombre}!",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email bienvenida a %s: %s", email, e)


# ── FEATURE: Recuperación de contraseña ───────────────────────────────────────

def enviar_email_recuperacion(email: str, nombre: str, token: str):
    try:
        resend = _get_resend()
        if not resend:
            return
        url = f"https://celdoctor.com/nueva-contrasenia?token={token}"
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recuperá tu contraseña</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, recibimos una solicitud para resetear la
          contraseña de tu cuenta en CelDoctor.
        </p>
        <p style="text-align:center;margin:32px 0">
          {_btn("Crear nueva contraseña", url)}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          ⏱ Este link es válido por <strong>1 hora</strong>.
        </p>
        <p style="color:#9CA3AF;font-size:13px;margin-top:24px">
          Si no pediste esto, ignorá este email. Tu contraseña no cambia.
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": "Recuperá tu contraseña de CelDoctor",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email recuperacion a %s: %s", email, e)


# ── FEATURE: Suscripción activa ───────────────────────────────────────────────

def enviar_email_suscripcion_activa(
    email: str, nombre: str, plan_nombre: str, fecha_vencimiento: str, precio: float
):
    try:
        resend = _get_resend()
        if not resend:
            return
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">¡Tu suscripción está activa! ✓</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu suscripción fue activada correctamente.
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
          {_btn("Ir a mi cuenta", "https://celdoctor.com/dashboard")}
        </p>
        <p style="color:#4B5563;font-size:14px;background:#FFF9E6;padding:12px 16px;
                  border-radius:6px;border-left:3px solid #F59E0B">
          💡 Para usar el servicio, descargá la app <strong>Mediquo</strong> y
          accedé con tus datos de CelDoctor.
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": f"Tu plan {plan_nombre} está activo ✓",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email suscripcion activa a %s: %s", email, e)


# ── FEATURE: Vencimiento próximo ──────────────────────────────────────────────

def enviar_email_vencimiento_proximo(
    email: str, nombre: str, plan_nombre: str, dias_restantes: int, fecha_vencimiento: str
):
    try:
        resend = _get_resend()
        if not resend:
            return
        urgente = dias_restantes <= 3
        alerta_html = ""
        if urgente:
            alerta_html = (
                '<p style="color:#DC2626;background:#FEF2F2;padding:12px 16px;'
                'border-radius:6px;border-left:3px solid #DC2626;font-weight:600;margin:16px 0">'
                "⚠️ ¡Atención! Tu plan vence muy pronto. No pierdas acceso a tus consultas.</p>"
            )
        dias_txt = "día" if dias_restantes == 1 else "días"
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan vence en {dias_restantes} {dias_txt} ⚠️</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu plan <strong>{plan_nombre}</strong>
          vence el <strong>{fecha_vencimiento}</strong>.
        </p>
        {alerta_html}
        <p style="text-align:center;margin:32px 0">
          {_btn("Renovar ahora", "https://celdoctor.com/planes")}
        </p>
        <p style="color:#9CA3AF;font-size:13px">
          Si ya renovaste tu plan, ignorá este email.
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": f"Tu plan vence en {dias_restantes} {dias_txt} ⚠️",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email vencimiento proximo a %s: %s", email, e)


# ── FEATURE: Plan vencido ─────────────────────────────────────────────────────

def enviar_email_plan_vencido(email: str, nombre: str, plan_nombre: str):
    try:
        resend = _get_resend()
        if not resend:
            return
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Tu plan CelDoctor venció</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, tu plan <strong>{plan_nombre}</strong> expiró.
        </p>
        <p style="color:#4B5563;line-height:1.7">
          Para seguir accediendo a videoconsultas, recetas digitales y especialistas,
          renovalo hoy.
        </p>
        <p style="text-align:center;margin:32px 0">
          {_btn("Reactivar mi plan", "https://celdoctor.com/planes")}
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": "Tu plan CelDoctor venció",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email plan vencido a %s: %s", email, e)


# ── FEATURE: Ticket recibido ──────────────────────────────────────────────────

def enviar_email_ticket_recibido(email: str, nombre: str, ticket_id: int, asunto: str):
    try:
        resend = _get_resend()
        if not resend:
            return
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Recibimos tu consulta #{ticket_id} ✓</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, recibimos tu mensaje sobre:
          <strong>{asunto}</strong>.
        </p>
        <p style="color:#4B5563;line-height:1.7">
          Nuestro equipo lo va a revisar y te va a responder en las próximas
          <strong>24 horas hábiles</strong>.
        </p>
        <p style="text-align:center;margin:32px 0">
          {_btn("Ver mi consulta", "https://celdoctor.com/dashboard")}
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": f"Recibimos tu consulta #{ticket_id}",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email ticket recibido a %s: %s", email, e)


# ── FEATURE: Ticket respondido ────────────────────────────────────────────────

def enviar_email_ticket_respondido(
    email: str, nombre: str, ticket_id: int, asunto: str, respuesta: str
):
    try:
        resend = _get_resend()
        if not resend:
            return
        body = f"""
        <h2 style="color:#1F2937;margin-top:0">Respondimos tu consulta #{ticket_id}</h2>
        <p style="color:#4B5563;line-height:1.7">
          Hola <strong>{nombre}</strong>, respondimos tu consulta:
          <strong>{asunto}</strong>.
        </p>
        <div style="background:#F5F3FF;border:1px solid #E9D5FF;border-radius:8px;
                    padding:20px;margin:24px 0">
          <p style="color:#6B7280;font-size:12px;margin:0 0 8px;
                    text-transform:uppercase;letter-spacing:0.5px">Respuesta</p>
          <p style="color:#1F2937;margin:0;line-height:1.7">{respuesta}</p>
        </div>
        <p style="text-align:center;margin:32px 0">
          {_btn("Ver respuesta completa", "https://celdoctor.com/dashboard")}
        </p>
        """
        resend.Emails.send({
            "from": FROM,
            "to": [email],
            "subject": f"Respondimos tu consulta #{ticket_id}",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email ticket respondido a %s: %s", email, e)


# ── FEATURE: Lead empresarial (email interno al admin) ────────────────────────

def enviar_email_lead_empresarial(
    nombre_contacto: str,
    empresa: str,
    email_contacto: str,
    telefono: str,
    empleados,
    mensaje: str,
):
    try:
        resend = _get_resend()
        if not resend:
            return
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
            <span style="color:#6B7280">Teléfono:</span>
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
        resend.Emails.send({
            "from": FROM,
            "to": [admin_email],
            "subject": f"Nuevo lead empresarial — {nombre_contacto}",
            "html": _wrap(body),
        })
    except Exception as e:
        logger.error("Error enviando email lead empresarial: %s", e)
