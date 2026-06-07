import uvicorn
import os

from app.core.config import settings


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=settings.environment == "local")
