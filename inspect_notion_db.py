import os
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def get_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def inspect_database():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    print(f"Inspecting Database ID: {NOTION_DATABASE_ID}")
    
    with httpx.Client() as client:
        response = client.get(url, headers=get_headers())
        
        if response.status_code == 200:
            data = response.json()
            title = data.get("title", [{}])[0].get("text", {}).get("content", "Untitled")
            print(f"✅ Database Found: {title}")
            print("\n[Current Properties (Columns)]")
            properties = data.get("properties", {})
            for name, prop in properties.items():
                print(f"- Name: '{name}', Type: '{prop['type']}'")
                
            print("\n[Required Properties]")
            print("- '내용' (title)")
            print("- 'URL' (url)")
            print("- '날짜' (date)")
            print("- '분야' (select)")
            print("- '유형' (select)")
            print("- '언론사' (multi_select)")
        else:
            print(f"❌ Failed to access database. Status: {response.status_code}")
            print(f"Response: {response.text}")

if __name__ == "__main__":
    inspect_database()
