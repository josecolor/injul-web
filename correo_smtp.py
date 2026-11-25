"""Mensajeria directa de INJUL por SMTP (sin n8n).

Variables de Railway: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_DEST.
Opcionales: SMTP_FROM (por defecto SMTP_USER), SITE_URL (por defecto https://injul.com.do).
"""
import html
import os
import re
import secrets
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

TELEFONO = "809-547-3178"
CORREO_INST = "injul01@gmail.com"
DIRECCION = "C/ Rafael Augusto Sánchez No. 125, Edif. Alexander, Suite 104, Evaristo Morales, D.N."
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _cfg(nombre, defecto=""):
    return (os.getenv(nombre, defecto) or "").strip()


def correo_valido(correo):
    return bool(EMAIL_RE.match(correo or "")) and len(correo) <= 254


def _limpio(texto, maximo):
    texto = re.sub(r"[\r\n\t]+", " ", texto or "")
    return texto.strip()[:maximo]


def _esc(texto):
    return html.escape(texto or "", quote=True)


def _esc_ml(texto):
    return _esc(texto).replace("\n", "<br>")


def _marco(titulo, contenido):
    sitio = _cfg("SITE_URL", "https://injul.com.do")
    sitio_corto = sitio.replace("https://", "").replace("http://", "")
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f4f7;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f7;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;">
<tr><td style="background:#0b2545;padding:24px 28px;">
<div style="color:#ffffff;font-size:24px;font-weight:bold;letter-spacing:2px;">INJUL</div>
<div style="color:#c9a227;font-size:11px;letter-spacing:2px;margin-top:4px;">INVESTIGADORES JURÍDICOS LEONOR</div>
</td></tr>
<tr><td style="padding:28px;">
<h2 style="margin:0 0 18px;font-size:20px;color:#0b2545;">{titulo}</h2>
{contenido}
</td></tr>
<tr><td style="background:#f8f9fb;padding:18px 28px;font-size:12px;line-height:1.7;color:#6b7280;border-top:3px solid #c9a227;">
<b style="color:#0b2545;">INJUL · Investigadores Jurídicos Leonor</b><br>
Tel. {TELEFONO} · <a href="mailto:{CORREO_INST}" style="color:#0b2545;">{CORREO_INST}</a><br>
{DIRECCION}<br>
<a href="{sitio}" style="color:#0b2545;">{sitio_corto}</a><br>
<i>Su información se maneja con estricta confidencialidad.</i>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def html_cliente(nombre, servicio, mensaje, ref):
    contenido = f"""
<p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Estimado(a) <b>{_esc(nombre)}</b>:</p>
<p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Hemos recibido su consulta sobre <b>{_esc(servicio)}</b>. Uno de nuestros especialistas la revisará y se comunicará con usted a la mayor brevedad.</p>
<p style="margin:0 0 18px;font-size:13px;color:#6b7280;">Referencia de su solicitud: <b style="color:#0b2545;">{_esc(ref)}</b></p>
<p style="margin:0 0 6px;font-size:13px;color:#6b7280;">Resumen de su mensaje:</p>
<div style="background:#f8f9fb;border-left:4px solid #c9a227;padding:12px 16px;font-size:14px;line-height:1.6;color:#374151;">{_esc_ml(mensaje)}</div>
<p style="margin:18px 0 0;font-size:14px;line-height:1.6;">Si su caso es urgente, llámenos al <b>{TELEFONO}</b>.</p>
"""
    return _marco("Hemos recibido su consulta", contenido)


def texto_cliente(nombre, servicio, mensaje, ref):
    return (
        f"Estimado(a) {nombre}:\n\n"
        f"Hemos recibido su consulta sobre {servicio}. Uno de nuestros especialistas "
        f"se comunicará con usted a la mayor brevedad.\n\n"
        f"Referencia: {ref}\n\nSu mensaje:\n{mensaje}\n\n"
        f"Si es urgente, llámenos al {TELEFONO}.\n\n"
        f"INJUL · Investigadores Jurídicos Leonor\n{DIRECCION}\n"
    )


def _fila(etiqueta, valor):
    return (
        '<tr><td style="padding:8px 12px;background:#f8f9fb;font-weight:bold;width:120px;'
        'border-bottom:1px solid #e5e7eb;font-size:14px;">' + etiqueta + '</td>'
        '<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:14px;">' + valor + '</td></tr>'
    )


def html_interno(nombre, correo, telefono, servicio, mensaje, ref, origen):
    filas = (
        _fila("Nombre", _esc(nombre))
        + _fila("Correo", f'<a href="mailto:{_esc(correo)}" style="color:#0b2545;">{_esc(correo)}</a>')
        + _fila("Teléfono", _esc(telefono) or "—")
        + _fila("Servicio", _esc(servicio))
        + _fila("Origen", _esc(origen))
        + _fila("Referencia", _esc(ref))
    )
    contenido = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:6px;margin-bottom:18px;">{filas}</table>
