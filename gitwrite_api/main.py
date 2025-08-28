from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, repository, uploads, annotations # Import the auth, repository, uploads and annotations routers

app = FastAPI(
    title="GitWrite API",
    description="API for Git-based version control for writers.",
    version="0.1.0", # Example version
)

# Set up CORS
origins = [
    "http://localhost:5173",
    "http://localhost:3000", # Example for a React dev server
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the authentication router
app.include_router(auth.router)
# Include the repository router
app.include_router(repository.router)

# Include the new routers from uploads.py
app.include_router(uploads.router) # This is the router for /initiate and /complete
app.include_router(uploads.session_upload_router) # This is the router for /upload-session

# Include the annotations router
app.include_router(annotations.router)

@app.get("/")
async def root():
    return {"message": "Welcome to GitWrite API - Health Check OK"}

@app.get("/health")
async def health_check():
    """Detailed health check endpoint for monitoring and deployment."""
    import time
    import os
    from pathlib import Path
    
    # Check system resources and dependencies
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.1.0",
        "environment": os.getenv("GITWRITE_ENV", "development"),
        "checks": {
            "api": "ok",
            "storage": "ok",
            "dependencies": "ok"
        }
    }
    
    try:
        # Check if storage directories are accessible
        repo_path = os.getenv("GITWRITE_REPO_PATH", "/app/data/repositories")
        export_path = os.getenv("GITWRITE_EXPORT_PATH", "/app/data/exports")
        
        if not Path(repo_path).exists():
            health_status["checks"]["storage"] = "warning - repo path not found"
        if not Path(export_path).exists():
            health_status["checks"]["storage"] = "warning - export path not found"
            
        # Check critical dependencies
        try:
            import pygit2
            import pypandoc
            pypandoc.get_pandoc_path()  # This will raise if pandoc is not found
        except ImportError as e:
            health_status["checks"]["dependencies"] = f"error - missing dependency: {e}"
            health_status["status"] = "degraded"
        except OSError:
            health_status["checks"]["dependencies"] = "warning - pandoc not found"
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
    
    # Return appropriate HTTP status code
    from fastapi import HTTPException
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

# Example of a protected endpoint (optional, for quick testing later if desired)
# from fastapi import Depends
# from .security import get_current_active_user
# from .models import User
#
# @app.get("/users/me/", response_model=User)
# async def read_users_me(current_user: User = Depends(get_current_active_user)):
# return current_user
