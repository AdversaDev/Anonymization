from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.routes import router

app = FastAPI(
    title="Anonymisierungs-API",
    description="API für die Anonymisierung und Deanonymisierung von Daten durch Datei-Upload",
    version="1.0.0"
)

# Router mit den Endpunkten /upload und /upload-deanonymize einbinden
app.include_router(router)

@app.get("/", response_class=HTMLResponse)
async def home():
    html_content = """
    <html>
      <head>
        <title>Anonymisierungsdienst</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
          h1 { color: #2c3e50; }
          h2 { color: #3498db; margin-top: 20px; }
          form { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
          input, button { padding: 8px; margin: 5px 0; }
          button { background-color: #3498db; color: white; border: none; cursor: pointer; border-radius: 3px; }
          button:hover { background-color: #2980b9; }
          .info { background-color: #e8f4f8; padding: 10px; border-radius: 5px; margin-top: 20px; }
          .note { color: #e74c3c; }
          .success { color: #27ae60; }
          .hidden { display: none; }
          .result-container { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f8f9fa; }
          .loader { border: 5px solid #f3f3f3; border-top: 5px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; margin: 20px auto; display: none; }
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
          .action-buttons { margin-top: 10px; }
          .action-buttons button { margin-right: 10px; }
          .file-input-wrapper { display: flex; align-items: center; margin-bottom: 10px; }
          .file-input-button { background-color: #3498db; color: white; border: none; cursor: pointer; border-radius: 3px; padding: 8px; margin-right: 10px; }
          .file-input-button:hover { background-color: #2980b9; }
        </style>
      </head>
      <body>
        <h1>Anonymisierungsdienst</h1>
        
        <div class="info">
          <h3>Dateiwarteschlangensystem</h3>
          <p>Das System verarbeitet Dateien in einer Warteschlange. Jede Datei wird einzeln verarbeitet, unabhängig von ihrer Größe.</p>
          <p>Nach dem Hochladen einer Datei erhalten Sie eine Aufgaben-ID, mit der Sie den Verarbeitungsstatus überprüfen und die Ergebnisse herunterladen können.</p>
        </div>
        <h2>Datei für Anonymisierung hochladen</h2>
        <form id="upload-form" action="/upload" method="post" enctype="multipart/form-data">
          <div class="file-input-wrapper">
            <input type="file" name="file" id="file-upload" required style="display: none;">
            <button type="button" class="file-input-button" onclick="document.getElementById('file-upload').click()">Datei auswählen</button>
            <span id="file-upload-name">Keine Datei ausgewählt</span>
          </div>
          <button type="submit">Datei hochladen</button>
          <p class="note">Nach dem Hochladen der Datei erhalten Sie eine Aufgaben-ID anstelle eines direkten Downloads.</p>
        </form>
        <div id="file-result" class="result-container hidden">
          <h3>Datei wurde hochgeladen</h3>
          <p><strong>Datei-ID:</strong> <span id="file-id-result"></span></p>
          <p>Verwenden Sie diese ID, um den Status zu überprüfen und die Datei herunterzuladen, sobald sie verarbeitet wurde.</p>
          <div class="action-buttons">
            <button onclick="checkStatus()">Status prüfen</button>
            <button onclick="copyToClipboard('file-id-result')">ID kopieren</button>
          </div>
        </div>
        <div id="file-loader" class="loader"></div>
        
        <h2>Datei für Deanonymisierung hochladen</h2>
        <form id="deanonymize-form" action="/upload-deanonymize" method="post" enctype="multipart/form-data">
          <div class="file-input-wrapper">
            <input type="file" name="file" id="file-deanonymize-upload" required style="display: none;">
            <button type="button" class="file-input-button" onclick="document.getElementById('file-deanonymize-upload').click()">Datei auswählen</button>
            <span id="file-deanonymize-upload-name">Keine Datei ausgewählt</span>
          </div>
          <button type="submit">Datei hochladen</button>
        </form>
        <div id="file-deanonymize-loader" class="loader"></div>
        
        <h2>Verarbeitungsstatus prüfen</h2>
        <form id="status-form" onsubmit="event.preventDefault(); checkStatus();">
          <input type="text" id="status-file-id" placeholder="Datei-ID eingeben" required>
          <button type="submit">Status prüfen</button>
        </form>
        <div id="status-result" class="result-container hidden"></div>
        <div id="status-loader" class="loader"></div>
        
        <script>
          // Inicjalizacja formularzy
          document.addEventListener('DOMContentLoaded', function() {
            // Formularz anonimizacji
            const uploadForm = document.getElementById('upload-form');
            if (uploadForm) {
              uploadForm.addEventListener('submit', function(event) {
                // Formularz będzie wysyłany normalnie przez przeglądarkę
                // Nie musimy nic robić, ponieważ używamy standardowego przesyłania formularza
              });
            }
            
            // Formularz deanonimizacji
            const deanonymizeForm = document.getElementById('deanonymize-form');
            if (deanonymizeForm) {
              deanonymizeForm.addEventListener('submit', function(event) {
                // Formularz będzie wysyłany normalnie przez przeglądarkę
                // Nie musimy nic robić, ponieważ używamy standardowego przesyłania formularza
              });
            }
            
            // Obsługa wyświetlania nazwy wybranego pliku dla formularza anonimizacji
            const fileUpload = document.getElementById('file-upload');
            const fileUploadName = document.getElementById('file-upload-name');
            if (fileUpload && fileUploadName) {
              fileUpload.addEventListener('change', function() {
                if (fileUpload.files.length > 0) {
                  fileUploadName.textContent = fileUpload.files[0].name;
                } else {
                  fileUploadName.textContent = 'Keine Datei ausgewählt';
                }
              });
            }
            
            // Obsługa wyświetlania nazwy wybranego pliku dla formularza deanonimizacji
            const fileDeanonymizeUpload = document.getElementById('file-deanonymize-upload');
            const fileDeanonymizeUploadName = document.getElementById('file-deanonymize-upload-name');
            if (fileDeanonymizeUpload && fileDeanonymizeUploadName) {
              fileDeanonymizeUpload.addEventListener('change', function() {
                if (fileDeanonymizeUpload.files.length > 0) {
                  fileDeanonymizeUploadName.textContent = fileDeanonymizeUpload.files[0].name;
                } else {
                  fileDeanonymizeUploadName.textContent = 'Keine Datei ausgewählt';
                }
              });
            }
          });
          
          // Status prüfen
          async function checkStatus() {
            const fileId = document.getElementById('status-file-id').value.trim();
            if (!fileId) {
              alert('Bitte geben Sie eine Datei-ID ein');
              return;
            }
            
            document.getElementById('status-loader').style.display = 'block';
            document.getElementById('status-result').classList.add('hidden');
            
            try {
              const response = await fetch(`/status/${fileId}`);
              const data = await response.json();
              
              const statusResult = document.getElementById('status-result');
              
              if (response.ok) {
                let statusHtml = `<h3>Status: ${getStatusTranslation(data.status)}</h3>`;
                
                if (data.status === 'queued') {
                  statusHtml += `<p>Position in der Warteschlange: ${data.position}</p>`;
                  statusHtml += `<p>Geschätzte Wartezeit: ${Math.round(data.estimated_wait_time)} Sekunden</p>`;
                } else if (data.status === 'processing') {
                  statusHtml += `<p>Verarbeitungszeit: ${data.processing_time}</p>`;
                } else if (data.status === 'completed') {
                  statusHtml += `<p class="success">Datei ist bereit zum Herunterladen</p>`;
                  statusHtml += `<p><a href="${data.download_url}" class="download-button" download>Datei herunterladen</a></p>`;
                }
                
                statusResult.innerHTML = statusHtml;
                statusResult.classList.remove('hidden');
              } else {
                statusResult.innerHTML = `<p>Fehler: ${data.detail || 'Unbekannter Fehler'}</p>`;
                statusResult.classList.remove('hidden');
              }
            } catch (error) {
              console.error('Fehler beim Prüfen des Status:', error);
              document.getElementById('status-result').innerHTML = `<p>Fehler beim Prüfen des Status: ${error.message}</p>`;
              document.getElementById('status-result').classList.remove('hidden');
            } finally {
              document.getElementById('status-loader').style.display = 'none';
            }
          }
          
          // In die Zwischenablage kopieren
          function copyToClipboard(elementId) {
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {
              alert('In die Zwischenablage kopiert!');
            }).catch(err => {
              console.error('Fehler beim Kopieren:', err);
              alert('Fehler beim Kopieren in die Zwischenablage');
            });
          }
          
          // Status-Übersetzung
          function getStatusTranslation(status) {
            const translations = {
              'queued': 'In Warteschlange',
              'processing': 'Wird verarbeitet',
              'completed': 'Abgeschlossen',
              'error': 'Fehler'
            };
            return translations[status] || status;
          }
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