<p style="margin:0 0 6px;font-size:13px;color:#6b7280;">Mensaje:</p>
<div style="background:#f8f9fb;border-left:4px solid #c9a227;padding:12px 16px;font-size:14px;line-height:1.6;color:#374151;">{_esc_ml(mensaje)}</div>
<p style="margin:18px 0 0;font-size:13px;color:#6b7280;">Puede responder directamente a este correo: la respuesta va al cliente.</p>
"""
    return _marco("Nueva solicitud de contacto", contenido)


def texto_interno(nombre, correo, telefono, servicio, mensaje, ref, origen):
    return (
        f"Nueva solicitud de contacto (Ref. {ref})\n\n"
        f"Nombre: {nombre}\nCorreo: {correo}\nTeléfono: {telefono or '-'}\n"
        f"Servicio: {servicio}\nOrigen: {origen}\n\nMensaje:\n{mensaje}\n"
    )


def _enviar_resend(destino, asunto, cuerpo_html, cuerpo_texto, reply_to=None):
    import json
    import urllib.error
    import urllib.request

    remitente = _cfg("RESEND_FROM") or "INJUL <onboarding@resend.dev>"
    datos = {
        "from": remitente,
        "to": [destino],
        "subject": asunto,
        "html": cuerpo_html,
        "text": cuerpo_texto,
    }
    if reply_to:
        datos["reply_to"] = reply_to
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(datos).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + _cfg("RESEND_API_KEY"),
            "Content-Type": "application/json",
            "User-Agent": "injul-web/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, f"resend HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"Resend HTTP {e.code}: " + e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _enviar_smtp(destino, asunto, cuerpo_html, cuerpo_texto, reply_to=None):
    usuario = _cfg("SMTP_USER")
    clave = _cfg("SMTP_PASS")
    if not usuario or not clave:
        return False, "Faltan RESEND_API_KEY o SMTP_USER/SMTP_PASS en las variables de Railway"
    host = _cfg("SMTP_HOST", "smtp.gmail.com")
    try:
        puerto = int(_cfg("SMTP_PORT", "587") or 587)
    except ValueError:
        puerto = 587
    remitente = _cfg("SMTP_FROM") or usuario

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(asunto, "utf-8")
    msg["From"] = formataddr(("INJUL", remitente))
    msg["To"] = destino
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="injul.com.do")
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    try:
        contexto = ssl.create_default_context()
        if puerto == 465:
            with smtplib.SMTP_SSL(host, puerto, timeout=15, context=contexto) as s:
                s.login(usuario, clave)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, puerto, timeout=15) as s:
                s.starttls(context=contexto)
                s.login(usuario, clave)
                s.send_message(msg)
        return True, "enviado"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def enviar_correo(destino, asunto, cuerpo_html, cuerpo_texto, reply_to=None):
    """Devuelve (ok, detalle). Nunca lanza excepcion.
    Con RESEND_API_KEY usa la API HTTPS de Resend; si no, SMTP."""
    if _cfg("RESEND_API_KEY"):
        return _enviar_resend(destino, asunto, cuerpo_html, cuerpo_texto, reply_to)
    return _enviar_smtp(destino, asunto, cuerpo_html, cuerpo_texto, reply_to)


def procesar_contacto(nombre, correo, telefono="", servicio="", mensaje="", origen="Portal"):
    nombre = _limpio(nombre, 120)
    correo = _limpio(correo, 254)
    telefono = _limpio(telefono, 40)
    servicio = _limpio(servicio, 120) or "No especificado"
    mensaje = (mensaje or "").replace("\r", "").strip()[:5000]
    ref = secrets.token_hex(4).upper()

    destino = _cfg("NOTIFY_DEST", CORREO_INST)
    asunto_interno = f"Nueva Solicitud de Contacto — INJUL ({servicio})"
    ok_int, det_int = enviar_correo(
        destino, asunto_interno,
        html_interno(nombre, correo, telefono, servicio, mensaje, ref, origen),
        texto_interno(nombre, correo, telefono, servicio, mensaje, ref, origen),
        reply_to=correo,
    )

    ok_cli, det_cli = False, "no se envio: fallo la notificacion interna"
    if ok_int:
        ok_cli, det_cli = enviar_correo(
            correo, "Hemos recibido su consulta — INJUL",
            html_cliente(nombre, servicio, mensaje, ref),
            texto_cliente(nombre, servicio, mensaje, ref),
            reply_to=destino,
        )
        if not ok_cli:
            print("Aviso: no se envio la cartilla al cliente:", det_cli)

    return {"ref": ref, "interno": ok_int, "cliente": ok_cli,
            "detalle": {"interno": det_int, "cliente": det_cli}}
