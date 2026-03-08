from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from functools import lru_cache
import time
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests from your Canva Code

# Configuration
ROBLOX_API_URL = "https://users.roblox.com/v1/usernames/users"
CACHE_DURATION = 3600  # Cache results for 1 hour
MAX_CACHE_SIZE = 1000  # Maximum cached results

# Simple in-memory cache with expiration
class CacheManager:
    def __init__(self):
        self.cache = {}
    
    def get(self, key):
        if key in self.cache:
            data, expiration = self.cache[key]
            if datetime.now() < expiration:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value, duration=CACHE_DURATION):
        if len(self.cache) >= MAX_CACHE_SIZE:
            # Remove oldest entry if cache is full
            oldest_key = list(self.cache.keys())[0]
            del self.cache[oldest_key]
        
        expiration = datetime.now() + timedelta(seconds=duration)
        self.cache[key] = (value, expiration)
    
    def clear(self):
        self.cache.clear()

cache_manager = CacheManager()

def validate_username(username):
    """
    Validate username format
    Returns (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 20:
        return False, "Username must be at most 20 characters"
    
    # Roblox allows letters, numbers, underscores, and hyphens
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    return True, None

def check_roblox_username_api(username):
    """
    Check if a Roblox username exists using the official Roblox API
    Returns a dictionary with the result
    """
    try:
        # Check cache first
        cached_result = cache_manager.get(username.lower())
        if cached_result:
            return cached_result
        
        # Roblox API endpoint to get user by username
        payload = {
            "usernames": [username],
            "excludeBannedUsers": False
        }
        
        response = requests.post(
            ROBLOX_API_URL,
            json=payload,
            timeout=10,
            headers={'User-Agent': 'Roblox-Username-Checker/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('data') and len(data['data']) > 0:
                user = data['data'][0]
                result = {
                    "exists": True,
                    "username": user.get('name'),
                    "user_id": user.get('id'),
                    "display_name": user.get('displayName'),
                    "created_at": datetime.now().isoformat()
                }
            else:
                result = {
                    "exists": False,
                    "username": username,
                    "created_at": datetime.now().isoformat()
                }
            
            # Cache the result
            cache_manager.set(username.lower(), result)
            return result
        
        else:
            return {
                "error": f"Roblox API returned status {response.status_code}",
                "exists": None
            }
    
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Roblox API may be slow."}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to Roblox API. Check your internet connection."}
    except requests.exceptions.RequestException as e:
        return {"error": f"API Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@app.route('/api/check-username', methods=['POST', 'OPTIONS'])
def api_check_username():
    """
    Endpoint that receives username from Canva Code and returns result
    Expected JSON: { "username": "username_to_check" }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        username = data.get('username', '').strip()
        
        # Validate username
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Check username via Roblox API
        result = check_roblox_username_api(username)
        
        # If there was an error, return it
        if "error" in result:
            return jsonify(result), 500
        
        return jsonify(result), 200
    
    except ValueError as e:
        return jsonify({"error": "Invalid JSON in request body"}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/cache-stats', methods=['GET'])
def cache_stats():
    """
    Returns cache statistics (for debugging)
    """
    return jsonify({
        "cached_items": len(cache_manager.cache),
        "max_cache_size": MAX_CACHE_SIZE,
        "cache_duration_seconds": CACHE_DURATION
    }), 200

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """
    Clears the cache (for debugging/maintenance)
    """
    cache_manager.clear()
    return jsonify({"status": "Cache cleared"}), 200

@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "ok",
        "service": "Roblox Username Checker",
        "version": "1.0"
    }), 200

@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint with API documentation
    """
    return jsonify({
        "name": "Roblox Username Checker API",
        "version": "1.0",
        "endpoints": {
            "POST /api/check-username": "Check if a username exists on Roblox",
            "GET /health": "Health check",
            "GET /api/cache-stats": "View cache statistics",
            "POST /api/clear-cache": "Clear the cache"
        },
        "example_request": {
            "endpoint": "POST /api/check-username",
            "body": {"username": "Roblox"}
        }
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("🚀 Roblox Username Checker API Starting...")
    print("📍 Running on http://localhost:5000")
    print("📚 Documentation available at http://localhost:5000/")
    print("\nEndpoints:")
    print("  • POST /api/check-username - Check username")
    print("  • GET /health - Health check")
    print("  • GET /api/cache-stats - View cache")
    print("  • POST /api/clear-cache - Clear cache\n")
    
    # Run the app
    app.run(debug=True, port=5000, host='0.0.0.0')
