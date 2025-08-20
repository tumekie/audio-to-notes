import os
import queue
import sounddevice as sd
import vosk
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# -------- Google Docs Setup --------
SCOPES = ["https://www.googleapis.com/auth/documents"]

def get_docs_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret_audio_to_notes.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("docs", "v1", credentials=creds)

def append_to_doc(service, doc_id, text):
    """Append transcribed text to the end of Google Doc."""
    if not text.strip():
        return

    # Get current doc length
    doc = service.documents().get(documentId=doc_id).execute()
    end_index = doc.get("body").get("content")[-1]["endIndex"]

    requests = [
        {
            "insertText": {
                "location": {"index": end_index - 1},  # append at end
                "text": text + "\n"
            }
        }
    ]
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


# -------- Vosk Speech Recognition Setup --------
MODEL_PATH = "models/vosk-model-en-us-0.22"  # make sure you extracted this model folder
if not os.path.exists(MODEL_PATH):
    print("Please download and unpack the model from https://alphacephei.com/vosk/models")
    exit(1)

model = vosk.Model(MODEL_PATH)
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, flush=True)
    q.put(bytes(indata))

def transcribe_and_write(service, doc_id):
    rec = vosk.KaldiRecognizer(model, 16000)
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                           channels=1, callback=callback):
        print("🎙️ Listening... Press Ctrl+C to stop.")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    print("You said:", text)
                    append_to_doc(service, doc_id, text)


# -------- Main --------
def main():
    DOCUMENT_ID = "1KFt7FI5EKQeFdzSU8K9lk5KYZSqMqMU-je9PgVhaU3U"  # replace with your Google Doc ID
    service = get_docs_service()
    transcribe_and_write(service, DOCUMENT_ID)

if __name__ == "__main__":
    main()
