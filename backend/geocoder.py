import json
import math
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple
from backend.constants import CENTROIDS

class GeocodingManager:
    def __init__(self, cache_file: str = "coordinates_cache.json"):
        if not os.path.isabs(cache_file):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.cache_file = os.path.join(base_dir, cache_file)
        else:
            self.cache_file = cache_file

        self.cache: Dict[str, Tuple[float, float]] = {}
        self._load_cache()
        self._seed_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, (list, tuple)) and len(v) == 2:
                            self.cache[k] = (float(v[0]), float(v[1]))
            except Exception:
                pass

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def _seed_cache(self):
        # Pre-seed sample locations and major hotspots
        seeds = {
            "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034": (12.9345, 77.6225),
            "koramangala v block bangalore 560034": (12.9352, 77.6248),
            "koramangala bangalore 560034": (12.9348, 77.6200),
            "koramangala i block bangalore 560034": (12.9288, 77.6290),
            "h no 12 gandhi nagar near hanuman mandir ludhiana punjab": (30.9126, 75.8530),
            "ludhiana h o ludhiana punjab 141001": (30.9084, 75.8576),
            "ludhiana ludhiana punjab 141001": (30.9084, 75.8576),
            "nit hamirpur anu hamirpur himachal": (31.7084, 76.5273),
            "hamirpur hamirpur himachal pradesh 177001": (31.6862, 76.5213),
            "govt degree clg hamirpur hamirpur himachal pradesh 177005": (31.6970, 76.5220),
            "gandhi chwk hamirpur hamirpur himachal pradesh 177001": (31.6885, 76.5235),
            "sector 62 noida UP 20130": (28.6258, 77.3649),
            "noida complex gautam buddha nagar uttar pradesh 201301": (28.5830, 77.3195),
            "estate gautam buddha nagar uttar pradesh 201303": (28.5720, 77.3310),
            "koramangala bangalore": (12.9357, 77.6240),
            "gandhi nagar ludhiana": (30.9126, 75.8530),
            "anu hamirpur": (31.6980, 76.5240),
            "sector 62 noida": (28.6258, 77.3649)
        }
        updated = False
        for k, v in seeds.items():
            norm_k = self._normalize_key(k)
            if norm_k not in self.cache:
                self.cache[norm_k] = v
                updated = True
        if updated:
            self._save_cache()

    def _normalize_key(self, text: str) -> str:
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    def geocode(self, query: str, state: Optional[str] = None, district: Optional[str] = None, pincode: Optional[str] = None) -> Optional[Tuple[float, float]]:
        norm_key = self._normalize_key(query)
        if norm_key in self.cache:
            return self.cache[norm_key]

        # Try Nominatim live geocoding
        q_clean = query.strip()
        if not re.search(r'\bindia\b', q_clean, re.IGNORECASE):
            q_clean = f"{q_clean}, India"

        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": q_clean,
            "format": "json",
            "limit": 1,
            "countrycodes": "in"
        })
        req = urllib.request.Request(url, headers={"User-Agent": "PostFinder-Desktop/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode())
                if data and "lat" in data[0] and "lon" in data[0]:
                    coords = (round(float(data[0]["lat"]), 5), round(float(data[0]["lon"]), 5))
                    self.cache[norm_key] = coords
                    self._save_cache()
                    return coords
        except Exception:
            pass

        # Fallback to District or City centroid
        if district and district in CENTROIDS:
            return CENTROIDS[district]
        if state and state in CENTROIDS:
            return CENTROIDS[state]

        # Scan text for any city/district in CENTROIDS
        for name, coords in CENTROIDS.items():
            if name.lower() in query.lower():
                return coords

        return None

    @staticmethod
    def haversine(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        r = 6371.0 # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 1)
