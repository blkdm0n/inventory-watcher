"""
watcher.py — inventory watcher entry point.

Run with:  python watcher.py
Stop with: Ctrl+C
"""

# ── Standard-library imports ──────────────────────────────────────────────────
import os           # read environment variables loaded from .env
import time         # pause the script between scheduler ticks
import smtplib      # built-in Python library for sending email over SMTP
import logging      # write timestamped messages to the console
import argparse     # parse --once command-line flag
from email.message import EmailMessage  # builds a properly formatted email

# ── Third-party imports (installed via requirements.txt) ──────────────────────
import yaml                             # parse config.yaml
import schedule                         # run a function on a timer
from playwright.sync_api import sync_playwright  # headless browser for JS-rendered pages
from dotenv import load_dotenv          # load .env file into os.environ

# ── Logging setup ─────────────────────────────────────────────────────────────
# This makes every print-style message include a timestamp, e.g.:
#   2026-03-14 10:00:00 - INFO - Checking "Nike Shoes"...
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Load secrets from .env ────────────────────────────────────────────────────
# python-dotenv reads the .env file and stuffs each KEY=VALUE pair into the
# process's environment variables, so os.getenv() can access them.
load_dotenv()

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")   # sender email address
SMTP_PASS     = os.getenv("SMTP_PASS")   # sender email password / app password
NOTIFY_EMAIL  = os.getenv("NOTIFY_EMAIL")  # recipient email address

# ── Load config.yaml ──────────────────────────────────────────────────────────
# yaml.safe_load() turns the YAML file into a plain Python dictionary.
# "safe_load" is used instead of "load" to prevent executing arbitrary code
# that could be embedded in a malicious YAML file.
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

CHECK_INTERVAL = config.get("check_interval_minutes", 5)  # default: 5 minutes
ITEMS          = config.get("items", [])

# ── State tracking ────────────────────────────────────────────────────────────
# A Python "set" is like a list but with no duplicates and fast lookups.
# We store item names here after we've sent an alert so we don't email again
# until the item goes out of stock and comes back in.
already_notified = set()


# ── Functions ─────────────────────────────────────────────────────────────────

def check_stock(item: dict) -> bool:
    """
    Launch a headless Chromium browser, load the product page (executing JS),
    then return True if the item appears to be in stock.

    Supports two modes:
    - in_stock_selector + in_stock_text: in stock when element text IS found
    - out_of_stock_text: in stock when that text is NOT found anywhere on the page

    item: a dictionary with keys: name, url, and either
          (in_stock_selector + in_stock_text) or (out_of_stock_text)
    """
    name = item["name"]
    url  = item["url"]

    log.info(f'Checking "{name}" at {url}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, timeout=30000, wait_until="networkidle")

                # ── Inverted mode: look for an out-of-stock phrase ────────────
                if "out_of_stock_text" in item:
                    oos_text = item["out_of_stock_text"].strip().lower()
                    page_text = page.inner_text("body").lower()
                    if oos_text in page_text:
                        log.info(f'  "{name}" is out of stock (found "{item["out_of_stock_text"]}").')
                        return False
                    else:
                        log.info(f'  "{name}" is IN STOCK (out-of-stock text not found)!')
                        return True

                # ── Normal mode: look for an in-stock phrase ─────────────────
                selector = item["in_stock_selector"]
                target   = item["in_stock_text"].strip().lower()

                elements = page.query_selector_all(selector)

                if not elements:
                    log.info(f'  Selector "{selector}" not found on page — assuming out of stock.')
                    return False

                for el in elements:
                    if target in el.inner_text().strip().lower():
                        log.info(f'  "{name}" is IN STOCK!')
                        return True

                log.info(f'  "{name}" is out of stock.')
                return False
            finally:
                browser.close()

    except Exception as e:
        log.warning(f'  Could not check "{name}": {e}')
        return False


def send_email(item: dict) -> None:
    """
    Send an email alert saying the item is in stock.

    Uses Python's built-in smtplib — no third-party email service needed.
    """
    name = item["name"]
    url  = item["url"]

    # EmailMessage is a standard-library class that builds a properly formatted
    # email with headers (To, From, Subject) and a body.
    msg = EmailMessage()
    msg["Subject"] = f"[Inventory Watcher] {name} is IN STOCK!"
    msg["From"]    = SMTP_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.set_content(
        f"Good news! The item you're watching is back in stock.\n\n"
        f"Product : {name}\n"
        f"Link    : {url}\n\n"
        f"Go buy it before it's gone!\n\n"
        f"— Inventory Watcher"
    )

    try:
        # smtplib.SMTP opens a connection to the mail server.
        # SMTP_SSL would encrypt from the start; plain SMTP + starttls() upgrades
        # an unencrypted connection to an encrypted one (standard for port 587).
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()       # introduce ourselves to the server
            smtp.starttls()   # upgrade to encrypted connection
            smtp.login(SMTP_USER, SMTP_PASS)   # authenticate
            smtp.send_message(msg)             # send the email
        log.info(f'  Alert email sent to {NOTIFY_EMAIL} for "{name}".')

    except smtplib.SMTPException as e:
        log.error(f'  Failed to send email for "{name}": {e}')


def run_checks() -> None:
    """
    Loop through every item in config.yaml and check its stock status.
    Send an email the first time an item is found in stock.
    """
    for item in ITEMS:
        name = item["name"]
        in_stock = check_stock(item)

        if in_stock and name not in already_notified:
            # Item is in stock and we haven't emailed about it yet → send alert
            send_email(item)
            already_notified.add(name)  # remember we already notified for this item

        elif not in_stock and name in already_notified:
            # Item went back out of stock → reset so we'll email again next time
            log.info(f'  "{name}" is back out of stock. Will notify again if it returns.')
            already_notified.discard(name)


# ── Scheduler ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run checks once and exit (used by GitHub Actions).",
    )
    args = parser.parse_args()

    # Validate that credentials were loaded — fail early with a clear message
    # rather than crashing later with a confusing smtplib error.
    if not all([SMTP_USER, SMTP_PASS, NOTIFY_EMAIL]):
        raise SystemExit(
            "ERROR: SMTP_USER, SMTP_PASS, and NOTIFY_EMAIL must be set in your .env file."
        )

    if args.once:
        log.info("Running in one-shot mode (--once).")
        run_checks()
    else:
        log.info(f"Inventory watcher started. Checking every {CHECK_INTERVAL} minute(s).")
        log.info(f"Watching {len(ITEMS)} item(s): {[i['name'] for i in ITEMS]}")

        # Run once immediately on startup so you don't wait for the first interval.
        run_checks()

        # schedule.every(N).minutes.do(fn) registers fn to be called every N minutes.
        # It doesn't run it yet — it just adds it to a queue.
        schedule.every(CHECK_INTERVAL).minutes.do(run_checks)

        # This loop runs forever. schedule.run_pending() checks whether any scheduled
        # jobs are due and runs them if so. time.sleep(30) pauses for 30 seconds
        # between checks so we're not burning CPU in a tight loop.
        while True:
            schedule.run_pending()
            time.sleep(30)
