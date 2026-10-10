import csv
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

class PostalDataLoader:
    def __init__(self, csv_path: str = "pincodes.csv"):
        self.csv_path = csv_path
        self.records: List[Dict[str, str]] = []
        self.by_pincode: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.by_prefix: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.by_state: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.by_district: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.by_city: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.token_index: Dict[str, Set[int]] = defaultdict(set)
        self.all_states: Set[str] = set()
        self.all_districts: Set[str] = set()
        self.all_cities: Set[str] = set()
        self._load()

    def _normalize(self, text: str) -> str:
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    def _tokenize(self, text: str) -> List[str]:
        return [w for w in re.split(r'[^a-z0-9]+', str(text).lower()) if len(w) > 1]

    def _load(self):
        if not os.path.isabs(self.csv_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resolved_path = os.path.join(base_dir, self.csv_path)
            if os.path.exists(resolved_path):
                self.csv_path = resolved_path

        with open(self.csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            idx = 0
            for row in reader:
                office = row.get("PostOfficeName", "").strip()
                pincode = row.get("Pincode", "").strip()
                district = row.get("DistrictsName", "").strip()
                city = row.get("City", "").strip()
                state = row.get("State", "").strip()

                if not pincode or not office:
                    continue

                rec = {
                    "id": idx,
                    "office": office,
                    "pincode": pincode,
                    "district": district,
                    "city": city,
                    "state": state,
                    "type": self.classify_office_type(office, pincode)
                }
                self.records.append(rec)

                # Indexes
                self.by_pincode[pincode].append(rec)
                for prefix_len in (2, 3, 4, 5):
                    if len(pincode) >= prefix_len:
                        self.by_prefix[pincode[:prefix_len]].append(rec)

                norm_state = self._normalize(state)
                norm_dist = self._normalize(district)
                norm_city = self._normalize(city)

                if norm_state:
                    self.by_state[norm_state].append(rec)
                    self.all_states.add(state)

                if norm_dist:
                    self.by_district[norm_dist].append(rec)
                    self.all_districts.add(district)

                if norm_city:
                    self.by_city[norm_city].append(rec)
                    self.all_cities.add(city)

                # Token indexing for fuzzy/token search
                tokens = set(self._tokenize(office) + self._tokenize(district) + self._tokenize(city))
                for t in tokens:
                    self.token_index[t].add(idx)

                idx += 1

    @staticmethod
    def classify_office_type(office_name: str, pincode: str) -> str:
        name_lower = office_name.lower()
        if re.search(r'\b(h\s*o|head\s*office|head\s*post\s*office)\b', name_lower) or pincode.endswith("001"):
            return "Head Post Office (H.O)"
        if re.search(r'\b(s\s*o|sub\s*office|sub\s*post\s*office)\b', name_lower):
            return "Sub Post Office (S.O)"
        if re.search(r'\b(b\s*o|branch\s*office|branch\s*post\s*office)\b', name_lower):
            return "Branch Post Office (B.O)"
        # Default for urban / delivery offices
        if len(pincode) == 6 and int(pincode[-3:]) < 100:
            return "Sub Post Office (Delivery)"
        return "Sub Post Office"

    def get_by_pincode(self, pin: str) -> List[Dict[str, str]]:
        return self.by_pincode.get(pin.strip(), [])

    def get_by_prefix(self, prefix: str) -> List[Dict[str, str]]:
        return self.by_prefix.get(prefix.strip(), [])

    def get_by_district(self, district: str, state: Optional[str] = None) -> List[Dict[str, str]]:
        norm_dist = self._normalize(district)
        recs = self.by_district.get(norm_dist, [])
        if state:
            norm_st = self._normalize(state)
            recs = [r for r in recs if self._normalize(r["state"]) == norm_st]
        return recs

    def get_by_state(self, state: str) -> List[Dict[str, str]]:
        norm_st = self._normalize(state)
        return self.by_state.get(norm_st, [])

    def search_by_tokens(self, tokens: List[str], state: Optional[str] = None, district: Optional[str] = None, limit: int = 20) -> List[Dict[str, str]]:
        matched_indices: Dict[int, int] = defaultdict(int)
        for t in tokens:
            for idx in self.token_index.get(t.lower(), set()):
                matched_indices[idx] += 1

        if not matched_indices:
            return []

        norm_st = self._normalize(state) if state else None
        norm_dist = self._normalize(district) if district else None

        filtered = []
        for idx, count in matched_indices.items():
            rec = self.records[idx]
            if norm_st and self._normalize(rec["state"]) != norm_st:
                continue
            if norm_dist and self._normalize(rec["district"]) != norm_dist:
                continue
            filtered.append((count, rec))

        filtered.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in filtered[:limit]]
