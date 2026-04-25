import asyncio
import json
import csv
import random
import re
import argparse
import os
from supabase import create_client
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


PAGE_LOAD_TIMEOUT  = 20_000
SCROLL_PAUSE_MIN   = 2.0
SCROLL_PAUSE_MAX   = 4.5
PROFILE_INTERVAL   = 15
HASHTAG_PAUSE_MIN  = 8
HASHTAG_PAUSE_MAX  = 14
DEFAULT_LIMIT      = 10

SA_HASHTAGS = [
    "smallbusinesssouthafrica",
    "southafricabusiness",
    "saentrepreneur",
    "johannesburgbusiness",
    "capetownbusiness",
    "durbanbusiness",
    "southafricastartups",
    "supportsmallbusinesssa",
    "madeinsouthafrica",
]

IG_USERNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._]{0,28}[a-zA-Z0-9])?$")
INVALID_USERNAME_PATTERNS = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|\d{4}|\boriginal\b|\baudio\b|\bvideo\b|\breels\b|\bstories\b|\bexplore\b"
    r"|\baccounts\b|\bdirect\b|\blive\b|\bshop\b)",
    re.IGNORECASE,
)

async def load_cookies(context, cookies_path: str):
    with open(cookies_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cookies = []
    for c in raw:
        cookie = {
            "name":   c.get("name"),
            "value":  c.get("value"),
            "domain": c.get("domain", ".instagram.com"),
            "path":   c.get("path", "/"),
        }
        same_site = c.get("sameSite") or c.get("same_site") or "Lax"
        cookie["sameSite"] = same_site if same_site in ("Strict", "Lax", "None") else "Lax"
        if c.get("expirationDate"):
            cookie["expires"] = int(c["expirationDate"])
        cookies.append(cookie)
    await context.add_cookies(cookies)
    print(f"🍪 Loaded {len(cookies)} cookies from {cookies_path}")

async def human_delay(min_s=SCROLL_PAUSE_MIN, max_s=SCROLL_PAUSE_MAX):
    await asyncio.sleep(random.uniform(min_s, max_s))

def is_valid_username(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if not IG_USERNAME_RE.match(text):
        return False
    if INVALID_USERNAME_PATTERNS.search(text):
        return False
    if " " in text or "•" in text:
        return False
    return True

def parse_count(text: str) -> int | None:
    if not text:
        return None
    text = text.strip().replace(",", "")
    for suffix, mult in [("M", 1_000_000), ("K", 1_000), ("B", 1_000_000_000)]:
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None

def extract_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text or "", re.IGNORECASE)
    return m.group() if m else None

def extract_phone(text: str) -> str | None:
    m = re.search(
        r"(\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}",
        text or "",
    )
    return m.group().strip() if m else None

def extract_country_code(phone: str | None) -> str | None:
    if not phone:
        return None
    m = re.match(r"(\+\d{1,3})", phone)
    return m.group(1) if m else None

async def get_logged_in_username(page) -> str | None:
    try:
        response = await page.request.get(
            "https://www.instagram.com/api/v1/accounts/current_user/?edit=true",
            headers={"x-ig-app-id": "936619743392459"},
        )
        if response.ok:
            data = await response.json()
            username = data.get("user", {}).get("username")
            if username:
                print(f"🔑 Logged in as: @{username} (will be excluded from results)")
                return username
    except Exception:
        pass
    return None

async def phase1_collect_all_links(page, hashtags: list[str], limit: int) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for i, hashtag in enumerate(hashtags, 1):
        print(f"\n  [{i}/{len(hashtags)}] Collecting links for #{hashtag}")
        links = await _collect_links_for_tag(page, hashtag, limit)
        results[hashtag] = links
        if i < len(hashtags):
            pause = random.uniform(HASHTAG_PAUSE_MIN, HASHTAG_PAUSE_MAX)
            print(f"  ⏸  Pausing {pause:.0f}s before next hashtag...")
            await asyncio.sleep(pause)
    total = sum(len(v) for v in results.values())
    print(f"\n✅ Phase 1 complete — {total} post links collected across {len(hashtags)} hashtags")
    return results

async def _collect_links_for_tag(page, hashtag: str, limit: int) -> list[str]:
    url = f"https://www.instagram.com/explore/tags/{hashtag}/"
    print(f"     🌐 {url}")
    try:
        await page.goto(url, timeout=PAGE_LOAD_TIMEOUT)
        await human_delay(3, 5)
    except Exception as e:
        print(f"     ❌ Failed to load hashtag page: {e}")
        return []

    for selector in [
        '[role="dialog"] button',
        'button:has-text("Not Now")',
        'button:has-text("Accept All")',
    ]:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2_000):
                await btn.click()
                await human_delay(1, 2)
        except Exception:
            pass

    links: list[str] = []
    seen: set[str] = set()
    scrolls = 0
    while len(links) < limit and scrolls < limit * 3:
        for a in await page.query_selector_all('a[href*="/p/"]'):
            href = await a.get_attribute("href")
            if href and "/p/" in href and href not in seen:
                seen.add(href)
                full = (f"https://www.instagram.com{href}" if href.startswith("/") else href)
                links.append(full)
        if len(links) >= limit:
            break
        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await human_delay()
        scrolls += 1

    links = links[:limit]
    print(f"     ✅ {len(links)} posts found")
    return links

