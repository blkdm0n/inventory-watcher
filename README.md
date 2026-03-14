# inventory-watcher

A Python script that checks a product page on a schedule and emails you the moment it comes back in stock.

**How it works:** Every N minutes the script fetches the product page, finds the element you pointed it to (e.g. an "Add to Cart" button), and checks the text. If the text matches your configured in-stock value it sends you an email — once — and waits until it goes out of stock again before alerting you a second time.

---

## Project structure

```
inventory-watcher/
├── watcher.py          # main script — run this
├── config.yaml         # which products to watch + check interval
├── sample.env          # template for your email credentials
├── requirements.txt    # Python dependencies
└── .gitignore          # keeps your real .env out of Git
```

---

## Prerequisites

- Python 3.8 or newer
- A Gmail account (or any SMTP-capable email account)
- If using Gmail with 2-factor auth (recommended): an [App Password](https://myaccount.google.com/apppasswords)

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

The second command downloads the headless Chromium browser that Playwright uses to render JS-heavy pages (like Wix sites).

### 2. Create your `.env` file

Copy the template and fill in your real email credentials:

```bash
cp sample.env .env
```

Then open `.env` and replace the placeholder values:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-app-password-here
NOTIFY_EMAIL=you@gmail.com
```

> **Gmail tip:** If you have 2-Step Verification enabled, you cannot use your normal password here.
> Go to **Google Account → Security → 2-Step Verification → App passwords** and generate one.

### 3. Configure the products you want to watch

Open `config.yaml` and replace the example item with your real product:

```yaml
check_interval_minutes: 5

items:
  - name: "Nike Air Max (Size 10)"
    url: "https://www.nike.com/..."
    in_stock_selector: ".add-to-cart-button"
    in_stock_text: "Add to Cart"
```

**How to find `in_stock_selector` for your product:**
1. Open the product page in Chrome or Firefox
2. Right-click the "Add to Cart" button (or whatever shows stock status)
3. Click **Inspect**
4. In the dev tools panel, right-click the highlighted HTML element
5. Choose **Copy → Copy selector**
6. Paste it as the value of `in_stock_selector`

`in_stock_text` is the exact text that element shows when the item **is** in stock.

### 4. Add `.env` to `.gitignore`

Make sure your real credentials never get committed to Git:

```bash
echo ".env" >> .gitignore
```

---

## Running the watcher

```bash
python watcher.py
```

You'll see timestamped log output in the terminal:

```
2026-03-14 10:00:00 - INFO - Inventory watcher started. Checking every 5 minute(s).
2026-03-14 10:00:00 - INFO - Checking "Nike Air Max (Size 10)" at https://...
2026-03-14 10:00:01 - INFO -   "Nike Air Max (Size 10)" is out of stock.
2026-03-14 10:05:00 - INFO - Checking "Nike Air Max (Size 10)" at https://...
2026-03-14 10:05:01 - INFO -   "Nike Air Max (Size 10)" is IN STOCK!
2026-03-14 10:05:02 - INFO -   Alert email sent to you@gmail.com for "Nike Air Max (Size 10)".
```

Stop the script at any time with **Ctrl+C**.

---

## Keeping it running in the background

If you close the terminal the script stops. To keep it running:

**On Linux/macOS** — use `nohup`:
```bash
nohup python watcher.py > watcher.log 2>&1 &
```

**On Windows** — use Task Scheduler, or run in Windows Terminal and leave it open.

---

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `SMTP_USER, SMTP_PASS... must be set` | `.env` file missing or not filled in |
| `SMTPAuthenticationError` | Wrong password, or Gmail needs an App Password |
| Selector not found on page | Website changed its HTML — re-copy the selector from the browser |
| No email even though in stock | Check `in_stock_text` matches exactly what the button says |
| 403 / blocked by website | Site is blocking the bot; try increasing `check_interval_minutes` |
| `playwright install` not run | Run `playwright install chromium` before starting the watcher |

