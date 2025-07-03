import time
import random
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# === CONFIG ===
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1mFQZXsx293j7S0qlybFSlCpm-n1F5oCSMUYjZus7cdg/edit?gid=0#gid=0"
WORKSHEET_NAME = "Sheet1"
PROFILE_DIR = "./linkedin_profile"

PEOPLE_KEYWORDS = [
    '"Open to work"', '"Available for freelance/consulting"',
    '"Recently laid off"', '"Available immediately"', '"Actively seeking"'
]

# --- GOOGLE SHEETS SETUP ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(GOOGLE_SHEET_URL).worksheet(WORKSHEET_NAME)
existing_data = sheet.get_all_records()
existing_urls = set(row["Profile URL"] for row in existing_data)

# === UTILS ===
def extract_username(profile_url):
    return profile_url.rstrip('/').split('/')[-1]

def prettify_username(username):
    # Convert "sanjoor-prem" -> "Sanjoor Prem"
    parts = username.replace('-', ' ').replace('.', ' ').split()
    return ' '.join(word.capitalize() for word in parts if word)

# === PEOPLE SEARCH (PAGINATED, ROBUST) ===
def scrape_people_search(page, keyword, known_urls, num_pages=10):
    today = datetime.today().strftime('%Y-%m-%d')
    quoted_keyword = keyword

    for page_num in range(1, num_pages + 1):
        print(f"Loading page {page_num} for {quoted_keyword}...")
        query = quoted_keyword.replace(' ', '%20')
        if page_num == 1:
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={query}&origin=GLOBAL_SEARCH_HEADER"
        else:
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={query}&origin=GLOBAL_SEARCH_HEADER&page={page_num}"
        try:
            page.goto(search_url, timeout=60000)
            time.sleep(5)
        except Exception as e:
            print(f"    [!] Timeout or navigation error on page {page_num} for '{keyword}': {e}")
            continue

        cards = page.query_selector_all('div.qzNyIFAzZJZBwmIgXqVzEZAKEhfUFiMYsI')
        print(f"  Found {len(cards)} cards on page {page_num} for {quoted_keyword}")
        if not cards:
            print("  No more results, stopping early.")
            break

        page_leads = []
        for card in cards:
            try:
                profile_link_el = card.query_selector('a[href*="/in/"]')
                if not profile_link_el:
                    continue
                profile_url = profile_link_el.get_attribute('href').split('?')[0]
                if profile_url in known_urls:
                    continue

                # === Full Name Logic ===
                # 1. Best: inner <span aria-hidden="true">
                name = ""
                name_span = profile_link_el.query_selector('span[aria-hidden="true"]')
                if name_span and name_span.inner_text().strip():
                    name = name_span.inner_text().strip()
                else:
                    # 2. Next: try .t-16 a
                    t16_a = card.query_selector('.t-16 a')
                    if t16_a and t16_a.inner_text().strip():
                        name = t16_a.inner_text().strip()
                    else:
                        # 3. Fallback: build from profile slug
                        username = extract_username(profile_url)
                        name = prettify_username(username)

                # === OTW logic ===
                img_el = card.query_selector('img')
                img_url = img_el.get_attribute('src') if img_el else ""
                otw = "Yes" if img_url and '/profile-framedphoto-' in img_url else "No"

                # === Bio/Header ===
                header_div = card.query_selector('div.RHIaxMYqSWhVYuOKZGwUdCILPpNyxMAnQ')
                bio_header = (header_div.inner_text() or "").strip() if header_div else ""

                lead = [
                    name,
                    extract_username(profile_url),
                    "LinkedIn",
                    bio_header,
                    otw,
                    profile_url,
                    keyword,
                    today,
                    "FALSE",
                    ""
                ]
                if name and profile_url:
                    page_leads.append(lead)
                    known_urls.add(profile_url)
                    print(f"    ✅ [People] {name} ({profile_url})")
                else:
                    print(f"    ⚠️  Skipped profile with missing name or URL: {profile_url}")

                # Sleep a bit after each profile
                time.sleep(random.uniform(0.5, 1.1))
            except Exception as ex:
                print(f"    [!] Error parsing people card: {ex}")

        # --- Update Google Sheet after each page ---
        if page_leads:
            try:
                sheet.append_rows(page_leads, value_input_option="USER_ENTERED")
                print(f"    💾 Added {len(page_leads)} new leads from page {page_num} to Google Sheet.")
            except Exception as sheet_err:
                print(f"    [!] Error writing to Google Sheet: {sheet_err}")

        # Human delay before next page
        wait_time = random.uniform(7, 12)
        print(f"    ⏳ Waiting {wait_time:.1f}s before next page...")
        time.sleep(wait_time)

# === MAIN ===
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=['--start-maximized']
        )
        page = browser.new_page()
        page.goto("https://www.linkedin.com/")
        print("🛑 Please log in to LinkedIn in the browser, then press ENTER here to continue.")
        input()
        print("✅ Continuing...")

        # PEOPLE SEARCH
        for keyword in PEOPLE_KEYWORDS:
            print(f"\n🔎 [People] Searching: {keyword}")
            scrape_people_search(page, keyword, existing_urls, num_pages=10)
            time.sleep(2)

        browser.close()

if __name__ == '__main__':
    main()
