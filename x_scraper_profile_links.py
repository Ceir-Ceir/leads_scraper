
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# ---- CONFIG ----
GOOGLE_SHEET_NAME = "X Leads"
WORKSHEET_NAME = "Sheet1"
TWITTER_KEYWORDS = [
    "open to work",
    "seeking new opportunities",
    "actively looking",
    "job seeker",
    "available for hire",
    "freelance available",
    "looking for work",
    "unemployed"
]
NUM_SCROLLS = 8

# ---- GOOGLE SHEETS SETUP ----
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1o9aVy-1zw8ZSCokPna-OiiUMO3GowVnIY2A4L569FBM/edit").worksheet("Sheet1")
existing_data = sheet.get_all_records()
existing_urls = set(row["Profile URL"] for row in existing_data)

# ---- SCRAPER ----
new_rows = []

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="./twitter_profile",
        headless=False
    )
    page = browser.pages[0]

    page.goto("https://twitter.com/login")
    print("🛑 Please log in manually and press Enter here when you're done.")
    input()

    for keyword in TWITTER_KEYWORDS:
        print(f"🔍 Searching: {keyword}")
        search_url = f"https://twitter.com/search?q={keyword}&src=typed_query&f=user"
        page.goto(search_url)
        time.sleep(5)

        for _ in range(NUM_SCROLLS):
            page.mouse.wheel(0, 3000)
            time.sleep(2)

        profile_links = page.eval_on_selector_all(
            "a[href^='/']:not([href*='/status'])",
            """elements => Array.from(new Set(elements.map(el => el.href))).map(link => 'https://twitter.com' + link)"""
        )


        for link in profile_links:
            if link in existing_urls:
                continue
            username = link.split("/")[-1]
            new_rows.append([
                "",  # Full Name will be parsed in next script
                username,
                "X",
                "",  # Bio/Header placeholder
                link,
                keyword,
                datetime.today().strftime('%Y-%m-%d'),
                "FALSE",
                ""
            ])
            existing_urls.add(link)
            print(f"✅ Added {link}")

    browser.close()

# ---- WRITE TO SHEET ----
if new_rows:
    sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"✅ Added {len(new_rows)} new profile links to X Leads")
else:
    print("✅ No new profiles to add")
