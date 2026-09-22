#!/usr/bin/env python3
import requests
import sqlite3
import json
from pathlib import Path

API_KEY = "d7236eda6e9b10d53d53913a6217bf7a"
USER_ID = "11706974@N08"
url = "https://api.flickr.com/services/rest/"

# Connect to state.db
db_path = Path("/root/.flickr-autotagger/state.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all photos from state.db that have venice_status = 'done'
cur.execute("""
    SELECT flickr_id, title, ai_title, ai_description, scene_type, mood, 
           technique, location_guess, time_of_day, colors, objects
    FROM photos
    WHERE venice_status = 'done'
""")
venice_photos = {row["flickr_id"]: dict(row) for row in cur.fetchall()}
print(f"Loaded {len(venice_photos)} Venice-analyzed photos from DB.")

# Let's search Flickr for the user's photos sorted by interestingness
matched = []
page = 1
while len(matched) < 30 and page <= 5:
    params = {
        "method": "flickr.photos.search",
        "api_key": API_KEY,
        "user_id": USER_ID,
        "sort": "interestingness-desc",
        "extras": "views,date_taken,description,tags,url_m",
        "per_page": 500,
        "page": page,
        "format": "json",
        "nojsoncallback": 1
    }
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    if "photos" not in data or not data["photos"]["photo"]:
        break
    
    photos = data["photos"]["photo"]
    for p in photos:
        fid = str(p["id"])
        if fid in venice_photos:
            v = venice_photos[fid]
            # get predicted tags from db
            cur.execute("SELECT tag FROM predicted_tags WHERE photo_id = (SELECT id FROM photos WHERE flickr_id = ?)", (fid,))
            tags = [r[0] for r in cur.fetchall()]
            matched.append({
                "flickr_id": fid,
                "views": int(p.get("views", 0)),
                "flickr_url": f"https://www.flickr.com/photos/maximusmaximus/{fid}/",
                "original_title": p.get("title", ""),
                "ai_title": v.get("ai_title", ""),
                "ai_description": v.get("ai_description", ""),
                "scene_type": v.get("scene_type", ""),
                "mood": v.get("mood", ""),
                "technique": v.get("technique", ""),
                "location_guess": v.get("location_guess", ""),
                "tags": tags[:15]
            })
    page += 1

# Sort matched by views desc
matched.sort(key=lambda x: x["views"], reverse=True)
print(f"Found {len(matched)} matched popular photos with Venice metadata.")

for m in matched[:15]:
    print("\n" + "="*80)
    print(f"🔗 Flickr URL: {m['flickr_url']}")
    print(f"👀 Views: {m['views']}")
    print(f"Original Title: {m['original_title']}")
    print(f"✨ AI Title: {m['ai_title']}")
    print(f"📝 AI Description: {m['ai_description']}")
    print(f"📍 Location: {m['location_guess']}")
    print(f"🎨 Scene / Mood: {m['scene_type']} | {m['mood']}")
    print(f"🏷️ Tags: {', '.join(m['tags'])}")
