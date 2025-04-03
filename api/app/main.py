from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.routes import router

app = FastAPI(
    title="Anonymization API",
    description="API umożliwiające anonimizację oraz deanonimizację danych poprzez upload plików",
    version="1.0.0"
)

# Dołączenie routera zawierającego endpointy /upload oraz /upload-deanonymize
app.include_router(router)

@app.get("/", response_class=HTMLResponse)
async def home():
    html_content = """
    <html>
      <head>
        <title>Anonymization Service</title>
      </head>
      <body>
        <h1>Anonymization Service</h1>
        <h2>Upload file for Anonymization</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
          <input type="file" name="file" required>
          <button type="submit">Anonymize</button>
        </form>
        <h2>Upload file for Deanonymization</h2>
        <form action="/upload-deanonymize" method="post" enctype="multipart/form-data">
          <input type="file" name="file" required>
          <button type="submit">Deanonymize</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
