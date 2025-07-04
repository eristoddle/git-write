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

# Example of a protected endpoint (optional, for quick testing later if desired)
# from fastapi import Depends
# from .security import get_current_active_user
# from .models import User
#
# @app.get("/users/me/", response_model=User)
# async def read_users_me(current_user: User = Depends(get_current_active_user)):
# return current_user