async def get_username_from_post(page, post_url: str, logged_in_user: str | None) -> str | None:
    try:
        resp = await page.request.get(
            f"https://www.instagram.com/api/v1/oembed/?url={post_url}",
            headers={"x-ig-app-id": "936619743392459"},
        )
        if resp.ok:
            data = await resp.json()
            author = (data.get("author_name") or data.get("author_url", "").rstrip("/").split("/")[-1])
            if author and is_valid_username(author) and author != logged_in_user:
                return author
    except Exception:
        pass

    captured: list[str] = []
    async def handle_response(response):
        if captured:
            return
        if "/api/v1/media/" in response.url or "graphql/query" in response.url:
            try:
                body = await response.json()
                for m in re.findall(r'"username"\s*:\s*"([a-zA-Z0-9._]{1,30})"', json.dumps(body)):
                    if is_valid_username(m) and m != logged_in_user:
                        captured.append(m)
                        break
            except Exception:
                pass

    page.on("response", handle_response)
    try:
        await page.goto(post_url, timeout=PAGE_LOAD_TIMEOUT)
        await human_delay(2, 3)
    except Exception:
        pass
    finally:
        page.remove_listener("response", handle_response)

    if captured:
        return captured[0]

    try:
        result = await page.evaluate(f"""
            () => {{
                const skip = {json.dumps(logged_in_user)};
                const re = /^[a-zA-Z0-9][a-zA-Z0-9._]{{0,28}}[a-zA-Z0-9]?$/;
                for (const s of document.querySelectorAll('script')) {{
                    try {{
                        for (const m of s.textContent.matchAll(/"username":"([^"]+)"/g)) {{
                            if (re.test(m[1]) && m[1] !== skip) return m[1];
                        }}
                    }} catch(e) {{}}
                }}
                return null;
            }}
        """)
        if result and is_valid_username(result) and result != logged_in_user:
            return result
    except Exception:
        pass

    return None

