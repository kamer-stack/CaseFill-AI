"""
CaseFill-AI Server Entrypoint
Run: python run.py
"""

import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting CaseFill-AI server on http://{HOST}:{PORT}")
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )
