from fastapi import APIRouter
from pydantic import BaseModel
import logging
import os
import base64
from google.cloud import texttospeech
from google.api_core.client_options import ClientOptions
import google.generativeai as genai

logger = logging.getLogger(__name__)

tts_router = APIRouter(
    prefix="/voice_service",
    tags=["tts"],
)

class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-US" # Default to en-US

import re

def wrap_ssml(text: str, language_code: str) -> str:
    """
    Wraps plain text in SSML tags to add natural rhythm.
    Adds pauses after punctuation and slight pitch/rate adjustments.
    """
    # Clean up markdown for TTS to prevent pronouncing "asterisk" or "hash"
    # Remove bold/italic asterisks and header hashes globally
    clean_text = re.sub(r'[*#]', '', text)
    # Remove bullet points (dash or plus followed by a space at start of lines)
    clean_text = re.sub(r'^\s*[-+]\s+', '', clean_text, flags=re.MULTILINE)
    
    # Escaping special characters for SSML
    ssml_text = clean_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Add natural pauses after periods and commas
    ssml_text = ssml_text.replace(". ", ". <break time='400ms'/>")
    ssml_text = ssml_text.replace("? ", "? <break time='500ms'/>")
    ssml_text = ssml_text.replace("! ", "! <break time='500ms'/>")
    ssml_text = ssml_text.replace(", ", ", <break time='200ms'/>")
    # Also add a pause for newlines to separate bullet points better
    ssml_text = ssml_text.replace("\n", " <break time='400ms'/>\n")
    
    # Language-specific tuning
    if "ar" in language_code.lower():
        # Egyptian/Arabic naturalization: Brisk, energetic pace
        return f"<speak><prosody rate='105%' pitch='+1st'>{ssml_text}</prosody></speak>"
    else:
        # English naturalization: Standard pace
        return f"<speak><prosody rate='110%' pitch='0st'>{ssml_text}</prosody></speak>"

@tts_router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Converts text to speech using Google Cloud Text-to-Speech (SSML enabled).
    """
    try:
        logger.info(f"Synthesizing text: {request.text[:50]}... in {request.language_code}")
        
        GOOGLE_API_KEY = os.getenv("GOOGLE_TTS_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY / GOOGLE_TTS_API_KEY not set")
            return {"status": "error", "message": "API Key not configured"}

        # We now instruct the host_agent to output conversational, flowing text without markdown natively.
        # This completely eliminates the 24-second delay of rewriting text with Gemini in the TTS pipeline.
        spoken_text = request.text

        # Initialize the client with API Key
        client_options = ClientOptions(api_key=GOOGLE_API_KEY)
        client = texttospeech.TextToSpeechClient(client_options=client_options)

        # Detect the best voice based on language_code
        lang = request.language_code.lower()
        
        # Voice IDs from environment
        en_voice_name = os.getenv("VOICE_TTS_EN_VOICE", "en-US-Journey-F")
        ar_voice_name = os.getenv("VOICE_TTS_AR_VOICE", "ar-XA-Studio-B")
        
        target_lang = request.language_code
        voice_name = en_voice_name

        if "ar" in lang:
            # Use ar-XA for Studio voices which are dialect-agnostic but high quality
            target_lang = "ar-XA"
            voice_name = ar_voice_name
        else:
            # Use the prefix from the voice name if available (e.g. en-US)
            if "-" in en_voice_name:
                parts = en_voice_name.split("-")
                if len(parts) >= 2:
                    target_lang = f"{parts[0]}-{parts[1]}"
            voice_name = en_voice_name

        # Wrap text in SSML for naturalness
        ssml_content = wrap_ssml(spoken_text, target_lang)
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_content)

        voice = texttospeech.VoiceSelectionParams(
            language_code=target_lang,
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        # Configure the audio file type
        # Pitch and Rate are handled inside SSML prosody tags now
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        # Convert to base64
        audio_base64 = base64.b64encode(response.audio_content).decode("utf-8")
        
        logger.info("TTS synthesis (SSML) successful")
        
        return {
            "audio_url": None,
            "audio_base64": audio_base64,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
