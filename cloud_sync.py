# -*- coding: utf-8 -*-
"""
Enterprise Cloud Persistence, Multi-Channel Sync & Async Email Notification Engine
Supports:
1. Local JSON & File Storage (data/rfqs.json, data/settings.json, data/uploads/)
2. GitHub Dedicated Branch ('cloud-backup') Auto-Backup & Startup Auto-Restore with [skip ci]
3. External PostgreSQL Database Sync (DATABASE_URL) including binary attachment backup
4. Google Sheets Webhook Sync (GOOGLE_SHEETS_WEBHOOK_URL)
5. Asynchronous SMTP Email Notification (Admin alert with attachments + Customer confirmation)
"""

import os
import json
import time
import base64
import smtplib
import threading
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
TTS_CACHE_DIR = os.path.join(DATA_DIR, "tts_cache")
RFQS_FILE = os.path.join(DATA_DIR, "rfqs.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

_file_lock = threading.RLock()

DEFAULT_SETTINGS = {
    "smtp_enabled": False,
    "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    "smtp_use_tls": True,
    "smtp_user": os.environ.get("SMTP_USER", ""),
    "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
    "smtp_sender_name": os.environ.get("SMTP_SENDER_NAME", "錸億精密工業 智慧詢價系統"),
    "admin_notify_email": os.environ.get("ADMIN_NOTIFY_EMAIL", "laiyi.huang@msa.hinet.net"),
    "github_backup_enabled": bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPO")),
    "github_token": os.environ.get("GITHUB_TOKEN", ""),
    "github_repo": os.environ.get("GITHUB_REPO", ""),  # e.g. "username/laiyi-web"
    "github_branch": os.environ.get("GITHUB_BACKUP_BRANCH", "cloud-backup"),
    "database_url": os.environ.get("DATABASE_URL", ""),
    "google_sheets_webhook": os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL", ""),
    "keep_alive_url": os.environ.get("KEEP_ALIVE_URL", ""),
    "last_backup_time": None,
    "last_backup_status": "Ready (Local + Cloud Sync Armed)",
    "last_restore_time": None
}

SAMPLE_RFQS = [
    {
        "id": "LY-20261110-0001",
        "created_at": "2026-11-10 09:30:15",
        "updated_at": "2026-11-10 10:15:00",
        "status": "quoted",
        "company": "南科半導體設備股份有限公司 (Tainan Semicon Equipment Corp.)",
        "contact_name": "陳建宏 研發部副理",
        "country": "TAIWAN (台灣)",
        "phone": "06-505-8899 #302",
        "email": "jh.chen@example-semicon.com.tw",
        "instant_messenger": "LINE: jhchen_semi",
        "target_delivery": "2026-11-28",
        "customer_notes": "大型自動化晶圓移載機台底座與真空腔體法蘭，需提供東京精密 3D CMM 三次元量測報告與鋁合金 6061-T651 原廠材質證明。",
        "admin_notes": "已由廠長評估 WELE NB-2150 龍門銑床排程，預計 10 個工作天交貨，已提供正式報價單 #Q20261110-01。",
        "items": [
            {
                "sku": "LY-GANTRY-2150A",
                "name": "半導體與面板設備大型龍門銑床精密結構底座",
                "material": "鋁合金 6061-T651",
                "dimensions": "1850 × 1200 × 180 mm",
                "tolerance": "±0.005 mm",
                "surface": "本色陽極處理",
                "qty": 2,
                "unit_Note": "附 3D CMM 報告"
            },
            {
                "sku": "LY-SEMI-VAC316",
                "name": "半導體晶圓傳輸設備 SUS316L 不鏽鋼真空腔體法蘭",
                "material": "不鏽鋼 SUS316L",
                "dimensions": "420 × 420 × 95 mm",
                "tolerance": "±0.005 mm",
                "surface": "無塵室電解拋光 (EP)",
                "qty": 6,
                "unit_Note": "O-Ring 密封面無刀痕"
            }
        ],
        "attachments": [],
        "email_status": "Demo Record (Pre-loaded)",
        "lang": "zh-TW"
    },
    {
        "id": "LY-20261110-0002",
        "created_at": "2026-11-10 14:12:40",
        "updated_at": "2026-11-10 14:12:40",
        "status": "pending",
        "company": "Aether AI Server Technologies Inc.",
        "contact_name": "Michael Vance (Sr. Mechanical Engineer)",
        "country": "UNITED STATES",
        "phone": "+1-408-555-0192",
        "email": "m.vance@example-aether-ai.com",
        "instant_messenger": "WhatsApp: +14085550192",
        "target_delivery": "2026-12-05",
        "customer_notes": "Need 25 sets of AI Server Liquid-Cooling Manifolds in 7075-T6 with Ra 0.4um sealing grooves. Please include discounted DHL Express shipping to San Jose, CA.",
        "admin_notes": "待確認 DHL 棧板折扣運費與 AQ-1265 雙機排程。",
        "items": [
            {
                "sku": "LY-AISRV-7075B",
                "name": "AI Server Liquid-Cooling Manifold & High-Precision Thermal Chassis",
                "material": "Aluminum 7075-T6",
                "dimensions": "680 × 450 × 65 mm",
                "tolerance": "±0.005 mm",
                "surface": "Hard Anodizing + Chromate",
                "qty": 25,
                "unit_Note": "100% Leak & CMM Test"
            }
        ],
        "attachments": [],
        "email_status": "Demo Record (Pre-loaded)",
        "lang": "en"
    }
]


def load_settings() -> dict:
    with _file_lock:
        if not os.path.exists(SETTINGS_FILE):
            save_settings(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            # Env var overrides if explicitly set in cloud environment and empty in file
            for env_key, setting_key in [
                ("GITHUB_TOKEN", "github_token"),
                ("GITHUB_REPO", "github_repo"),
                ("DATABASE_URL", "database_url"),
                ("GOOGLE_SHEETS_WEBHOOK_URL", "google_sheets_webhook"),
                ("KEEP_ALIVE_URL", "keep_alive_url")
            ]:
                if os.environ.get(env_key) and not merged.get(setting_key):
                    merged[setting_key] = os.environ.get(env_key)
            return merged
        except Exception:
            return dict(DEFAULT_SETTINGS)


def save_settings(new_settings: dict) -> dict:
    with _file_lock:
        current = dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    current.update(json.load(f))
            except Exception:
                pass
        current.update(new_settings)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return current


def load_rfqs() -> list:
    with _file_lock:
        if not os.path.exists(RFQS_FILE):
            with open(RFQS_FILE, "w", encoding="utf-8") as f:
                json.dump(SAMPLE_RFQS, f, ensure_ascii=False, indent=2)
            return list(SAMPLE_RFQS)
        try:
            with open(RFQS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else list(SAMPLE_RFQS)
        except Exception:
            return list(SAMPLE_RFQS)


def save_rfqs(rfqs: list, trigger_cloud: bool = True, new_attachment_paths: list = None):
    with _file_lock:
        with open(RFQS_FILE, "w", encoding="utf-8") as f:
            json.dump(rfqs, f, ensure_ascii=False, indent=2)
    if trigger_cloud:
        threading.Thread(
            target=_background_cloud_sync,
            args=(rfqs, new_attachment_paths or []),
            daemon=True
        ).start()


# ==============================================================================
# PostgreSQL Persistence Sync (Optional / Cloud Database)
# ==============================================================================
def _sync_to_postgres(rfqs: list, settings: dict, attachment_paths: list = None):
    db_url = settings.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return False, "No DATABASE_URL configured"
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=8)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS laiyi_kv_store (
                key TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS laiyi_uploaded_files (
                filename TEXT PRIMARY KEY,
                content_b64 TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            INSERT INTO laiyi_kv_store (key, payload, updated_at)
            VALUES ('rfqs', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = CURRENT_TIMESTAMP;
        """, (json.dumps(rfqs, ensure_ascii=False),))

        safe_settings = dict(settings)
        cur.execute("""
            INSERT INTO laiyi_kv_store (key, payload, updated_at)
            VALUES ('settings', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = CURRENT_TIMESTAMP;
        """, (json.dumps(safe_settings, ensure_ascii=False),))

        for path in (attachment_paths or []):
            if os.path.exists(path):
                fname = os.path.basename(path)
                with open(path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")
                cur.execute("""
                    INSERT INTO laiyi_uploaded_files (filename, content_b64, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (filename) DO UPDATE SET content_b64 = EXCLUDED.content_b64, updated_at = CURRENT_TIMESTAMP;
                """, (fname, b64_data))

        conn.commit()
        cur.close()
        conn.close()
        return True, "PostgreSQL synced"
    except Exception as e:
        return False, f"PostgreSQL sync error: {e}"


def _restore_from_postgres(settings: dict) -> bool:
    db_url = settings.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return False
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=8)
        cur = conn.cursor()
        cur.execute("SELECT payload FROM laiyi_kv_store WHERE key = 'rfqs';")
        row = cur.fetchone()
        if row and row[0]:
            rfqs_data = row[0] if isinstance(row[0], list) else json.loads(row[0])
            with _file_lock:
                with open(RFQS_FILE, "w", encoding="utf-8") as f:
                    json.dump(rfqs_data, f, ensure_ascii=False, indent=2)

        cur.execute("SELECT filename, content_b64 FROM laiyi_uploaded_files;")
        for fname, b64_data in cur.fetchall():
            dest = os.path.join(UPLOADS_DIR, os.path.basename(fname))
            if not os.path.exists(dest):
                with open(dest, "wb") as f:
                    f.write(base64.b64decode(b64_data))
        cur.close()
        conn.close()
        return True
    except Exception:
        return False


# ==============================================================================
# GitHub Dedicated Branch ('cloud-backup') Auto-Backup & Startup Auto-Restore
# ==============================================================================
def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LaiYi-Enterprise-Cloud-Backup"
    }


def _ensure_github_branch(repo: str, branch: str, token: str) -> bool:
    headers = _github_headers(token)
    r = requests.get(f"https://api.github.com/repos/{repo}/branches/{branch}", headers=headers, timeout=10)
    if r.status_code == 200:
        return True
    # Get default branch SHA to create `cloud-backup` branch
    repo_info = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=10)
    if repo_info.status_code != 200:
        return False
    default_branch = repo_info.json().get("default_branch", "main")
    ref_resp = requests.get(f"https://api.github.com/repos/{repo}/git/ref/heads/{default_branch}", headers=headers, timeout=10)
    if ref_resp.status_code != 200:
        return False
    sha = ref_resp.json()["object"]["sha"]
    create_resp = requests.post(
        f"https://api.github.com/repos/{repo}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{branch}", "sha": sha},
        timeout=10
    )
    return create_resp.status_code in (200, 201)


def _github_put_file(repo: str, branch: str, token: str, remote_path: str, raw_bytes: bytes, message: str) -> bool:
    headers = _github_headers(token)
    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    get_resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
    payload = {
        "message": f"{message} [skip ci]",
        "content": base64.b64encode(raw_bytes).decode("ascii"),
        "branch": branch
    }
    if get_resp.status_code == 200:
        payload["sha"] = get_resp.json().get("sha")
    put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
    return put_resp.status_code in (200, 201)


def backup_to_github_branch(rfqs: list = None, attachment_paths: list = None) -> tuple:
    """Push rfqs.json, settings.json, and uploaded attachments to GitHub `cloud-backup` branch with [skip ci]."""
    settings = load_settings()
    token = (settings.get("github_token") or os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = (settings.get("github_repo") or os.environ.get("GITHUB_REPO") or "").strip()
    branch = (settings.get("github_branch") or "cloud-backup").strip()

    if not token or not repo:
        return False, "GitHub Token or Repo not configured"

    try:
        if not _ensure_github_branch(repo, branch, token):
            return False, f"Unable to access or create branch '{branch}' on {repo}"

        if rfqs is None:
            rfqs = load_rfqs()

        rfqs_bytes = json.dumps(rfqs, ensure_ascii=False, indent=2).encode("utf-8")
        ok1 = _github_put_file(
            repo, branch, token,
            "backup/rfqs.json",
            rfqs_bytes,
            "chore(backup): sync RFQ records"
        )

        # Redact sensitive tokens before pushing settings snapshot if desired, or keep encrypted
        settings_copy = dict(settings)
        settings_bytes = json.dumps(settings_copy, ensure_ascii=False, indent=2).encode("utf-8")
        _github_put_file(
            repo, branch, token,
            "backup/settings.json",
            settings_bytes,
            "chore(backup): sync CRM settings"
        )

        # Upload new attachment files
        files_to_sync = attachment_paths if attachment_paths is not None else [
            os.path.join(UPLOADS_DIR, fn) for fn in os.listdir(UPLOADS_DIR)
            if os.path.isfile(os.path.join(UPLOADS_DIR, fn))
        ]
        for fpath in files_to_sync:
            if os.path.exists(fpath) and os.path.getsize(fpath) < 20 * 1024 * 1024:
                fname = os.path.basename(fpath)
                with open(fpath, "rb") as f:
                    _github_put_file(
                        repo, branch, token,
                        f"backup/uploads/{fname}",
                        f.read(),
                        f"chore(backup): sync customer attachment {fname}"
                    )

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_settings({
            "last_backup_time": now_str,
            "last_backup_status": f"Success -> GitHub ({repo}@{branch}) [skip ci]" if ok1 else "Partial sync"
        })
        return ok1, f"Backed up to {repo}@{branch} at {now_str}"
    except Exception as e:
        err_msg = f"GitHub backup error: {e}"
        save_settings({"last_backup_status": err_msg})
        return False, err_msg


def restore_from_github_branch() -> tuple:
    """Restore rfqs.json and uploaded files from GitHub `cloud-backup` branch."""
    settings = load_settings()
    token = (settings.get("github_token") or os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = (settings.get("github_repo") or os.environ.get("GITHUB_REPO") or "").strip()
    branch = (settings.get("github_branch") or "cloud-backup").strip()

    if not token or not repo:
        return False, "GitHub Token or Repo not configured"

    headers = _github_headers(token)
    try:
        url = f"https://api.github.com/repos/{repo}/contents/backup/rfqs.json"
        r = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
        if r.status_code != 200:
            return False, f"No backup/rfqs.json found on {repo}@{branch}"

        content_b64 = r.json().get("content", "")
        raw_json = base64.b64decode(content_b64).decode("utf-8")
        rfqs_data = json.loads(raw_json)
        if isinstance(rfqs_data, list):
            with _file_lock:
                with open(RFQS_FILE, "w", encoding="utf-8") as f:
                    json.dump(rfqs_data, f, ensure_ascii=False, indent=2)

        # Also check backup/uploads directory
        up_url = f"https://api.github.com/repos/{repo}/contents/backup/uploads"
        up_r = requests.get(up_url, headers=headers, params={"ref": branch}, timeout=10)
        restored_files = 0
        if up_r.status_code == 200 and isinstance(up_r.json(), list):
            for item in up_r.json():
                fname = item.get("name")
                if not fname:
                    continue
                local_dest = os.path.join(UPLOADS_DIR, os.path.basename(fname))
                if not os.path.exists(local_dest):
                    file_r = requests.get(item.get("url"), headers=headers, timeout=15)
                    if file_r.status_code == 200 and file_r.json().get("content"):
                        with open(local_dest, "wb") as f:
                            f.write(base64.b64decode(file_r.json()["content"]))
                        restored_files += 1

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_settings({
            "last_restore_time": now_str,
            "last_backup_status": f"Restored {len(rfqs_data)} RFQs & {restored_files} files from {repo}@{branch}"
        })
        return True, f"Restored {len(rfqs_data)} RFQs & {restored_files} attachments from {repo}@{branch}"
    except Exception as e:
        return False, f"GitHub restore error: {e}"


def restore_from_cloud_on_startup():
    """Called once when Flask starts to automatically recover data after cloud container restart/redeploy."""
    settings = load_settings()
    pg_ok = _restore_from_postgres(settings)
    gh_ok, gh_msg = restore_from_github_branch()
    # Ensure local file is initialized if neither cloud source had prior state
    load_rfqs()
    return {"postgres_restored": pg_ok, "github_restored": gh_ok, "github_message": gh_msg}


def _sync_to_google_sheets(latest_rfq: dict, settings: dict):
    webhook = (settings.get("google_sheets_webhook") or os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL") or "").strip()
    if not webhook:
        return False
    try:
        requests.post(webhook, json=latest_rfq, timeout=10)
        return True
    except Exception:
        return False


def _background_cloud_sync(rfqs: list, attachment_paths: list):
    settings = load_settings()
    _sync_to_postgres(rfqs, settings, attachment_paths)
    if settings.get("github_backup_enabled") or (settings.get("github_token") and settings.get("github_repo")):
        backup_to_github_branch(rfqs, attachment_paths)
    if rfqs:
        _sync_to_google_sheets(rfqs[0], settings)


# ==============================================================================
# Automated Asynchronous Email Notification (Admin with Attachments + Customer)
# ==============================================================================
def _build_admin_email_html(rfq: dict) -> str:
    items_rows = ""
    for idx, item in enumerate(rfq.get("items", []), start=1):
        items_rows += f"""
        <tr>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;text-align:center;">{idx}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;font-weight:600;">{item.get('name', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;">{item.get('material', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;">{item.get('dimensions', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;">{item.get('tolerance', '±0.005 mm')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;text-align:right;font-weight:700;color:#0284c7;">{item.get('qty', 1)}</td>
        </tr>
        """
    return f"""
    <div style="font-family:'Microsoft JhengHei',Arial,sans-serif;max-width:720px;margin:0 auto;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
        <div style="background:#0f172a;color:#f8fafc;padding:20px 24px;border-bottom:4px solid #0ea5e9;">
            <h2 style="margin:0;font-size:20px;">【錸億精密工業】新線上詢價單通知 ({rfq.get('id')})</h2>
            <p style="margin:6px 0 0;color:#94a3b8;font-size:13px;">提交時間：{rfq.get('created_at')} ｜ 語系：{rfq.get('lang', 'zh-TW')}</p>
        </div>
        <div style="padding:24px;background:#ffffff;color:#1e293b;">
            <h3 style="margin-top:0;color:#0f172a;border-left:4px solid #0ea5e9;padding-left:10px;">客戶聯絡資訊</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;">
                <tr><td style="padding:6px 0;color:#64748b;width:130px;">公司名稱：</td><td style="font-weight:600;">{rfq.get('company', '-')}</td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">聯絡人姓名：</td><td>{rfq.get('contact_name', '-')}</td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">國家/地區：</td><td>{rfq.get('country', 'TAIWAN')}</td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">聯絡電話：</td><td>{rfq.get('phone', '-')}</td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">電子信箱：</td><td><a href="mailto:{rfq.get('email', '')}">{rfq.get('email', '-')}</a></td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">通訊軟體：</td><td>{rfq.get('instant_messenger', '-')}</td></tr>
                <tr><td style="padding:6px 0;color:#64748b;">期望交期：</td><td>{rfq.get('target_delivery', '未指定')}</td></tr>
            </table>

            <h3 style="color:#0f172a;border-left:4px solid #0ea5e9;padding-left:10px;">詢價品項明細 ({len(rfq.get('items', []))} 項)</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:13px;">
                <thead>
                    <tr style="background:#f1f5f9;color:#334155;">
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;">#</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">品項 / 零件名稱</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">材質規格</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">尺寸 (mm)</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">精度需求</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:right;">數量</th>
                    </tr>
                </thead>
                <tbody>{items_rows}</tbody>
            </table>

            <h3 style="color:#0f172a;border-left:4px solid #0ea5e9;padding-left:10px;">客戶專案需求與備註</h3>
            <div style="background:#f8fafc;padding:14px;border-radius:6px;border:1px solid #e2e8f0;white-space:pre-wrap;font-size:14px;">{rfq.get('customer_notes') or '無額外備註'}</div>
            <p style="margin-top:16px;font-size:13px;color:#475569;">上傳附件數量：{len(rfq.get('attachments', []))} 個檔案（已隨信附上或可登入 CRM 後台下載）</p>
        </div>
    </div>
    """


def _build_customer_email_html(rfq: dict) -> str:
    items_rows = ""
    for idx, item in enumerate(rfq.get("items", []), start=1):
        items_rows += f"""
        <tr>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;text-align:center;">{idx}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;font-weight:600;">{item.get('name', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;">{item.get('material', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;">{item.get('dimensions', '-')}</td>
            <td style="padding:8px 12px;border:1px solid #cbd5e1;text-align:right;">{item.get('qty', 1)}</td>
        </tr>
        """
    return f"""
    <div style="font-family:'Microsoft JhengHei',Arial,sans-serif;max-width:680px;margin:0 auto;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
        <div style="background:#0f172a;color:#f8fafc;padding:20px 24px;border-bottom:4px solid #f59e0b;">
            <h2 style="margin:0;font-size:19px;">錸億精密工業有限公司 (LAI YI Precision Industrial)</h2>
            <p style="margin:6px 0 0;color:#cbd5e1;font-size:14px;">線上詢價確認通知 ｜ RFQ Receipt Confirmation: <strong>{rfq.get('id')}</strong></p>
        </div>
        <div style="padding:24px;background:#ffffff;color:#1e293b;line-height:1.6;">
            <p>親愛的 <strong>{rfq.get('contact_name')} ({rfq.get('company')})</strong> 您好：</p>
            <p>感謝您聯繫<strong>錸億精密工業有限公司</strong>！我們已成功收到您的線上詢價單（單號：<strong>{rfq.get('id')}</strong>）。我們的專業 CNC 工程與業務團隊正在評估您的圖檔與加工規格，將於 24 小時內（1 個工作天）與您聯繫並提供正式報價。</p>
            <table style="width:100%;border-collapse:collapse;margin:18px 0;font-size:13px;">
                <thead>
                    <tr style="background:#f1f5f9;color:#334155;">
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;">#</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">品項名稱 / Part Name</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">材質 / Material</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:left;">尺寸 / Dimensions</th>
                        <th style="padding:8px 12px;border:1px solid #cbd5e1;text-align:right;">數量 / Qty</th>
                    </tr>
                </thead>
                <tbody>{items_rows}</tbody>
            </table>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
            <p style="font-size:13px;color:#475569;margin:0;">
                <strong>錸億精密工業有限公司 (Legacy Precision Inc.)</strong><br>
                電話：06-3565855 / 0929-045-504 ｜ 傳真：06-3562100<br>
                信箱：laiyi.huang@msa.hinet.net<br>
                廠址：709029 台南市安南區安和路四段36巷276號
            </p>
        </div>
    </div>
    """


def send_rfq_emails_async(rfq_id: str, attachment_paths: list = None):
    """Spawn a background thread to send Admin notification (with attachments) and Customer confirmation."""
    def _worker():
        settings = load_settings()
        if not settings.get("smtp_enabled") or not settings.get("smtp_user") or not settings.get("smtp_password"):
            _update_rfq_email_status(rfq_id, "SMTP 未啟用或未設定帳號密碼 (已安全儲存於系統資料庫)")
            return

        rfqs = load_rfqs()
        target_rfq = next((r for r in rfqs if r.get("id") == rfq_id), None)
        if not target_rfq:
            return

        smtp_host = settings.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(settings.get("smtp_port", 587))
        smtp_user = settings.get("smtp_user")
        smtp_pass = settings.get("smtp_password")
        sender_name = settings.get("smtp_sender_name", "錸億精密工業 智慧詢價系統")
        admin_email = settings.get("admin_notify_email", "laiyi.huang@msa.hinet.net")
        customer_email = target_rfq.get("email", "")

        try:
            # 1. Admin email with attachments
            admin_msg = MIMEMultipart()
            admin_msg["From"] = formataddr((sender_name, smtp_user))
            admin_msg["To"] = admin_email
            if customer_email:
                admin_msg["Reply-To"] = customer_email
            admin_msg["Subject"] = f"【新詢價單 {rfq_id}】{target_rfq.get('company')} - {target_rfq.get('contact_name')}"
            admin_msg.attach(MIMEText(_build_admin_email_html(target_rfq), "html", "utf-8"))

            for fpath in (attachment_paths or []):
                if os.path.exists(fpath) and os.path.getsize(fpath) < 15 * 1024 * 1024:
                    fname = os.path.basename(fpath)
                    with open(fpath, "rb") as f:
                        part = MIMEApplication(f.read(), Name=fname)
                    part["Content-Disposition"] = f'attachment; filename="{fname}"'
                    admin_msg.attach(part)

            # 2. Customer confirmation email
            cust_msg = None
            if customer_email and "@" in customer_email:
                cust_msg = MIMEMultipart()
                cust_msg["From"] = formataddr((sender_name, smtp_user))
                cust_msg["To"] = customer_email
                cust_msg["Subject"] = f"【錸億精密工業】我們已收到您的線上詢價單 ({rfq_id}) / RFQ Confirmation"
                cust_msg.attach(MIMEText(_build_customer_email_html(target_rfq), "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if settings.get("smtp_use_tls", True):
                    server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(admin_msg)
                if cust_msg:
                    server.send_message(cust_msg)

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _update_rfq_email_status(rfq_id, f"已成功寄送通知信與客戶確認信 ({now_str})")
        except Exception as e:
            _update_rfq_email_status(rfq_id, f"郵件發送失敗: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _update_rfq_email_status(rfq_id: str, status_msg: str):
    with _file_lock:
        rfqs = load_rfqs()
        for r in rfqs:
            if r.get("id") == rfq_id:
                r["email_status"] = status_msg
                break
        save_rfqs(rfqs, trigger_cloud=False)