async def scrape_profile(page, username: str, source_hashtag: str) -> dict:
    profile_url = f"https://www.instagram.com/{username}/"
    record = {
        "username":           username,
        "profile_link":       profile_url,
        "full_name":          None,
        "is_business":        False,
        "is_private":         False,
        "is_verified":        False,
        "category":           None,
        "bio":                None,
        "external_url":       None,
        "email":              None,
        "phone":              None,
        "phone_country_code": None,
        "city":               None,
        "address":            None,
        "posts_count":        None,
        "followers":          None,
        "following":          None,
        "source_hashtag":     source_hashtag,
        "scraped_at":         datetime.now().isoformat(),
    }

    try:
        response = await page.request.get(
            f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers={"x-ig-app-id": "936619743392459"},
        )
        if response.ok:
            data = await response.json()
            u = data.get("data", {}).get("user", {})
            if u:
                record["full_name"]    = u.get("full_name")
                record["bio"]          = u.get("biography")
                record["is_private"]   = u.get("is_private", False)
                record["is_verified"]  = u.get("is_verified", False)
                record["is_business"]  = u.get("is_business_account", False)
                record["category"]     = u.get("category_name") or u.get("business_category_name")
                record["posts_count"]  = u.get("edge_owner_to_timeline_media", {}).get("count")
                record["followers"]    = u.get("edge_followed_by", {}).get("count")
                record["following"]    = u.get("edge_follow", {}).get("count")
                record["email"]        = u.get("business_email") or u.get("public_email")
                record["phone"]        = u.get("business_phone_number") or u.get("public_phone_number")
                record["phone_country_code"] = (u.get("business_phone_country_code") or u.get("public_phone_country_code"))
                record["city"] = u.get("city_name") or u.get("location_name")

                bio_links = u.get("bio_links", [])
                record["external_url"] = (bio_links[0].get("url") if bio_links else u.get("external_url"))

                raw_addr = u.get("business_address_json") or u.get("address_json")
                if isinstance(raw_addr, str):
                    try:
                        addr = json.loads(raw_addr)
                        parts = [addr.get("street_address", ""), addr.get("zip_code", ""), addr.get("city_name", ""), addr.get("region_name", "")]
                        record["address"] = ", ".join(p for p in parts if p)
                        if not record["city"]:
                            record["city"] = addr.get("city_name")
                    except Exception:
                        record["address"] = raw_addr
                elif isinstance(raw_addr, dict):
                    parts = [raw_addr.get("street_address", ""), raw_addr.get("zip_code", ""), raw_addr.get("city_name", ""), raw_addr.get("region_name", "")]
                    record["address"] = ", ".join(p for p in parts if p)
                    if not record["city"]:
                        record["city"] = raw_addr.get("city_name")

                bio_text = record["bio"] or ""
                if not record["email"]:
                    record["email"] = extract_email(bio_text)
                if not record["phone"]:
                    record["phone"] = extract_phone(bio_text)
                    record["phone_country_code"] = extract_country_code(record["phone"])

                print(f"    ✅ API data OK")
                return record
    except Exception as e:
        print(f"    ⚠️  API failed ({e}), falling back to DOM")

    try:
        await page.goto(profile_url, timeout=PAGE_LOAD_TIMEOUT)
        await human_delay(2, 4)

        for sel in ["header h1", "header h2"]:
            el = await page.query_selector(sel)
            if el:
                record["full_name"] = (await el.inner_text()).strip()
                break

        for sel in ['div[data-testid="user-bio"]', 'header section > div > span']:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    record["bio"] = text
                    break

        for sel in ['a[rel*="nofollow"][href*="http"]', 'header a[target="_blank"]']:
            el = await page.query_selector(sel)
            if el:
                record["external_url"] = await el.get_attribute("href")
                break

        for el in await page.query_selector_all("header ul li"):
            text = (await el.inner_text()).strip().lower()
            num = re.search(r"([\d,.]+[kmb]?)", text, re.IGNORECASE)
            if num:
                val = parse_count(num.group(1))
                if "post" in text:
                    record["posts_count"] = val
                elif "follower" in text:
                    record["followers"] = val
                elif "following" in text:
                    record["following"] = val

        for sel in ['div[data-testid="user-category"]', 'header section span']:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) < 60 and "@" not in text and "#" not in text:
                    record["category"]    = text
                    record["is_business"] = True
                    break

        record["is_private"]  = bool(await page.query_selector('[data-testid="private-account-lock"]'))
        record["is_verified"] = bool(await page.query_selector('[aria-label="Verified"]'))

        bio_text = record["bio"] or ""
        if not record["email"]:
            record["email"] = extract_email(bio_text)
        if not record["phone"]:
            record["phone"] = extract_phone(bio_text)
            record["phone_country_code"] = extract_country_code(record["phone"])

    except PlaywrightTimeout:
        print(f"    ⏱ Timeout on @{username}")
    except Exception as e:
        print(f"    ❌ DOM error for @{username}: {e}")

    return record

FIELDNAMES = [
    "username", "profile_link", "full_name",
    "is_business", "is_private", "is_verified",
    "category", "bio", "external_url",
    "email", "phone", "phone_country_code",
    "city", "address",
    "posts_count", "followers", "following",
    "source_hashtag", "scraped_at",
]

def save_results(results: list[dict], stem: str):
    if not results:
        return
        
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Supabase credentials missing. Data not saved.")
        return
        
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    try:
        # Insert all scraped profiles directly into the Supabase database
        response = supabase.table("leads").insert(results).execute()
        print(f"✅ Saved {len(results)} leads to Supabase!")
    except Exception as e:
        print(f"❌ Failed to save to Supabase: {e}")

