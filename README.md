# NavSphere

**Passenger Princess**

Conversational, LLM-based navigation tool with dynamic routing and a customized AI personality for driving support.

![alt text](image.png)

Enter a destination and click **Start Navigation**. The AI assistant provides turn-by-turn driving instructions with traffic-aware routing. While navigating, verbally ask the assistant for remaining duration, add stops, or change destination.

## Stack

| Layer | Technology |
|---|---|
| Map & Routing | Google Maps JavaScript API + Directions API |
| Destination Search | Google Places Autocomplete |
| Backend API | FastAPI (Python) |
| LLM Assistant | GPT-4o-mini via OpenRouter |
| Voice Input | Browser SpeechRecognition (Chrome) |
| Voice Output | Browser SpeechSynthesis |

## Environment Variables

**`backend/.env`**
```
OPENAI_API_KEY=your_openrouter_key
GMAPS_API_KEY=your_google_maps_key
```

**`frontend/my-app/.env`**
```
REACT_APP_GOOGLE_KEY=your_google_maps_key
```

Google API key requires: Maps JavaScript API, Directions API, Places API, Geocoding API enabled.

## Backend setup (from root)

Package manager: `uv` — install with `pip install uv`  
Python version: 3.11.11

```bash
cd backend

uv venv --python 3.11.11

# Mac
source .venv/bin/activate
# Windows
.venv\Scripts\activate

uv pip install -r requirements.txt

uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

## Frontend setup (from root)

```bash
cd frontend/my-app
npm install
npm start
```

Open `http://localhost:3000` in Chrome (required for SpeechRecognition).
