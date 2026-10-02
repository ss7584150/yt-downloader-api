import os
import time
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import random
import requests
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

# ======================
# CONFIG & FIREBASE
# ======================
API_KEY = "YT_SECURE_API_V1_2026_PRO"

firebase_credentials = {
  "type": "service_account",
  "project_id": "proxy-service-61a43",
  "private_key_id": "66ff3630a06adf5eb4eb0c11b879b53bb575794b",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCyRVuQfDvfxIHf\nrgD1RaYyluZmJWdDxHxUCitHt487GenZwVQwpYLOWQHsVSFUf1Rgu+GVBtZzXHdr\n/OWz+IhZvFwp/krgH+f2c+K9uO6SsPTf8rCKyRFXyZL2XGFPoV8MRHkqu8eblOxI\n8Fw6t0etH9e7uZj4GYvwefIm+miFJ6w8G9IRwyxf/AEUI0Sc1llxuptATY1+yItF\nKo7rxQTFvKjWCbaNCNgCAYp+0WbhZq9luhs9F8W01W/N0JSEBe0aWy7hD2nho/E0\nZUdDWyh8LqvXeazh+6TiGOmzaiqLU9hrrM+Fk3Mwq6F/fTnEKL36QpaQR24R0dC2\nzu5HXUllAgMBAAECggEAH0Ettn0xeh/XrUGyhU36v2/ZYRs5qZXvPkSyJda20+PN\nLhJJEmZSMp9ESQz71Pal8ne+KwSR4JPblCE4nH78WM8/UVV2BylQ39KddCnSGgHQ\nTNsdvJdX5Q5AJ9U2cmGWam4u2CEn88z+SCNr6BduB5pHlnAJs6W29ShMJs6W29ShMHi1U2dM5\nbny9VeothqAffo1kd5oOfOGCZDMR2DDfKCPYzjUY5fc9LfZxs9bcqz1H26kCpckf\n9T54KdgCBwJ8Gtutcmm7th7L02yI4QCoLukj/16e9+//80oKnuYt4/fzstb27EUR\nU/JCQNumjZ6n7jxHu7oNJSoggQD7m1Dwc3tjGa5SgQKBgQDusYKx5iK8etixKUxu\nJ2jmWSDMJGA/P7N4VaS2eOViQ3NsUK5/YsIa6IAe0IinFgiaXjX6lpLbseS9z39m\n62lLgYA3ygcBTzdY3OwfeU/bP78BdRP6vMiJFizai5zpOYrSxeTFhWTbSjocOHmW\nqMh5jGPL3g/ssMLtLMKkHt5nEQKBgQC/MlHsBSMlPQTf6/pf0QhAL+fwlJvZHQWr\nqpwmNJ/u6A8mCSFLWEALFAaWZLIJ7OHPBEDxiwWEv1Sen88k0NIlRs7j9/dVxxrj\nqJaiXR/hkMSC4ANxJ7jFvznTHWeHYrfrd83fPgi65XsRCzWXE1C9prN8gwnoCjKW\nQxEW2GOFFQKBgBaT1c/r+8cmO47uYBtfQO3g6lhE7JGu/dPZDf5wiwnzZVyOeSL1\nfXS8HzpK8VIUpHWtiZ+NVJDRT9igYuWiSNBqjG06f9Ug4BRYuUD04ZfUfMWvhFdI\nOhO1dEKryAjLd5UeQNhqGLMhX0PCF8YnaucMX3guJgV2Zsm2XSbXAKRxAoGBAKIT\nQvTDKhbQEgjLnjOJG+hlc8UyBKbYfk0WVEXiyEyaNPU2Oh4HkkqR0D++3lmhj42Q\neokHI0dzdYT9zXfU+L8Wthzzv5vcK0QfTooWTQdGU/7pbKGIXY5r2tXGkFNo8KXP\nqhn7GSVtkJRTHzuQ6RnLbU04O7aSpm1QLvVhu4M9AoGAQkwfc8tcMEmUFK5cKI/t\nBgcIPhqNbj2LTD4952ZutxV1FQJiOLnZLVX4OE3Cb3dU7HZC7OZFuGHTWAZGOJOD\n1DLj34aGmGNpBmK2fb/UI2ElIs3t/IIvszXKMsfsJrf/virgcfafCaLO7brZ+3mJ\nqYHZfPiTsbbYX+8TiyUx52E=\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@proxy-service-61a43.iam.gserviceaccount.com",
  "client_id": "109257419616440087075",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40proxy-service-61a43.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://proxy-service-61a43-default-rtdb.firebaseio.com/'
    })

live_proxies_ref = db.reference('proxies/live')
dead_proxies_ref = db.reference('proxies/dead')

# ======================
# IN-MEMORY CACHE (PYTHON SERVER PROXY STORAGE)
# ======================
LOCAL_PROXIES = []
proxy_lock = threading.Lock()

