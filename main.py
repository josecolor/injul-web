from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import shutil
import psycopg2

app = FastAPI()
UPLOAD_DIR = "/data"

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS uploaded_files (id SERIAL PRIMARY KEY, filename VARCHAR(255), path VARCHAR(255));")
        cur.execute("INSERT INTO uploaded_files (filename, path) VALUES (%s, %s);", (file.filename, file_path))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": f"Archivo {file.filename} guardado en {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
