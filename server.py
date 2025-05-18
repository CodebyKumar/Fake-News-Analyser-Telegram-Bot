from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import tempfile
import os
import requests
from dotenv import load_dotenv

# Import functions from analyse.py
from analyse import analyze_news, create_news_input, extract_json_from_response

# Load environment variables
load_dotenv()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# Initialize FastAPI app
app = FastAPI(
    title="Fake News Detection API",
    description="API for analyzing news content to detect fake news",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Pydantic models
class NewsAnalysisRequest(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None
    target_language: Optional[str] = None  # Added target language field

class NewsAnalysisResponse(BaseModel):
    verdict: str
    confidence: float
    reason: str
    sources: Dict[str, str]
    detected_language: Optional[str] = None  # Added detected language field

# Language detection and translation functions
async def detect_language(text):
    """Detect language of input text"""
    if not text or len(text.strip()) < 5:
        return "en"  # Default to English for short/empty texts
    
    try:
        url = "https://api.sarvam.ai/text-lid"
        payload = {"input": text}
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get('language_code', 'en')
    except Exception as e:
        print(f"Language detection error: {e}")
        return "en"

async def translate_text(text, target_lang):
    """Translate text to target language"""
    if not text or target_lang == "en":
        return text
    
    try:
        url = "https://api.sarvam.ai/translate"
        payload = {
            "source_language_code": "auto",
            "target_language_code": target_lang,
            "speaker_gender": "Male",
            "mode": "classic-colloquial",
            "model": "mayura:v1",
            "enable_preprocessing": False,
            "input": text
        }
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        if 'translated_text' in result:
            return result['translated_text']
        return text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

# Routes
@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"status": "API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api/analyze", response_model=NewsAnalysisResponse)
async def analyze_content(analysis_request: NewsAnalysisRequest):
    """Analyze news content for fake news detection"""
    if not analysis_request.text and not analysis_request.image_url:
        raise HTTPException(status_code=400, detail="Either text or image URL must be provided")
    
    # Detect language of the input text
    detected_language = "en"
    if analysis_request.text:
        detected_language = await detect_language(analysis_request.text)
    
    # Use specified target language or detected language
    target_language = analysis_request.target_language or detected_language
    
    # Prepare input for Gemini
    news_input = create_news_input(
        news_text=analysis_request.text or "", 
        image_source=analysis_request.image_url
    )
    
    # Get analysis from Gemini
    response_text = analyze_news(news_input)
    
    # Parse response
    analysis_result = extract_json_from_response(response_text, analysis_request.text or "")

    if not analysis_result:
        raise HTTPException(status_code=500, detail="Failed to parse analysis results")
    
    # Translate verdict and reason if needed
    if target_language != "en":
        to_translate = (
            f"Verdict: {analysis_result.get('verdict', 'Unknown')}\n\n"
            f"Confidence: {int(analysis_result.get('confidence', 0) * 100)}%\n\n"
            f"Reason: {analysis_result.get('reason', '')}"
        )
        
        translated_text = await translate_text(to_translate, target_language)
        
        # Extract the translated parts
        parts = translated_text.split("\n\n")
        if len(parts) >= 3:
            analysis_result['verdict'] = parts[0].replace("Verdict: ", "").strip()
            analysis_result['reason'] = parts[2].replace("Reason: ", "").strip()
    
    # Add detected language to the result
    analysis_result['detected_language'] = detected_language
    
    return analysis_result

@app.post("/api/analyze/upload", response_model=NewsAnalysisResponse)
async def analyze_uploaded_content(
    text: str = Form(None),
    image: UploadFile = File(None)
):
    """Analyze news content with uploaded image for fake news detection"""
    if not text and not image:
        raise HTTPException(status_code=400, detail="Either text or image must be provided")
    
    image_path = None
    try:
        if image:
            # Save uploaded image to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                image_path = temp_file.name
                contents = await image.read()
                temp_file.write(contents)
        
        # Prepare input for Gemini
        news_input = create_news_input(
            news_text=text or "", 
            image_source=image_path
        )
        
        # Get analysis from Gemini
        response_text = analyze_news(news_input)
        
        # Parse response
        analysis_result = extract_json_from_response(response_text, text or "")
        
        if not analysis_result:
            raise HTTPException(status_code=500, detail="Failed to parse analysis results")
        
        return analysis_result
    
    finally:
        # Clean up the temporary file
        if image_path and os.path.exists(image_path):
            os.unlink(image_path)

# Run the server
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)