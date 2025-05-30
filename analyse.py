import os
import json
import requests
import io
from urllib.parse import urlparse
from dotenv import load_dotenv
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Part

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)

# Gemini model ID
model_id = "gemini-2.0-flash"

# Google Search tool
google_search_tool = Tool(google_search=GoogleSearch())

def analyze_news(news_input, model_id=model_id, google_search_tool=google_search_tool):
    """Analyze news or claim using Gemini."""
    response = client.models.generate_content(
        model=model_id,
        contents=news_input,
        config=GenerateContentConfig(
            system_instruction="""
            You are a Fake NEWS Detector. You will be given a news article or claim, and you need to determine if it is real or fake.
            Provide a JSON with: "verdict" ("Real", "Fake" or "Uncertain"), "confidence" (float 0-1), "reason" (proper valid reason for the verdict), "sources" (object with titles).
            example: {"verdict": "Fake", "confidence": 0.85, "reason": "The article contains misleading information.", "sources": {"title1": "source1", "title2": "source2"}}
            NOTE: Reverify the verdict before returning the response.
            In sources the title should be the title of the source and the link should be the link to the source.
            NOTE: IF HALF THE MESSAGE IS REAL AND HALF THE MESSAGE IS NOT THE RETURN CONFIDENCE AS 0.5 AND VERDICT AS UNCERTAIN
             
            """,
            tools=[google_search_tool]
        )
    )
    return response.text

def extract_json_from_response(response_text, user_text=""):
    """
    Extracts JSON object from response and enhances source links.
    
    Args:
        response_text (str): Response from Gemini
        user_text (str): Original user input to include in search queries
    """
    try:
        data = json.loads(response_text)
        # Process sources if they exist
        if isinstance(data, dict) and "sources" in data and isinstance(data["sources"], dict):
            for title, link in data["sources"].items():
                # Check if source link is not a valid URL
                if not str(link).startswith(('http://', 'https://')) or str(link).isdigit() or len(str(link)) < 5:
                    # Create a search link based on the title and user input
                    search_query = f"{title} {user_text[:50]}".strip().replace(' ', '+')
                    data["sources"][title] = f"https://www.google.com/search?q={search_query}"
        return data
    except json.JSONDecodeError:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1 and start < end:
            try:
                data = json.loads(response_text[start:end + 1])
                # Process sources if they exist
                if isinstance(data, dict) and "sources" in data and isinstance(data["sources"], dict):
                    for title, link in data["sources"].items():
                        # Check if source link is not a valid URL
                        if not str(link).startswith(('http://', 'https://')) or str(link).isdigit() or len(str(link)) < 5:
                            # Create a search link based on the title and user input
                            search_query = f"{title} {user_text[:50]}".strip().replace(' ', '+')
                            data["sources"][title] = f"https://www.google.com/search?q={search_query}"
                return data
            except:
                return None
        return None



def create_news_input(news_text="", image_source=None):
    """
    Prepares input for Gemini with image (from local path or URL) and optional text.
    
    Args:
        news_text (str): The news article or claim.
        image_source (str): URL or local file path to the image.
    
    Returns:
        list: Gemini input with image part and text.
    """
    try:
        image_bytes = None

        if image_source:
            parsed = urlparse(image_source)
            if parsed.scheme in ("http", "https"):
                # Image from URL
                response = requests.get(image_source)
                response.raise_for_status()
                image_bytes = response.content
            else:
                # Local image path
                with open(image_source, "rb") as f:
                    image_bytes = f.read()

        if image_bytes:
            image_part = Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            text_part = news_text.strip() if news_text.strip() else "news image"
            return [image_part, text_part]

        # If no image, return just the text
        return news_text.strip() or "No input provided."

    except Exception as e:
        print(f"⚠️ Error processing image: {e}")
        return news_text or "Image load failed."

def json_to_formatted_text(json_data):
    """
    Convert JSON data to formatted text compatible with Telegram markdown.
    
    Args:
        json_data (dict): The JSON data to format
        
    Returns:
        str: Formatted text representation of the JSON data for Telegram
    """
    # Extract data from JSON
    verdict = json_data.get("verdict", "Unknown")
    confidence = json_data.get("confidence", 0)
    reason = json_data.get("reason", "")
    sources = json_data.get("sources", {})
    
    # Convert confidence to percentage
    confidence_percent = int(confidence * 100) if isinstance(confidence, (int, float)) else confidence
    
    # Format text for Telegram (uses different markdown syntax)
    formatted_text = f"Verdict:  {verdict} \n\n"
    formatted_text += f"Confidence: {confidence_percent}% \n\n"
    formatted_text += f"Reason: {reason} \n\n"
    
    # Add sources if available
    if sources:
        formatted_text += "Sources:\n"
        for title, source in sources.items():
            # If source is a valid URL, use it directly
            if isinstance(source, str) and source.startswith(('http://', 'https://')):
                formatted_text += f"- [{title}]({source})\n"
            else:
                # Otherwise, create a Google search link using the title and user_text
                query = f"{title} {json_data.get('input', '')}".strip()
                query = query.replace(' ', '+')
                google_link = f"https://www.google.com/search?q={query}"
                formatted_text += f"- [{title}]({google_link})\n"
    return formatted_text


# === Main ===
if __name__ == "__main__":
    # Input from user
    user_text = input("📝 Enter news article or claim (leave blank if in image): ").strip()

    # Telegram image URL
    image_url = ""  # Replace <YOUR_BOT_TOKEN>

    # Create input for Gemini
    news_input = create_news_input(news_text=user_text)

    # Get response
    response_text = analyze_news(news_input)
    
    print("\n🔍 Gemini Raw Output:")
    print(response_text)

    # Pass user_text to extract_json_from_response
    parsed = extract_json_from_response(response_text, user_text)
    print("\n✅ Parsed Verdict:")
    print(parsed)
