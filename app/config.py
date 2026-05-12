
 import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./garden.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "owner")
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")