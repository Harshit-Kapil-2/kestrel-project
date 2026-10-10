import re
from typing import Dict, Any, List, Optional, Tuple
from backend.constants import STATE_ALIASES, CITY_ALIASES, ABBREVIATIONS, ROMAN_NUMERALS

class AddressCleaner:
    def __init__(self, known_districts=None, known_cities=None):
        self.known_districts = {d.lower(): d for d in (known_districts or [])}
        self.known_cities = {c.lower(): c for c in (known_cities or [])}

    def clean_and_parse(self, raw_address: str) -> Dict[str, Any]:
        text = raw_address.strip()
        cleaned_words = []
        
        # 1. Detect 6-digit PIN code
        pincode_match = re.search(r'\b([1-9][0-9]{5})\b', text)
        detected_pincode = pincode_match.group(1) if pincode_match else None

        # 2. Detect partial PIN code (e.g. 5 digits like 20130, or 4 digits at the end)
        partial_pincode = None
        if not detected_pincode:
            partial_match = re.search(r'\b([1-9][0-9]{4})\b', text)
            if partial_match:
                partial_pincode = partial_match.group(1)

        # 3. Tokenize and normalize text for entity extraction
        tokens = [t.lower() for t in re.split(r'[,.\s/\\-]+', text) if t]
        
        # 4. State detection
        detected_state = None
        # Check 2-word states first (e.g., 'uttar pradesh', 'himachal pradesh')
        for i in range(len(tokens) - 1):
            two_word = f"{tokens[i]} {tokens[i+1]}"
            if two_word in STATE_ALIASES:
                detected_state = STATE_ALIASES[two_word]
                break

        if not detected_state:
            for t in tokens:
                if t in STATE_ALIASES:
                    detected_state = STATE_ALIASES[t]
                    break

        # 5. City & District detection
        detected_city = None
        detected_district = None

        # Check city aliases (e.g., blr -> Bangalore, noida -> Gautam Buddha Nagar, ldh -> Ludhiana)
        for i in range(len(tokens) - 1):
            two_word = f"{tokens[i]} {tokens[i+1]}"
            if two_word in CITY_ALIASES:
                detected_city = CITY_ALIASES[two_word][0]
                if not detected_state:
                    detected_state = CITY_ALIASES[two_word][1]
                break

        if not detected_city:
            for t in tokens:
                if t in CITY_ALIASES:
                    detected_city = CITY_ALIASES[t][0]
                    if not detected_state:
                        detected_state = CITY_ALIASES[t][1]
                    break

        # Check known districts
        if not detected_district:
            for t in tokens:
                if t in self.known_districts:
                    detected_district = self.known_districts[t]
                    break

        if detected_city and not detected_district:
            detected_district = detected_city

        # 6. Detect Block / Sector / Roman numerals (e.g., '5th blk' -> V Block, 'sector 62')
        block_or_sector = None
        roman_numeral = None
        sector_match = re.search(r'\b(?:sector|sec|sctr)\.?\s*([0-9a-zA-Z]+)\b', text, re.IGNORECASE)
        if sector_match:
            block_or_sector = f"Sector {sector_match.group(1).upper()}"

        block_match = re.search(r'\b([0-9a-zA-Z]+)(?:\s*(?:th|st|nd|rd))?\s*(?:block|blk|bk)\b', text, re.IGNORECASE)
        if block_match:
            b_val = block_match.group(1).lower()
            block_or_sector = f"{b_val.upper()} Block"
            if b_val in ROMAN_NUMERALS:
                roman_numeral = ROMAN_NUMERALS[b_val]

        # 7. Build a neat readable cleaned_address string
        cleaned_tokens = []
        for word in re.split(r'(\s+|,|\.)', text):
            w_strip = word.strip().lower()
            if not w_strip:
                cleaned_tokens.append(word)
                continue
            if w_strip in ABBREVIATIONS:
                expanded = ABBREVIATIONS[w_strip].title()
                cleaned_tokens.append(expanded)
            elif w_strip in CITY_ALIASES:
                cleaned_tokens.append(CITY_ALIASES[w_strip][0])
            elif w_strip in STATE_ALIASES:
                cleaned_tokens.append(STATE_ALIASES[w_strip])
            else:
                cleaned_tokens.append(word)

        cleaned_text = "".join(cleaned_tokens).strip()
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = re.sub(r'\s*,\s*', ', ', cleaned_text)

        # Capitalize nicely if not capitalized
        sentences = [s.strip().capitalize() for s in cleaned_text.split(', ') if s.strip()]
        cleaned_address = ", ".join(sentences)

        return {
            "raw_address": raw_address,
            "cleaned_address": cleaned_address,
            "pincode": detected_pincode,
            "partial_pincode": partial_pincode,
            "state": detected_state,
            "district": detected_district,
            "city": detected_city,
            "block_or_sector": block_or_sector,
            "roman_numeral": roman_numeral,
            "tokens": tokens
        }
