from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Gemini API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")