# PostFinder 📮
> **Messy address in, serviceable post office out.**

PostFinder is a desktop application powered by an intelligent postal resolution engine that maps unstructured, noisy Indian delivery addresses to their nearest serviceable Indian Post Office and PIN code, plotting them directly onto an interactive Leaflet map.

---

## 🚀 How to Run the Desktop Application

### Method 1: Double-Click Launcher (Recommended)
Simply double-click either:
- **`PostFinder.bat`**: Launches the desktop window with console logs.
- **`PostFinder.vbs`**: Launches silently in native desktop window mode with no background console.

### Method 2: Command Line
From the project folder, run:
```bash
# Launch native desktop application
py -3.11 desktop.py
# or
py -3.11 main.py

# Run standalone API server (for browser at http://localhost:8000)
py -3.11 main.py --server

# Run automated test suite
py -3.11 main.py --test

# Query directly from terminal
py -3.11 main.py --cli "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034"
```

---

## 🧠 Backend Engine Architecture

The backend engine (`backend/`) processes raw, noisy addresses through a multi-stage NLP & spatial matching pipeline:

1. **Address Normalization & Cleaning (`backend/cleaner.py`)**:
   - Expands common Indian delivery abbreviations (`nr` → Near, `opp` → Opposite, `blk` → Block, `sec` → Sector, `h no` → House No, etc.).
   - Converts city abbreviations (`blr` → Bangalore, `bom` → Mumbai, `del` → Delhi, `hyd` → Hyderabad, `ldh` → Ludhiana, `noida` → Gautam Buddha Nagar, etc.).
   - Translates state abbreviations (`UP`, `MP`, `HP`, `TN`, `KA`, `PB`, `MH`, etc.) to full state jurisdictions.
   - Maps block numbers and ordinal suffixes to Roman numerals (`5th blk` → `V Block`).

2. **In-Memory Multi-Index Data Loader (`backend/data_loader.py`)**:
   - Indexes all 39,736 post offices from `pincodes.csv` into memory upon startup.
   - Separate indices for exact 6-digit PIN codes, 2-to-5 digit prefix trees, districts, cities, states, and word tokens.
   - Classifies offices into Head Post Office (H.O), Sub Post Office (S.O), and Branch Office (B.O).

3. **Multi-Stage Candidate Resolution (`backend/resolver.py`)**:
   - **Stage 1 (Exact PIN)**: Matches 6-digit PIN code and scores sub-locality/block within that postal beat (e.g. `560034` + `5th blk` → `Koramangala V Block`).
   - **Stage 2 (Prefix PIN)**: Expands incomplete PIN codes (e.g. `20130` → `201301 Noida Complex`).
   - **Stage 3 (Administrative Hierarchy)**: Pinpoints State → District/City → Locality when no PIN is supplied.
   - **Stage 4 (Token & Landmark Correlation)**: Semantic token matching across all 39k offices.

4. **Geocoding & Spatial Routing (`backend/geocoder.py`)**:
   - High-precision live Nominatim geocoding with local JSON caching (`coordinates_cache.json`).
   - Comprehensive offline fallback centroid dictionary for all 36 Indian states and 60+ major districts.
   - Calculates Haversine distance in kilometers and renders delivery trajectory polylines on Leaflet.

---

## 📡 API Specification

### `POST /api/resolve`
**Request Body:**
```json
{
  "address": "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034"
}
```

**Response Format:**
```json
{
  "best": {
    "office": "Koramangala V Block",
    "pincode": "560034",
    "type": "Sub Post Office (Delivery)",
    "district": "Bangalore",
    "state": "Karnataka",
    "lat": 12.9374,
    "lon": 77.6270
  },
  "confidence": 0.99,
  "distance_km": 0.6,
  "parsed": {
    "cleaned_address": "Flat 4b, Near big bazar, Opposite sbi, Koramangla 5th block, Bangalore 560034"
  },
  "trace": [
    "Cleaned address and expanded common Indian postal abbreviations.",
    "Extracted 6-digit PIN code: 560034",
    "Retrieved 5 registered post offices for PIN 560034.",
    "Selected nearest serviceable office: Koramangala V Block (PIN: 560034).",
    "Selection criteria: Exact PIN match; Matched block numeral 'V' in office name (Koramangala V Block).",
    "Calculated distance: 0.6 km between delivery address and post office."
  ],
  "query_point": {
    "lat": 12.9345,
    "lon": 77.6225
  },
  "alternatives": [
    {
      "office": "Koramangala I Block (560034)",
      "score": "98%",
      "lat": 12.9366,
      "lon": 77.6229
    }
  ]
}
```

### `GET /api/health`
Checks server status and reports total indexed records.
