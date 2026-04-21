from fastapi import APIRouter, UploadFile, File
import logging
import os
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

stt_router = APIRouter(
    prefix="/voice_service",
    tags=["stt"],
)

# Initialize Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

@stt_router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Converts audio file to text using Gemini 1.5 Flash.
    """
    try:
        content = await audio.read()
        logger.info(f"Received audio file {audio.filename}, size: {len(content)} bytes")
        
        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY not set")
            return {"status": "error", "message": "API Key not configured"}

        # Initialize model
        stt_model_id = os.getenv("VOICE_STT_MODEL_ID", "gemini-1.5-flash-latest")
        model = genai.GenerativeModel(stt_model_id)
        
        # Prepare the audio part
        audio_part = {
            "mime_type": audio.content_type or "audio/wav", # Default to wav if unknown
            "data": content
        }
        
        # Use loose safety settings for transcription to prevent false positives
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        # Call Gemini to transcribe
        response = model.generate_content([
            "Please transcribe the following audio accurately. Just return the verbatim transcript without any conversational filler or extra text. If the audio is in Arabic, provide the Arabic transcript. If English, provide English. If you hear no speech, return an empty string.",
            audio_part
        ], safety_settings=safety_settings)
        
        # Defensive check for response text
        transcription = ""
        try:
            if response and response.candidates and len(response.candidates) > 0:
                # Check if the candidate actually has parts (text)
                if response.candidates[0].content.parts:
                    transcription = response.text.strip()
                else:
                    logger.warning("Gemini returned a candidate with no message parts (likely silent audio).")
            else:
                logger.warning("Gemini returned no candidates for the audio.")
        except ValueError as ve:
            # This happens if response.text is accessed but blocked by safety or empty
            logger.warning(f"Could not retrieve text from Gemini response: {str(ve)}")
            transcription = ""
        logger.info(f"TRANSCRIPTION RESULT: '{transcription}'")
        
        return {
            "text": transcription,
            "status": "success",
            "filename": audio.filename
        }
    except Exception as e:
        logger.error(f"STT error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
