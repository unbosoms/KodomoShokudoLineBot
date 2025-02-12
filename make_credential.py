import os
import base64
from dotenv import load_dotenv

load_dotenv()
credentials_base64=os.environ.get("GOOGLE_CREDENTIALS")

if credentials_base64:
    with open("credentials.json", "wb") as f:
        f.write(base64.b64decode(credentials_base64))
