import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Supabase API credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Directory where generated PDF certificates are stored locally
CERTIFICATES_DIR = Path(os.getenv("CERTIFICATES_DIR", str(BASE_DIR / "generated_certificates")))
CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
