import os
import queue
import sounddevice as sd
# vosk offline model imports
#import vosk
#import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# google cloud speech-to-text API imports
from google.cloud import speech 
from google.auth.transport.requests import Request

# ------------------ CONFIG ------------------
SCOPES = [
    "https://www.googleapis.com/auth/documents",   # Google Docs
    "https://www.googleapis.com/auth/cloud-platform"  # Speech-to-Text
]

DOCUMENT_ID = "1KFt7FI5EKQeFdzSU8K9lk5KYZSqMqMU-je9PgVhaU3U"   # <-- replace with your Google Doc ID
RATE = 16000                         # microphone sample rate

# ------------------ AUTH ------------------
def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# ------------------ GOOGLE DOCS SERVICE ------------------
def get_docs_service(creds):
    return build("docs", "v1", credentials=creds)

# ------------------ GOOGLE SPEECH CLIENT ------------------
def get_speech_client(creds):
    return speech.SpeechClient(credentials=creds)

# ------------------ APPEND TO DOC ------------------
def append_to_doc(service, doc_id, text):
    requests = [
    {
        "insertText": {
            "endOfSegmentLocation": {},   # instead of "location": {"index": 1}
            "text": text + "\n"
        }
    }
    ]
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print(f"✅ Added to Google Doc: {text}")

# ------------------ MICROPHONE STREAM ------------------
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, flush=True)
    q.put(bytes(indata))

# ------------------ MAIN TRANSCRIPTION ------------------
def listen_and_transcribe():
    creds = get_credentials()
    speech_client = get_speech_client(creds)
    docs_service = get_docs_service(creds)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    with sd.RawInputStream(
        samplerate=RATE, blocksize=8000, dtype="int16", channels=1, callback=callback
    ):
        print("🎙️ Listening... Speak into your mic (Ctrl+C to stop)")

        # Generator for audio stream
        def request_generator():
            while True:
                data = q.get()
                if data is None:
                    return
                yield speech.StreamingRecognizeRequest(audio_content=data)

        # Stream to Google Speech
        responses = speech_client.streaming_recognize(streaming_config, request_generator())

        try:
            for response in responses:
                for result in response.results:
                    if result.is_final:
                        text = result.alternatives[0].transcript.strip()
                        print("You said:", text)
                        append_to_doc(docs_service, DOCUMENT_ID, text)
        except KeyboardInterrupt:
            print("\n🛑 Stopped listening.")

# ------------------ RUN ------------------
if __name__ == "__main__":
    listen_and_transcribe()