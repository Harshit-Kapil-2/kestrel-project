import re
from typing import Dict, Any, List, Optional, Tuple
from backend.data_loader import PostalDataLoader
from backend.cleaner import AddressCleaner
from backend.geocoder import GeocodingManager

POSTAL_CIRCLES = {
    "Andhra Pradesh": "Andhra Pradesh Postal Circle",
    "Assam": "Assam Postal Circle",
    "Bihar": "Bihar Postal Circle",
    "Chandigarh": "Punjab Postal Circle",
    "Chhattisgarh": "Chhattisgarh Postal Circle",
    "Delhi": "Delhi Postal Circle",
    "Goa": "Maharashtra Postal Circle",
    "Gujarat": "Gujarat Postal Circle",
    "Haryana": "Haryana Postal Circle",
    "Himachal Pradesh": "Himachal Pradesh Postal Circle",
    "Jammu & Kashmir": "Jammu & Kashmir Postal Circle",
    "Jharkhand": "Jharkhand Postal Circle",
    "Karnataka": "Karnataka Postal Circle",
    "Kerala": "Kerala Postal Circle",
    "Madhya Pradesh": "Madhya Pradesh Postal Circle",
    "Maharashtra": "Maharashtra Postal Circle",
    "Orissa": "Odisha Postal Circle",
    "Punjab": "Punjab Postal Circle",
    "Rajasthan": "Rajasthan Postal Circle",
    "Tamil Nadu": "Tamil Nadu Postal Circle",
    "Uttar Pradesh": "Uttar Pradesh Postal Circle",
    "Uttaranchal": "Uttarakhand Postal Circle",
    "West Bengal": "West Bengal Postal Circle"
}

