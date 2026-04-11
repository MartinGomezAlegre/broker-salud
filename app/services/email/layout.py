import os


def frontend_url(path: str) -> str:
    base_url = os.getenv("FRONTEND_URL", "https://celdoctor.com").rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{clean_path}"


def btn(label: str, url: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:14px 28px;'
        f'background:#4C1D95;color:#fff;font-weight:600;text-decoration:none;'
        f'border-radius:8px;font-size:15px">{label}</a>'
    )


def wrap(body: str) -> str:
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
