from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import jobs

app = FastAPI(
    title="Bulk Certificate Generator API",
    description="High-performance backend API using Supabase client to accept bulk certificate generation requests, process them asynchronously with fault isolation, track job progress, and retrieve generated PDF certificates individually or in bulk.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints
app.include_router(jobs.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": "Bulk Certificate Generator API",
        "version": "1.0.0",
        "database": "Supabase",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
