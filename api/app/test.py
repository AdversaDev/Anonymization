import requests
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

url = "http://127.0.0.1:8000/upload"
file_path = "c:/Users/HopE/Desktop/Anonymisierungssystem/api/app/test.json",
file_path = "c:/Users/HopE/Desktop/Anonymisierungssystem/api/app/test.txt",
file_path = "c:/Users/HopE/Desktop/Anonymisierungssystem/api/app/test.xml"



with open(file_path, "rb") as file:
    files = {"file": (file_path, file)}
    response = requests.post(url, files=files)

print(response.json())
