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
        trace.append("Converting user address into geological coordinates using geopy...")
        user_loc = self.geocoder.geocode_user_location(raw_address, fallback_components=parsed)

        user_coords = None
        user_formatted_address = None
        user_maps_url = None

        if user_loc:
            user_coords = (user_loc["lat"], user_loc["lon"])
            user_formatted_address = user_loc.get("formatted_address", parsed["cleaned_address"])
            user_maps_url = user_loc.get("maps_url")
            trace.append(f"Geopy resolved geological location: {user_formatted_address} ({user_coords[0]}, {user_coords[1]}).")

            # Extract postal code from geocoded location if missing
            if not parsed["pincode"] and user_loc.get("extracted_pincode"):
                parsed["pincode"] = user_loc["extracted_pincode"]
                trace.append(f"Extracted PIN code {parsed['pincode']} from geological location.")
        else:
            trace.append("Could not determine precise geological coordinates; proceeding with postal directory search.")

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
                "user_entered_address": raw_address,
                "parsed": parsed,
                "trace": trace + ["No matching postal office found in directory."]
            }

        # 3. Calculate Geodesic Distance for candidate post offices using geopy
        # Pure physical proximity: NO bias towards Head Post Office!
        # Small branch offices (B.O), sub offices (S.O), and head offices (H.O) are treated equally.
        block_or_sec = parsed["block_or_sector"]
        roman = parsed["roman_numeral"]

        # Limit candidates to a reasonable size if large (prioritizing token match)
        if len(candidates) > 15:
            ranked_candidates = []
            for c in candidates:
                txt_score = 0.0
                c_name = c["office"].lower()
                c_toks = set(re.split(r'[^a-z0-9]+', c_name))
                matches = [t for t in parsed["tokens"] if t in c_toks and len(t) > 2]
                txt_score += len(matches) * 1.0
                if roman and (f" {roman.lower()} " in f" {c_name} " or c_name.endswith(f" {roman.lower()}")):
                    txt_score += 3.0
                if block_or_sec and any(tok in c_name for tok in block_or_sec.lower().split()):
                    txt_score += 2.0
                ranked_candidates.append((txt_score, c))
            ranked_candidates.sort(key=lambda x: x[0], reverse=True)
            candidate_subset = [c for _, c in ranked_candidates[:12]]
        else:
            candidate_subset = candidates

        evaluated_offices: List[Tuple[float, float, Dict[str, Any], Tuple[float, float], List[str]]] = []

        for c in candidate_subset:
            office_name = c["office"]
            c_name_lower = office_name.lower()
            po_coords = self.geocoder.geocode_post_office(
                office_name, c["district"], c["state"], c["pincode"]
            )

            # Calculate geodesic distance
            d_km = 9999.0
            reasons = []
            if user_coords:
                d_km = self.geocoder.calculate_geodesic_distance(user_coords, po_coords)
                reasons.append(f"Geodesic distance: {d_km} km ({int(d_km * 1000)} meters)")
            else:
                reasons.append("Exact geographic beat")

            # Secondary score for tie-breaking when distances are virtually identical (within 100 meters)
            tie_breaker = 0.0
            if matched_stage == "exact_pin":
                tie_breaker += 1.0
                reasons.append("Exact PIN beat")

            if roman and (f" {roman.lower()} " in f" {c_name_lower} " or c_name_lower.endswith(f" {roman.lower()}")):
                tie_breaker += 2.0
                reasons.append(f"Matched block numeral '{roman}'")
            elif block_or_sec and any(tok in c_name_lower for tok in block_or_sec.lower().split()):
                tie_breaker += 1.5
                reasons.append(f"Matched sector/block token '{block_or_sec}'")

            c_toks = set(re.split(r'[^a-z0-9]+', c_name_lower))
            matches = [t for t in parsed["tokens"] if t in c_toks and len(t) > 2]
            if matches:
                tie_breaker += len(matches) * 0.5
                reasons.append(f"Locality: {', '.join(matches)}")

            # Effective distance: exact block/sector matches within same neighborhood beat get a slight 250m beat alignment
            effective_dist = d_km
            if (roman and f" {roman.lower()} " in f" {c_name_lower} ") or (block_or_sec and any(tok in c_name_lower for tok in block_or_sec.lower().split())):
                effective_dist = max(0.0, d_km - 0.30)
                reasons.append("Block/sector beat alignment")

            # Add to list: (effective_dist, d_km, -tie_breaker, candidate, po_coords, reasons)
            evaluated_offices.append((effective_dist, d_km, -tie_breaker, c, po_coords, reasons))

        # SORTING: Strictly by MINIMUM EFFECTIVE DISTANCE as primary key!
        # Smallest physical proximity wins, irrespective of whether it's a head, sub, or branch office!
        evaluated_offices.sort(key=lambda x: (x[0], x[1], x[2]))

        _, best_distance, _, best_office, best_coords, best_reasons = evaluated_offices[0]
        actual_distance = best_distance if best_distance < 9990.0 else None

        # Compute proximity confidence based on actual physical distance
        if actual_distance is not None:
            if actual_distance <= 1.0:
                final_confidence = 0.99
            elif actual_distance <= 3.0:
                final_confidence = 0.95
            elif actual_distance <= 7.0:
                final_confidence = 0.88
            elif actual_distance <= 15.0:
                final_confidence = 0.80
            else:
                final_confidence = 0.70
        else:
            final_confidence = 0.85

        trace.append(f"Identified nearest post office: {best_office['office']} (PIN: {best_office['pincode']}).")
        if actual_distance is not None:
            trace.append(f"Physical distance from address: {actual_distance} km ({int(actual_distance * 1000)} meters).")
        if best_reasons:
            trace.append(f"Proximity details: {'; '.join(best_reasons)}.")

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
            "distance_km": actual_distance,
            "distance_meters": int(actual_distance * 1000) if actual_distance is not None else None,
            "directions_url": (
                f"https://www.google.com/maps/dir/?api=1&origin={user_coords[0]},{user_coords[1]}&destination={best_coords[0]},{best_coords[1]}"
                if user_coords else None
            )
        }

        # Alternative nearby post offices
        alternatives = []
        for _, alt_dist, _, alt_rec, alt_coords, _ in evaluated_offices[1:4]:
            alt_d = alt_dist if alt_dist < 9990.0 else None
            alternatives.append({
                "office": f"{alt_rec['office']} ({alt_rec['pincode']})",
                "score": f"{alt_d} km away" if alt_d is not None else "Nearby",
                "distance_km": alt_d,
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
            "user_entered_address": raw_address,
            "confidence": round(final_confidence, 2),
            "distance_km": actual_distance,
            "parsed": {
                "cleaned_address": parsed["cleaned_address"],
                "geocoded_address": user_formatted_address
            },
            "trace": trace,
            "query_point": query_point_payload,
            "alternatives": alternatives
        }