def on_proxy_update(event):
    """
    Firebase-এ কোনো পরিবর্তন (Add/Delete/Update) হলে এই ফাংশনটি স্বয়ংক্রিয়ভাবে কল হবে।
    এটি মেমোরির পুরনো প্রক্সি ডিলিট করে নতুন ডাটা সেভ করবে।
    """
    global LOCAL_PROXIES
    data = live_proxies_ref.get()
    
    with proxy_lock:
        LOCAL_PROXIES.clear()  # পুরনো ডাটা মুছে ফেলা হচ্ছে
        if data:
            if isinstance(data, dict):
                LOCAL_PROXIES = list(data.values())
            elif isinstance(data, list):
                LOCAL_PROXIES = list(data)
        print(f"[FIREBASE SYNC] Proxies updated in Python memory. Total active proxies: {len(LOCAL_PROXIES)}")

def start_firebase_listener():
    """
    Firebase Realtime Listener চালু করে যাতে Firebase থেকে বারবার ডাটা রিড করতে না হয়।
    """
    try:
        live_proxies_ref.listen(on_proxy_update)
    except Exception as e:
        print(f"[FIREBASE LISTENER ERROR] {e}")

# ব্যাকগ্রাউন্ড থ্রেডে লিসেনার শুরু করা
threading.Thread(target=start_firebase_listener, daemon=True).start()

# ======================
# YTDL OPTS
# ======================
BASE_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "nocheckcertificate": True,
    "extract_flat": "in_playlist",
    "socket_timeout": 10,  # ১০ সেকেন্ডের বেশি লোড নিলে পরের প্রক্সি ট্রাই করবে
    "retries": 1,
    "format": "best",
    "http_headers": {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
}

def get_local_proxies():
    """মেমোরি থেকে প্রক্সি লিস্ট সংগ্রহ করা"""
    with proxy_lock:
        return list(LOCAL_PROXIES)

def remove_bad_proxy_locally_and_firebase(proxy):
    """মেমোরি এবং Firebase থেকে নষ্ট হয়ে যাওয়া প্রক্সি রিমুভ করা"""
    with proxy_lock:
        if proxy in LOCAL_PROXIES:
            LOCAL_PROXIES.remove(proxy)
            # Firebase এ আপডেট করা
            live_proxies_ref.set(LOCAL_PROXIES)
            
            # Dead proxies তালিকায় যুক্ত করা
            current_dead = dead_proxies_ref.get() or []
            if isinstance(current_dead, dict):
                current_dead = list(current_dead.values())
            dead_proxies_ref.set(list(set(current_dead + [proxy])))

def check_proxy_status(proxy):
    try:
        proxies = {"http": proxy, "https": proxy}
        requests.head("https://www.google.com", proxies=proxies, timeout=5)
        return "LIVE"
    except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout):
        return "DEAD"
    except Exception as e:
        err = str(e).lower()
        if "dlp" in err or "403" in err or "429" in err:
            return "TEMP_ERR"  # DLP এররের জন্য Dead করবে না
        return "DEAD"

def auto_proxy_check_loop():
    while True:
        # Firebase না ডেকে মেমোরি থেকে ডাটা প্রসেস করা হবে
        live_proxies = get_local_proxies()
        if live_proxies:
            for proxy in live_proxies:
                status = check_proxy_status(proxy)
                if status == "DEAD":
                    remove_bad_proxy_locally_and_firebase(proxy)
        time.sleep(1800)

threading.Thread(target=auto_proxy_check_loop, daemon=True).start()

# ======================
# ROUTES
# ======================
@app.route("/")
def home():
    return "NextUpdateTube API Optimized with Realtime In-Memory Proxies."

@app.route("/get-link")
def playback():
    key = request.args.get("key")
    url = request.args.get("url")

    if key != API_KEY:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    if not url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    # Firebase রিড না করে পাইথনের মেমোরি থেকে সরাসরি নেওয়া হচ্ছে
    proxies = get_local_proxies()
    random.shuffle(proxies)

    last_error = None
    # সর্বোচ্চ ৫টি প্রক্সি ট্রাই করবে
    for proxy in proxies[:5]:
        ydl_opts = BASE_YDL_OPTS.copy()
        ydl_opts["proxy"] = proxy

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                playback_url = info.get("url")

            if playback_url:
                return jsonify({
                    "success": True, 
                    "playback": playback_url,
                    "title": info.get("title")
                })
        except Exception as e:
            last_error = str(e)
            lower_err = last_error.lower()
            if "proxyerror" in lower_err or "connection refused" in lower_err or "10061" in lower_err:
                remove_bad_proxy_locally_and_firebase(proxy)
            continue 

    return jsonify({"success": False, "error": "সব প্রক্সি ব্যর্থ হয়েছে অথবা ইউটিউব ব্লক করেছে। আবার চেষ্টা করুন।"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
