import os
import random
import time
import socket
import urllib.request
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

# দ্রুত রেসপন্স নিশ্চিত করতে ২ সেকেন্ড টাইমআউট
socket.setdefaulttimeout(2)

app = Flask(__name__)
CORS(app)

API_KEY = "YT_SECURE_API_V1_2026_PRO"

# -------------------------------------------------------------
# Supabase এর সেটিংস (আপনার Supabase Credentials দিন)
# -------------------------------------------------------------
SUPABASE_URL = "https://xzwbejlxdjixndvrwvey.supabase.co"
SUPABASE_KEY = "sb_publishable_UXzBvtY5Javvg5DwaS1l6g_OUC18jr5"

# ইন-মেমোরি প্রক্সি পুল ক্যাশে
PROXY_POOL = []

# প্রতি রিকোয়েস্টে সর্বোচ্চ কয়টি প্রক্সি ট্রাই করা হবে
MAX_RETRIES = 3


def load_proxies_from_supabase():
    """Supabase Rest API ব্যবহার করে প্রক্সি লোড করার ফাংশন"""
    global PROXY_POOL
    try:
        # Supabase 'proxies' টেবিল থেকে শুধু live প্রক্সি আনার রিকোয়েস্ট
        endpoint = f"{SUPABASE_URL}/rest/v1/proxies?status=eq.live&select=ip"
        req = urllib.request.Request(
            endpoint,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                # ইন-মেমোরি প্রক্সি পুল আপডেট (পুরনো ডাটা মুছে যাবে)
                PROXY_POOL = [item['ip'] for item in data if 'ip' in item]
                print(f" Successfully loaded {len(PROXY_POOL)} active proxies from Supabase.")
                return True
    except Exception as e:
        print(f" Failed to load proxies from Supabase: {e}")
    
    return False


# সার্ভার চালু হওয়ার সাথে সাথেই Supabase থেকে প্রক্সি লোড হবে
load_proxies_from_supabase()


def get_base_opts(proxy_url=None):
    """yt-dlp কনফিগারেশন অপশন"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "cachedir": False,
        "format": "best[protocol=https]/best",
        "socket_timeout": 4,  # প্রক্সি ব্লকড থাকলে দ্রুত পরবর্তী প্রক্সিতে যাওয়ার জন্য ৪ সেকেন্ড টাইমআউট
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web",
                    "android_tv",
                    "ios"
                ]
            }
        }
    }
    if proxy_url:
        opts["proxy"] = proxy_url
    return opts


def extract_with_fallback(url):
    """প্রক্সি ফেইল করলে স্বয়ংক্রিয়ভাবে পরবর্তী প্রক্সি ব্যবহারের ফাংশন"""
    if not PROXY_POOL:
        with yt_dlp.YoutubeDL(get_base_opts()) as ydl:
            return ydl.extract_info(url, download=False)

    available_proxies = list(PROXY_POOL)
    random.shuffle(available_proxies)

    attempts = min(MAX_RETRIES, len(available_proxies))
    last_error = None

    for attempt in range(attempts):
        selected_proxy = available_proxies.pop()
        try:
            opts = get_base_opts(selected_proxy)
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(f"All {attempts} proxy attempts failed. Last error: {last_error}")


@app.route("/")
def home():
    return f"API is Running! Total active proxies in memory: {len(PROXY_POOL)}"


@app.route("/get-link")
def get_link():
    key = request.args.get("key")
    url = request.args.get("url")

    if key != API_KEY:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    if not url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    start = time.time()

    try:
        info = extract_with_fallback(url)
        return jsonify({
            "success": True,
            "mode": "direct",
            "playback": info.get("url"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "took": round(time.time() - start, 2)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Extraction failed",
            "detail": str(e)
        }), 500


@app.route("/admin/reload-proxies", methods=["POST"])
def reload_proxies():
    """অ্যাডমিন প্যানেল থেকে সংকেত পাওয়ার পর ইন-মেমোরি প্রক্সি রিফ্রেশ করার এন্ডপয়েন্ট"""
    key = request.args.get("key")
    if key != API_KEY:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    success = load_proxies_from_supabase()
    if success:
        return jsonify({
            "success": True, 
            "message": "Memory updated successfully from Supabase", 
            "total_proxies": len(PROXY_POOL)
        }), 200
    else:
        return jsonify({
            "success": False, 
            "error": "Failed to fetch updated proxies"
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
