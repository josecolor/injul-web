import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
import smtplib
import ssl
from email.mime.text import MIMEText
import psycopg2

app = FastAPI()
UPLOAD_DIR = "/data"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# Configuración SMTP — leída de variables de entorno de Railway
SMTP_HOST = os.getenv("SMTP_HOST", "mail.injul.com.do")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "contacto@injul.com.do")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_DEST = os.getenv("SMTP_DEST", "contacto@injul.com.do")

# Sirve wp-content e imagenesweb como archivos estáticos
if os.path.isdir(os.path.join(SITE_DIR, "wp-content")):
    app.mount("/wp-content", StaticFiles(directory=os.path.join(SITE_DIR, "wp-content")), name="wp-content")
if os.path.isdir(os.path.join(SITE_DIR, "imagenesweb")):
    app.mount("/imagenesweb", StaticFiles(directory=os.path.join(SITE_DIR, "imagenesweb")), name="imagenesweb")


def serve_page(filename: str):
    file_path = os.path.join(SITE_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    raise HTTPException(status_code=404, detail=f"{filename} no encontrado")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return serve_page("index.html")


@app.get("/nosotros.html", response_class=HTMLResponse)
async def serve_nosotros():
    return serve_page("nosotros.html")


@app.get("/noticias.html", response_class=HTMLResponse)
async def serve_noticias():
    return serve_page("noticias.html")


@app.get("/perfiles.html", response_class=HTMLResponse)
async def serve_perfiles():
    return serve_page("perfiles.html")


@app.get("/admin.html", response_class=HTMLResponse)
async def serve_admin():
    return serve_page("admin.html")


# Equivalente Python de enviar.php — formulario de contacto por SMTP
@app.post("/enviar.php")
async def enviar_contacto(
    nombre: str = Form(""),
    telefono: str = Form(""),
    correo: str = Form(""),
    servicio: str = Form(""),
    mensaje: str = Form(""),
):
    nombre = nombre.strip()
    telefono = telefono.strip()
    correo = correo.strip()
    servicio = servicio.strip()
    mensaje = mensaje.strip()

    if not nombre or not correo or not mensaje:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "msg": "Complete los campos obligatorios."},
        )

    asunto = f"Consulta web: {servicio} - {nombre}"
    html = f"""<h3>Nueva consulta desde la web</h3>
    <p><b>Nombre:</b> {nombre} <br>
    <b>Correo:</b> {correo} <br>
    <b>Teléfono:</b> {telefono} <br>
    <b>Servicio:</b> {servicio} </p>
    <p><b>Mensaje:</b><br>{mensaje}</p>"""

    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = f"INJUL Web <{SMTP_USER}>"
        msg["To"] = SMTP_DEST

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=10) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [SMTP_DEST], msg.as_string())

        return JSONResponse(content={"ok": True, "msg": "¡Mensaje enviado con éxito!"})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "msg": f"Fallo: {str(e)}"},
        )


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS uploaded_files (id SERIAL PRIMARY KEY, filename TEXT, path TEXT);")
        cur.execute("INSERT INTO uploaded_files (filename, path) VALUES (%s, %s)", (file.filename, file_path))
        conn.commit()
        cur.close()
        conn.close()

        return {"status": "success", "message": f"Archivo {file.filename} guardado en {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
