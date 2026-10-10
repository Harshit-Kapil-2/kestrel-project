import sys
import os
import argparse
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def main():
    parser = argparse.ArgumentParser(description="PostFinder - Delivery Address to Post Office Matching Engine")
    parser.add_argument("--server", action="store_true", help="Run as standalone HTTP/API server")
    parser.add_argument("--port", type=int, default=8000, help="Port for server (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for server (default: 127.0.0.1)")
    parser.add_argument("--cli", type=str, help="Resolve address directly in terminal and output JSON")
    parser.add_argument("--test", action="store_true", help="Run automated test suite on sample addresses")

    args = parser.parse_args()

    if args.cli:
        from backend.data_loader import PostalDataLoader
        from backend.geocoder import GeocodingManager
        from backend.resolver import PostalResolver

        loader = PostalDataLoader(os.path.join(BASE_DIR, "pincodes.csv"))
        geocoder = GeocodingManager(os.path.join(BASE_DIR, "coordinates_cache.json"))
        resolver = PostalResolver(loader, geocoder)
        result = resolver.resolve(args.cli)
        print(json.dumps(result, indent=2))
        return

    if args.test:
        from backend.data_loader import PostalDataLoader
        from backend.geocoder import GeocodingManager
        from backend.resolver import PostalResolver

        loader = PostalDataLoader(os.path.join(BASE_DIR, "pincodes.csv"))
        geocoder = GeocodingManager(os.path.join(BASE_DIR, "coordinates_cache.json"))
        resolver = PostalResolver(loader, geocoder)

        samples = [
            "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034",
            "h no 12 gandhi nagar near hanuman mandir ludhiana punjab",
            "nit hamirpur anu hamirpur himachal",
            "sector 62 noida UP 20130"
        ]

        print("Running PostFinder Test Suite...")
        for s in samples:
            res = resolver.resolve(s)
            assert res.get("best") is not None, f"Failed match on: {s}"
            print(f"[PASS] '{s[:35]}...' -> {res['best']['office']} ({res['best']['pincode']}) | Conf: {res['confidence']}")
        print("All tests passed successfully!")
        return

    if args.server:
        import uvicorn
        from backend.server import app
        print(f"Starting PostFinder API server on http://{args.host}:{args.port}...")
        uvicorn.run(app, host=args.host, port=args.port)
        return

    # Default action: launch desktop application
    import desktop
    desktop.main()

if __name__ == "__main__":
    main()
