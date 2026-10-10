# PostFinder 📮
> **Geological Location & Nearest Post Office Resolver powered by Python `geopy`**

PostFinder is a desktop application that converts noisy, unstructured address text into an exact geological location (similar to Google Maps), finds the physically nearest serviceable Indian Post Office, and displays comprehensive postal beat details, available services, and interactive map navigation.

---

## 🌟 Key Capabilities

1. **Text to Geological Location (Google Maps style)**:
   - Takes messy or partial user text and converts it into precise geographical coordinates $(\text{latitude}, \text{longitude})$ and a structured formatted address using Python `geopy` (ArcGIS, OpenStreetMap Nominatim, and Photon engines).
2. **Geodesic Nearest Post Office Calculation**:
   - Calculates the true ellipsoidal distance (WGS-84) using `geopy.distance.geodesic`.
   - Ranks all candidate post offices by actual physical proximity (kilometers / meters).
3. **Rich Post Office Details**:
   - Post office name & PIN code
   - Category & type: Sub Post Office (S.O), Head Post Office (H.O), Branch Office (B.O)
   - Postal Circle, Division, and Region
   - Available services: Speed Post, Registered Letter, Parcel Booking, Post Office Savings Bank (POSB), Aadhaar Services, PLI
   - Operating hours and counter timings
   - One-click Google Maps Navigation link
4. **Interactive Leaflet Desktop Map**:
   - User geological location marker (Blue)
   - Nearest post office marker (Red)
   - Route trajectory dashed polyline connecting user to the post office
   - Alternative nearby post offices with proximity tags

---

## 🚀 How to Run the Desktop Application

### Double-Click Launcher (Recommended)
- **`PostFinder.bat`**: Double-click to launch with console logs.
- **`PostFinder.vbs`**: Double-click for a silent native desktop window without background terminal.

### Command Line
```bash
# Launch desktop app window
py -3.11 desktop.py
# or
py -3.11 main.py

# Query directly from terminal (CLI)
py -3.11 main.py --cli "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034"

# Run automated test suite
py -3.11 main.py --test

# Standalone API server (http://127.0.0.1:8000)
py -3.11 main.py --server
```

---

## 📡 API Specification

### `POST /api/resolve`
**Request Body:**
```json
{
  "address": "Connaught Place New Delhi 110001"
}
```

**Response Format:**
```json
{
  "best": {
    "office": "Connaught Place",
    "pincode": "110001",
    "type": "Sub Post Office",
    "district": "Central Delhi",
    "city": "New Delhi",
    "state": "Delhi",
    "circle": "Delhi Postal Circle",
    "division": "Central Delhi Postal Division",
    "delivery_status": "Delivery Office (Serviceable Beat)",
    "services": [
      "Speed Post & Tracking",
      "Registered Post",
      "Parcel & Logistics Post",
      "Post Office Savings Bank (POSB)",
      "Aadhaar Services (Enrollment & Update)",
      "Postal Life Insurance (PLI)"
    ],
    "timings": "Mon - Sat: 9:00 AM - 5:00 PM (Public Counters: 9:30 AM - 3:30 PM)",
    "lat": 28.6318,
    "lon": 77.2185,
    "distance_km": 0.09,
    "directions_url": "https://www.google.com/maps/dir/?api=1&origin=28.6310,77.2183&destination=28.6318,77.2185"
  },
  "confidence": 0.99,
  "distance_km": 0.09,
  "query_point": {
    "lat": 28.6310,
    "lon": 77.2183,
    "formatted_address": "110001, New Delhi, Delhi",
    "maps_url": "https://www.google.com/maps?q=28.6310,77.2183"
  },
  "parsed": {
    "cleaned_address": "Connaught Place, New Delhi, Delhi 110001",
    "geocoded_address": "110001, New Delhi, Delhi"
  },
  "alternatives": [
    {
      "office": "Janpath (110001)",
      "score": "95%",
      "distance_km": 0.65,
      "lat": 28.6258,
      "lon": 77.2192
    }
  ]
}
```
