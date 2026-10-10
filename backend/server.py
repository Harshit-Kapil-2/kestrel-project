import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.data_loader import PostalDataLoader
from backend.geocoder import GeocodingManager
from backend.resolver import PostalResolver

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Initialize data and resolver
print("Initializing PostFinder backend engine...")
loader = PostalDataLoader(os.path.join(BASE_DIR, "pincodes.csv"))
geocoder = GeocodingManager(os.path.join(BASE_DIR, "coordinates_cache.json"))
resolver = PostalResolver(loader, geocoder)
print(f"Loaded {len(loader.records)} postal office records.")

app = FastAPI(title="PostFinder Backend API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResolveRequest(BaseModel):
    address: str

@app.post("/api/resolve")
async def resolve_address(payload: ResolveRequest):
    addr = payload.address.strip()
    if not addr:
        raise HTTPException(status_code=400, detail="Address cannot be empty.")
    result = resolver.resolve(addr)
    return result

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "PostFinder",
        "total_records": len(loader.records),
        "states_count": len(loader.all_states),
        "districts_count": len(loader.all_districts)
    }

# Static file serving
@app.get("/")
async def serve_index():
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "index.html not found"}

@app.get("/style.css")
async def serve_css():
    css_file = os.path.join(BASE_DIR, "style.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return HTTPException(status_code=404, detail="style.css not found")

@app.get("/script.js")
async def serve_js():
    js_file = os.path.join(BASE_DIR, "script.js")
    if os.path.exists(js_file):
        return FileResponse(js_file, media_type="application/javascript")
    return HTTPException(status_code=404, detail="script.js not found")

@app.get("/{filename:path}")
async def serve_static(filename: str):
    file_path = os.path.join(BASE_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Default to index.html for single-page app
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="File not found")