def print_summary(results: list[dict], stem: str):
    print(f"\n{'='*58}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*58}")
    print(f"  Total profiles    : {len(results)}")
    print(f"  Business accounts : {sum(1 for r in results if r.get('is_business'))}")
    print(f"  Private accounts  : {sum(1 for r in results if r.get('is_private'))}")
    print(f"  Verified          : {sum(1 for r in results if r.get('is_verified'))}")
    print(f"  Has email         : {sum(1 for r in results if r.get('email'))}")
    print(f"  Has phone         : {sum(1 for r in results if r.get('phone'))}")
    print(f"  Has city          : {sum(1 for r in results if r.get('city'))}")
    print(f"  Has address       : {sum(1 for r in results if r.get('address'))}")
    followers = [r["followers"] for r in results if r.get("followers") is not None]
    if followers:
        print(f"\n  Avg followers     : {int(sum(followers)/len(followers)):,}")
        print(f"  Top followers     : {max(followers):,}")
    print(f"\n  Output → output/{stem}.(json|csv)")
    print(f"{'='*58}\n")

async def main_wrapper(args):
    stem = f"ig_sa_profiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\n📸 Instagram SA Business Profile Scraper")
    print(f"   Hashtags        : {len(args.hashtags)}")
    print(f"   Posts per tag   : {args.limit}")
    print(f"   Profile interval: {PROFILE_INTERVAL}s")
    print(f"   Output          : output/{stem}.*\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-ZA",
            timezone_id="Africa/Johannesburg",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        cookies_path = Path(args.cookies)
        if cookies_path.exists():
            await load_cookies(context, str(cookies_path))
        else:
            print(f"⚠️  {args.cookies} not found — running without auth (limited data)\n")

        logged_in_user = await get_logged_in_username(page)

        print(f"\n{'─'*50}")
        print(f"  PHASE 1 — Collecting post links")
        print(f"{'─'*50}")
        hashtag_links = await phase1_collect_all_links(page, args.hashtags, args.limit)

        all_posts: list[tuple[str, str]] = []
        for hashtag, links in hashtag_links.items():
            for link in links:
                all_posts.append((link, hashtag))

        print(f"\n{'─'*50}")
        print(f"  PHASE 2 — Extracting usernames & scraping profiles")
        print(f"  Total posts to process: {len(all_posts)}")
        print(f"{'─'*50}")

        all_profiles: list[dict] = []
        seen_usernames: set[str] = set()

        if logged_in_user:
            seen_usernames.add(logged_in_user)

        for i, (post_url, source_hashtag) in enumerate(all_posts, 1):
            print(f"\n[{i}/{len(all_posts)}] Post from #{source_hashtag}")
            print(f"  {post_url}")

            username = await get_username_from_post(page, post_url, logged_in_user)

            if not username:
                print(f"  ⚠️  Could not extract a valid username — skipping")
                continue

            if username in seen_usernames:
                print(f"  @{username} already scraped — skipping")
                continue

            seen_usernames.add(username)

            print(f"  👤 @{username} — waiting {PROFILE_INTERVAL}s before scraping...")
            await asyncio.sleep(PROFILE_INTERVAL)

            profile = await scrape_profile(page, username, source_hashtag)
            all_profiles.append(profile)
            save_results(all_profiles, stem)

            flags = []
            if profile.get("is_business"):  flags.append("business")
            if profile.get("is_private"):   flags.append("private")
            if profile.get("is_verified"):  flags.append("verified")
            if profile.get("email"):        flags.append(f"✉ {profile['email']}")
            if profile.get("phone"):        flags.append(f"📞 {profile['phone']}")
            if profile.get("city"):         flags.append(f"📍 {profile['city']}")
            print(f"  📋 {', '.join(flags) if flags else 'basic profile'}")

        await browser.close()

    save_results(all_profiles, stem)
    print_summary(all_profiles, stem)

    return {
    "count": len(all_profiles),
    "file": f"output/{stem}.csv"
}

async def start_scraper(hashtags, cookies_path, limit=10, headless=True):
    class Args:
        pass
    args = Args()
    args.hashtags = hashtags
    args.limit = limit
    args.cookies = cookies_path
    args.headless = headless
    return await main_wrapper(args)