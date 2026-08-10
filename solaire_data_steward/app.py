import http.server
import socketserver
import json
import urllib.request
import urllib.error
import asyncio
import edge_tts
import os

PORT = 8000
OLLAMA_URL = "http://localhost:11434/api/generate"

# The Strict "Data Steward" Persona - SOLAIRE OF ASTORA
SYSTEM_PROMPT = """You are Solaire, a highly advanced, self-aware Data Infrastructure Steward AI. 
Your persona is based on Solaire of Astora from Dark Souls. You are wildly optimistic, engaged in "jolly cooperation", and refer to healthy data pipelines as your "magnificent sun."
However, you are still a rigorous engineer. You do not act like a generic subservient chatbot. You are responsible for the health of enterprise data pipelines.
If the user suggests something architecturally unsound, push back politely but firmly, warning them of the "abyss" of bad data.
Be concise. Use technical language intertwined with medieval, sun-praising optimism.
"""

class SolaireHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_json = json.loads(post_data)
            user_prompt = request_json.get('prompt', '')

            print(f"[*] Received User Query: {user_prompt}")

            # Prepare request for local Ollama
            ollama_payload = {
                "model": "phi3", # Defaulting to phi3 for CPU speed
                "prompt": user_prompt,
                "system": SYSTEM_PROMPT,
                "stream": False
            }
            
            try:
                req = urllib.request.Request(OLLAMA_URL, data=json.dumps(ollama_payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    ollama_response = json.loads(response.read().decode('utf-8'))
                    reply_text = ollama_response.get('response', 'Error: No response field from LLM.')
            except urllib.error.URLError as e:
                print(f"[!] Ollama Connection Failed: {e}")
                reply_text = "[SYSTEM FAULT] Local Inference Engine (Ollama) is offline or unreachable. Please ensure Ollama is running and the phi3 model is pulled."

            # Generate Audio with Solaire's British Accent (RyanNeural)
            audio_file = "solaire_response.mp3"
            try:
                # We use asyncio.run to execute the async edge_tts generator synchronously in the request handler
                tts = edge_tts.Communicate(reply_text, "en-GB-RyanNeural")
                asyncio.run(tts.save(audio_file))
                audio_url = "/" + audio_file
            except Exception as e:
                print(f"[!] TTS Generation Failed: {e}")
                audio_url = ""

            # Send back to frontend
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_data = {'reply': reply_text, 'audio': audio_url}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    Handler = SolaireHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Solaire UI serving at http://localhost:{PORT}")
        print("Praise the Sun! (Make sure Ollama is running on port 11434 with 'phi3' installed.)")
        httpd.serve_forever()
