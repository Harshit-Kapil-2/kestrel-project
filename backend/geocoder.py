import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

from geopy.geocoders import ArcGIS, Nominatim, Photon
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from backend.constants import CENTROIDS

class GeocodingManager:
    def __init__(self, cache_file: str = "coordinates_cache.json"):
        if not os.path.isabs(cache_file):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.cache_file = os.path.join(base_dir, cache_file)
        else:
            self.cache_file = cache_file

        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

        # Initialize geopy geocoders
        self.arcgis = ArcGIS(timeout=7)
        self.nominatim = Nominatim(user_agent="PostFinder_Desktop_App/2.0", timeout=7)
        self.photon = Photon(timeout=7)

    def _normalize_key(self, text: str) -> str:
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    def _load_cache(self):
        import unicodedata
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, dict):
                            if "formatted_address" in v and isinstance(v["formatted_address"], str):
                                v["formatted_address"] = unicodedata.normalize('NFKD', v["formatted_address"]).encode('ascii', 'ignore').decode('ascii').strip()
                            self.cache[k] = v
                        elif isinstance(v, (list, tuple)) and len(v) == 2:
                            self.cache[k] = {"lat": float(v[0]), "lon": float(v[1])}
            except Exception:
                pass

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def geocode_user_location(self, text: str, fallback_components: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Converts user input text into an exact geological location using geopy,
        similar to Google Maps (returns lat, lon, full formatted address, and components).
        """
        norm_key = "user_" + self._normalize_key(text)
        if norm_key in self.cache and "lat" in self.cache[norm_key]:
            return self.cache[norm_key]

        search_candidates = [text]

        # If fallback components (clean address, city, district) are provided, add cleaner query variants
        if fallback_components:
            clean_addr = fallback_components.get("cleaned_address")
            if clean_addr and clean_addr != text:
                search_candidates.append(clean_addr)
            
            city = fallback_components.get("city")
            district = fallback_components.get("district")
            state = fallback_components.get("state")
            pin = fallback_components.get("pincode")
            block = fallback_components.get("block_or_sector")

            if block and (city or district):
                search_candidates.append(f"{block}, {city or district}, {state or ''}".strip(', '))
            if (city or district) and state:
                search_candidates.append(f"{city or district}, {state}, India")
            if pin:
                search_candidates.append(f"{pin}, India")

        # Try geocoders in priority order
        import unicodedata
        for query in search_candidates:
            loc = self._try_geopy_geocode(query)
            if loc:
                clean_addr = unicodedata.normalize('NFKD', loc.address).encode('ascii', 'ignore').decode('ascii').strip()
                result = {
                    "lat": round(loc.latitude, 6),
                    "lon": round(loc.longitude, 6),
                    "formatted_address": clean_addr or loc.address,
                    "provider": "geopy",
                    "maps_url": f"https://www.google.com/maps?q={loc.latitude},{loc.longitude}"
                }
                # Extract PIN from address if available
                pin_match = re.search(r'\b([1-9][0-9]{5})\b', loc.address)
                if pin_match:
                    result["extracted_pincode"] = pin_match.group(1)

                self.cache[norm_key] = result
                self._save_cache()
                return result

        # Fallback to offline centroids if offline
        centroid = None
        if fallback_components:
            dist = fallback_components.get("district") or fallback_components.get("city")
            st = fallback_components.get("state")
            if dist and dist in CENTROIDS:
                centroid = CENTROIDS[dist]
            elif st and st in CENTROIDS:
                centroid = CENTROIDS[st]

        if centroid:
            result = {
                "lat": centroid[0],
                "lon": centroid[1],
                "formatted_address": f"{fallback_components.get('district', '')}, {fallback_components.get('state', '')}, India",
                "provider": "offline_centroid",
                "maps_url": f"https://www.google.com/maps?q={centroid[0]},{centroid[1]}"
            }
            self.cache[norm_key] = result
            self._save_cache()
            return result

        return None

    def _try_geopy_geocode(self, query: str):
        # 1. Try ArcGIS (super reliable for Indian landmarks, streets, sectors)
        try:
            loc = self.arcgis.geocode(query)
            if loc:
                return loc
        except Exception:
            pass

        # 2. Try Nominatim (fine-grained OpenStreetMap)
        try:
            q_osm = query if "india" in query.lower() else f"{query}, India"
            loc = self.nominatim.geocode(q_osm, country_codes="in")
            if loc:
                return loc
        except Exception:
            pass

        # 3. Try Photon (OSM geocoder)
        try:
            loc = self.photon.geocode(query)
            if loc:
                return loc
        except Exception:
            pass

        return None

    def geocode_post_office(self, office_name: str, district: str, state: str, pincode: str) -> Tuple[float, float]:
        norm_key = "po_" + self._normalize_key(f"{office_name}_{district}_{pincode}")
        if norm_key in self.cache and "lat" in self.cache[norm_key]:
            return (self.cache[norm_key]["lat"], self.cache[norm_key]["lon"])

        # Try geocoding post office specifically
        queries = [
            f"Post Office {office_name} {district} {pincode}",
            f"{office_name} Post Office {pincode}",
            f"{office_name} {district} {state} {pincode}",
            f"{office_name} {district} {state}",
            f"{pincode}, India"
        ]

        for q in queries:
            loc = self._try_geopy_geocode(q)
            if loc:
                coords = (round(loc.latitude, 6), round(loc.longitude, 6))
                self.cache[norm_key] = {"lat": coords[0], "lon": coords[1], "address": loc.address}
                self._save_cache()
                return coords

        # Centroid fallback
        if district in CENTROIDS:
            return CENTROIDS[district]
        if state in CENTROIDS:
            return CENTROIDS[state]

        return (22.5, 79.0) # Center of India fallback

    @staticmethod
    def calculate_geodesic_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculates precise geodesic distance in kilometers using geopy."""
        return round(geodesic(point1, point2).km, 2)