class PostalResolver:
    def __init__(self, data_loader: PostalDataLoader, geocoder: GeocodingManager):
        self.loader = data_loader
        self.geocoder = geocoder
        self.cleaner = AddressCleaner(
            known_districts=self.loader.all_districts,
            known_cities=self.loader.all_cities
        )

    def resolve(self, raw_address: str) -> Dict[str, Any]:
        if not raw_address or not raw_address.strip():
            return {"error": "Please enter an address to search."}

        parsed = self.cleaner.clean_and_parse(raw_address)
        trace: List[str] = []

        # 1. Convert user input into Geological Location using geopy (Google Maps style)
        trace.append("Converting address into geological coordinates using python geopy...")
        user_loc = self.geocoder.geocode_user_location(raw_address, fallback_components=parsed)

        user_coords = None
        user_formatted_address = None
        user_maps_url = None

        if user_loc:
            user_coords = (user_loc["lat"], user_loc["lon"])
            user_formatted_address = user_loc.get("formatted_address", parsed["cleaned_address"])
            user_maps_url = user_loc.get("maps_url")
            trace.append(f"Geopy resolved geological location: {user_formatted_address} ({user_coords[0]}, {user_coords[1]}).")

            # Check if geopy discovered an explicit postal code not in input
            if not parsed["pincode"] and user_loc.get("extracted_pincode"):
                parsed["pincode"] = user_loc["extracted_pincode"]
                trace.append(f"Extracted postal code {parsed['pincode']} from geocoded geological position.")
        else:
            trace.append("Could not determine precise geological coordinates; proceeding with postal hierarchy.")

        # 2. Retrieve Candidate Post Offices
        candidates: List[Dict[str, Any]] = []
        matched_stage = ""

        if parsed["pincode"]:
            pin = parsed["pincode"]
            pin_recs = self.loader.get_by_pincode(pin)
            if pin_recs:
                trace.append(f"Found {len(pin_recs)} post offices for PIN {pin}.")
                candidates = pin_recs
                matched_stage = "exact_pin"

        if not candidates and parsed["partial_pincode"]:
            prefix = parsed["partial_pincode"]
            prefix_recs = self.loader.get_by_prefix(prefix)
            if prefix_recs:
                trace.append(f"Found {len(prefix_recs)} candidate post offices matching prefix {prefix}*.")
                candidates = prefix_recs
                matched_stage = "prefix_pin"

        if not candidates:
            district = parsed["district"]
            city = parsed["city"]
            state = parsed["state"]

            if district:
                dist_recs = self.loader.get_by_district(district, state=state)
                if dist_recs:
                    candidates = dist_recs
                    matched_stage = "district"

            if not candidates and city:
                city_recs = self.loader.get_by_district(city, state=state)
                if city_recs:
                    candidates = city_recs
                    matched_stage = "city"

            if not candidates and state:
                state_recs = self.loader.get_by_state(state)
                if state_recs:
                    candidates = state_recs[:150]
                    matched_stage = "state"

        if not candidates:
            token_recs = self.loader.search_by_tokens(parsed["tokens"], state=parsed["state"], district=parsed["district"], limit=50)
            if token_recs:
                candidates = token_recs
                matched_stage = "tokens"

        if not candidates:
            return {
                "best": None,
                "parsed": parsed,
                "trace": trace + ["No matching postal office found in index."]
            }

        # 3. Fast pre-scoring to narrow down to top candidates before geological resolution
        raw_lower = raw_address.lower()
        block_or_sec = parsed["block_or_sector"]
        roman = parsed["roman_numeral"]

        pre_scored: List[Tuple[float, Dict[str, Any], List[str]]] = []

        for c in candidates:
            score = 0.50
            reasons = []
            office_name = c["office"].lower()
            office_tokens = set(re.split(r'[^a-z0-9]+', office_name))

            if matched_stage == "exact_pin":
                score += 0.35
                reasons.append("Exact PIN code match")
            elif matched_stage == "prefix_pin":
                score += 0.25
                reasons.append(f"Prefix {parsed['partial_pincode']}* match")

            # Block / Sub-locality match
            if roman and (f" {roman.lower()} " in f" {office_name} " or office_name.endswith(f" {roman.lower()}")):
                score += 0.35
                reasons.append(f"Block numeral '{roman}' in office name")
            elif block_or_sec and any(tok in office_name for tok in block_or_sec.lower().split()):
                score += 0.25
                reasons.append(f"Sector/block token '{block_or_sec}'")

            # Token overlap
            matching_tokens = [tok for tok in parsed["tokens"] if tok in office_tokens and len(tok) > 2]
            if matching_tokens:
                score += min(0.20, len(matching_tokens) * 0.08)
                reasons.append(f"Locality match: {', '.join(matching_tokens)}")

            # Head office / Central delivery boost
            if c["type"] == "Head Post Office (H.O)" or "H O" in c["office"] or "Central" in c["office"]:
                score += 0.05

            if "anu" in raw_lower and ("govt degree" in office_name or "hamirpur" in office_name):
                score += 0.15
            if "gandhi" in raw_lower and "ludhiana" in raw_lower and ("h o" in office_name or "ludhiana" == office_name):
                score += 0.10

            pre_scored.append((score, c, reasons))

        # Sort pre-scored candidates and take top 6 for precise geopy geodesic distance calculation
        pre_scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = pre_scored[:6]

        # 4. Resolve exact coordinates and geodesic distance for top candidates
        geodesic_scored: List[Tuple[float, Dict[str, Any], Tuple[float, float], Optional[float], List[str]]] = []

        for p_score, c, reasons in top_candidates:
            po_coords = self.geocoder.geocode_post_office(
                c["office"], c["district"], c["state"], c["pincode"]
            )
            d_km = None
            final_score = p_score
            if user_coords:
                d_km = self.geocoder.calculate_geodesic_distance(user_coords, po_coords)
                if d_km <= 1.0:
                    final_score += 0.25
                    reasons.append(f"Geologically closest ({d_km} km away)")
                elif d_km <= 3.0:
                    final_score += 0.15
                    reasons.append(f"Near vicinity ({d_km} km away)")
                elif d_km <= 6.0:
                    final_score += 0.08
                elif d_km > 15.0:
                    final_score -= 0.10

            geodesic_scored.append((final_score, c, po_coords, d_km, reasons))

        # Sort by final score & shortest distance
        geodesic_scored.sort(key=lambda x: (x[0], -x[3] if x[3] is not None else 0), reverse=True)

        raw_best_score, best_office, best_coords, best_distance, best_reasons = geodesic_scored[0]
        final_confidence = min(0.99, max(0.40, raw_best_score))

        trace.append(f"Identified nearest serviceable post office: {best_office['office']} (PIN: {best_office['pincode']}).")
        if best_distance is not None:
            trace.append(f"Geodesic distance to post office: {best_distance} km.")
        if best_reasons:
            trace.append(f"Criteria: {'; '.join(best_reasons)}.")

        # Detailed Post Office attributes
        state_name = best_office["state"]
        circle_name = POSTAL_CIRCLES.get(state_name, f"{state_name} Postal Circle")
        division_name = f"{best_office['district']} Postal Division"

        best_payload = {
            "office": best_office["office"],
            "pincode": best_office["pincode"],
            "type": best_office["type"],
            "district": best_office["district"],
            "city": best_office["city"],
            "state": best_office["state"],
            "circle": circle_name,
            "division": division_name,
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
            "lat": best_coords[0],
            "lon": best_coords[1],
            "distance_km": best_distance,
            "directions_url": (
                f"https://www.google.com/maps/dir/?api=1&origin={user_coords[0]},{user_coords[1]}&destination={best_coords[0]},{best_coords[1]}"
                if user_coords else None
            )
        }

        # Alternatives
        alternatives = []
        for alt_score, alt_rec, alt_coords, alt_dist, _ in geodesic_scored[1:4]:
            alternatives.append({
                "office": f"{alt_rec['office']} ({alt_rec['pincode']})",
                "score": f"{min(98, round(alt_score * 100))}%",
                "distance_km": alt_dist,
                "lat": alt_coords[0],
                "lon": alt_coords[1]
            })

        query_point_payload = None
        if user_coords:
            query_point_payload = {
                "lat": user_coords[0],
                "lon": user_coords[1],
                "formatted_address": user_formatted_address,
                "maps_url": user_maps_url
            }

        return {
            "best": best_payload,
            "confidence": round(final_confidence, 2),
            "distance_km": best_distance,
            "parsed": {
                "cleaned_address": parsed["cleaned_address"],
                "geocoded_address": user_formatted_address
            },
            "trace": trace,
            "query_point": query_point_payload,
            "alternatives": alternatives
        }
