# -*- coding: utf-8 -*-
"""
錸億精密工業有限公司 (LAI YI Precision Industrial Co., Ltd.)
Enterprise Brand Portal & Smart RFQ Management Platform
Backend: Python Flask + Gunicorn + Edge-TTS + HMAC Admin CRM + Cloud Sync + Keep-Alive
"""

import os
import re
import csv
import io
import time
import json
import hmac
import hashlib
import asyncio
import datetime
import threading
from functools import wraps
from urllib.parse import quote
from flask import (
    Flask, render_template, request, jsonify, send_from_directory,
    send_file, Response, make_response
)
from werkzeug.utils import secure_filename

from catalog_data import (
    COMPANY_INFO, ROUTE_SEO, MATERIALS, PRODUCTS, EQUIPMENT, FAQS, TECH_ARTICLES, build_json_ld
)
from cloud_sync import (
    BASE_DIR, DATA_DIR, UPLOADS_DIR, TTS_CACHE_DIR,
    load_settings, save_settings, load_rfqs, save_rfqs,
    restore_from_cloud_on_startup, backup_to_github_branch,
    restore_from_github_branch, send_rfq_emails_async
)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

START_TIME = time.time()
SECRET_KEY = os.environ.get("SECRET_KEY", "laiyi-precision-hmac-secret-2026-key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "laiyi888")

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "webp", "gif", "bmp", "svg",
    "dwg", "dxf", "step", "stp", "iges", "igs", "stl", "x_t",
    "zip", "rar", "7z", "doc", "docx", "xls", "xlsx", "csv", "txt"
}

EDGE_TTS_VOICES = {
    "zh-TW": "zh-TW-HsiaoChenNeural",
    "en": "en-US-AriaNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural"
}

# ==============================================================================
# Startup Cloud Auto-Restore & Background Keep-Alive Daemon
# ==============================================================================
_startup_sync_info = {"restored": False}


def _init_cloud_and_keep_alive():
    if _startup_sync_info.get("initialized"):
        return
    _startup_sync_info["initialized"] = True

    def _startup_task():
        res = restore_from_cloud_on_startup()
        _startup_sync_info["restore_result"] = res

    threading.Thread(target=_startup_task, daemon=True).start()

    def _keep_alive_loop():
        import requests as req_lib
        while True:
            time.sleep(540)  # Every 9 minutes
            try:
                settings = load_settings()
                target_url = (
                    settings.get("keep_alive_url")
                    or os.environ.get("KEEP_ALIVE_URL")
                    or os.environ.get("RENDER_EXTERNAL_URL")
                )
                if target_url:
                    ping_url = target_url.rstrip("/") + "/api/health"
                    req_lib.get(ping_url, timeout=10)
            except Exception:
                pass

    threading.Thread(target=_keep_alive_loop, daemon=True).start()


_init_cloud_and_keep_alive()


# ==============================================================================
# HMAC Security Helpers for Admin CRM
# ==============================================================================
def generate_admin_token(password: str) -> str:
    msg = f"laiyi_admin:{password}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_admin_password(input_password: str) -> bool:
    expected = ADMIN_PASSWORD.encode("utf-8")
    provided = (input_password or "").encode("utf-8")
    return hmac.compare_digest(expected, provided)


def is_admin_authenticated() -> bool:
    token = request.headers.get("X-Admin-Token") or request.cookies.get("laiyi_admin_token") or ""
    expected_token = generate_admin_token(ADMIN_PASSWORD)
    return hmac.compare_digest(token, expected_token)


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin_authenticated():
            return jsonify({"ok": False, "error": "Unauthorized (HMAC verification failed)"}), 401
        return f(*args, **kwargs)
    return decorated


# ==============================================================================
# Static Assets Serving (/assets/...)
# ==============================================================================
@app.route("/assets/<path:filename>")
def serve_assets(filename):
    assets_dir = os.path.join(BASE_DIR, "assets")
    return send_from_directory(assets_dir, filename)


# ==============================================================================
# SSR + SPA Hybrid Routes (Each with Dedicated URL, SEO Meta & JSON-LD)
# ==============================================================================
def _render_spa_route(route_key: str):
    lang = request.args.get("lang", "zh-TW")
    if lang not in ("zh-TW", "en", "ja", "ko"):
        lang = "zh-TW"

    seo_entry = ROUTE_SEO.get(route_key, ROUTE_SEO["home"])
    base_url = request.url_root.rstrip("/") if request.url_root else "https://www.laiyi-tw.com"
    canonical_url = f"{base_url}{seo_entry['path']}"
    if lang != "zh-TW":
        canonical_url += f"?lang={lang}"

    json_ld_schemas = build_json_ld(route_key, lang=lang, base_url=base_url)

    initial_state = {
        "activeRoute": route_key,
        "lang": lang,
        "company": COMPANY_INFO,
        "routeSeo": ROUTE_SEO,
        "materials": MATERIALS,
        "products": PRODUCTS,
        "equipment": EQUIPMENT,
        "faqs": FAQS,
        "articles": TECH_ARTICLES
    }

    return render_template(
        "index.html",
        route_key=route_key,
        lang=lang,
        page_title=seo_entry["title"][lang],
        page_description=seo_entry["description"][lang],
        canonical_url=canonical_url,
        og_image=f"{base_url}/assets/images/brand/about-company.png",
        json_ld_str=json.dumps(json_ld_schemas, ensure_ascii=False),
        initial_state_str=json.dumps(initial_state, ensure_ascii=False),
        company=COMPANY_INFO,
        materials=MATERIALS,
        products=PRODUCTS,
        equipment=EQUIPMENT,
        faqs=FAQS,
        articles=TECH_ARTICLES
    )


@app.route("/")
@app.route("/index.php")
def route_home():
    return _render_spa_route("home")


@app.route("/about")
@app.route("/about.php")
def route_about():
    return _render_spa_route("about")


@app.route("/products")
@app.route("/services")
@app.route("/article.php")
def route_products():
    return _render_spa_route("products")


@app.route("/equipment")
@app.route("/works.php")
def route_equipment():
    return _render_spa_route("equipment")


@app.route("/calculator")
def route_calculator():
    return _render_spa_route("calculator")


@app.route("/faq")
@app.route("/faq.php")
def route_faq():
    return _render_spa_route("faq")


@app.route("/news")
@app.route("/life.php")
def route_news():
    return _render_spa_route("news")


@app.route("/privacy")
@app.route("/privacy.php")
def route_privacy():
    return _render_spa_route("privacy")


@app.route("/rfq")
@app.route("/contact")
@app.route("/contact.php")
def route_rfq():
    return _render_spa_route("rfq")


# ==============================================================================
# Public APIs: Catalog, CNC Spec Calculator, AI Assistant, Edge-TTS, RFQ Submit
# ==============================================================================
@app.route("/api/catalog", methods=["GET"])
def api_catalog():
    return jsonify({
        "ok": True,
        "company": COMPANY_INFO,
        "routeSeo": ROUTE_SEO,
        "materials": MATERIALS,
        "products": PRODUCTS,
        "equipment": EQUIPMENT,
        "faqs": FAQS
    })


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(silent=True) or {}
    length = max(10.0, min(2000.0, float(data.get("length", 250))))
    width = max(10.0, min(1500.0, float(data.get("width", 180))))
    height = max(5.0, min(810.0, float(data.get("height", 45))))
    qty = max(1, min(10000, int(data.get("qty", 10))))
    mat_id = data.get("material_id", "mat-aluminum")
    tolerance = data.get("tolerance", "±0.005 mm")
    complexity = data.get("complexity", "medium")  # simple, medium, high
    surface = data.get("surface", "standard")

    mat = next((m for m in MATERIALS if m["id"] == mat_id), MATERIALS[2])
    density = mat["density"]  # g/cm3
    volume_cm3 = (length * width * height) / 1000.0
    raw_weight_kg = round((volume_cm3 * density) / 1000.0 * 1.12, 3)  # +12% stock allowance
    finished_weight_kg = round(raw_weight_kg * 0.62, 3)

    # Optimal Machine Selection from Lai Yi's real CNC fleet
    if length > 1400 or width > 650 or height > 610:
        recommended_machine = "WELE NB-2150 大型CNC龍門加工機 (2000×1500×810 mm)"
        machine_rate = 1.65
        table_x, table_y = 2000, 1500
    elif length > 1200:
        recommended_machine = "WELE AQ-1465 立式CNC電腦銑床 (1400×650×610 mm)"
        machine_rate = 1.25
        table_x, table_y = 1400, 650
    elif length > 800 or width > 500:
        recommended_machine = "WELE AQ-1265 高精度立式電腦銑床 ×2台聯動 (1200×650×610 mm)"
        machine_rate = 1.15
        table_x, table_y = 1200, 650
    else:
        recommended_machine = "TONGTAI TMV-800A 高速立式加工機 / WELE AA-965"
        machine_rate = 1.0
        table_x, table_y = 800, 500

    complexity_mult = {"simple": 0.85, "medium": 1.15, "high": 1.65}.get(complexity, 1.15)
    tol_mult = 1.30 if "0.005" in str(tolerance) else (1.12 if "0.01" in str(tolerance) else 1.0)
    qty_discount = 0.72 if qty >= 100 else (0.82 if qty >= 30 else (0.90 if qty >= 10 else 1.0))

    mat_cost = max(120.0, raw_weight_kg * mat["unit_price_kg_twd"])
    machining_base = (volume_cm3 ** 0.58) * 28.0 * mat["machinability_factor"] * machine_rate * complexity_mult * tol_mult
    setup_cost_per_unit = 1800.0 / max(1, qty)
    est_unit_twd = int(round((mat_cost + machining_base + setup_cost_per_unit) * qty_discount, -1))
    est_total_twd = est_unit_twd * qty

    # Nesting calculation on machine worktable
    margin = 25
    per_row = max(1, int((table_x - margin) // (length + 15)))
    per_col = max(1, int((table_y - margin) // (width + 15)))
    parts_per_setup = per_row * per_col

    lead_days = "5 ~ 7" if qty <= 20 and length <= 800 else ("8 ~ 12" if qty <= 100 else "12 ~ 16")

    return jsonify({
        "ok": True,
        "raw_weight_kg": raw_weight_kg,
        "finished_weight_kg": finished_weight_kg,
        "total_shipment_kg": round(finished_weight_kg * qty * 1.15, 2),
        "recommended_machine": recommended_machine,
        "qc_equipment": "日本東京精密 TOKYO SEIMITSU GS800D 3D CMM 三次元全檢",
        "table_x": table_x,
        "table_y": table_y,
        "parts_per_setup": parts_per_setup,
        "est_unit_twd": est_unit_twd,
        "est_total_twd": est_total_twd,
        "discount_pct": int(round((1.0 - qty_discount) * 100)),
        "lead_time_days": lead_days
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip().lower()
    lang = data.get("lang", "zh-TW")
    if lang not in ("zh-TW", "en", "ja", "ko"):
        lang = "zh-TW"

    # Multi-language intent matching knowledge engine
    if any(k in msg for k in ["精度", "公差", "tolerance", "accuracy", "三次元", "cmm", "東京精密", "公差", "정밀", "공차"]):
        replies = {
            "zh-TW": "錸億精密的最高尺寸加工精度可達 **±0.005 mm (5微米)**！我們廠內恆溫品保室配備日本原裝 **東京精密 TOKYO SEIMITSU GS800D 三次元座標量測機 (3D CMM)**、鎢鋼0級塊規、標準環規與三點式內徑分釐卡，可隨貨提供完整 3D 量測檢驗報告。",
            "en": "LAI YI Precision achieves tight tolerances down to **±0.005 mm (5 microns)**! Our QC room is equipped with a Japanese **TOKYO SEIMITSU GS800D 3D CMM**, Grade 0 tungsten carbide gauge blocks, and 3-point bore micrometers. Full 3D CMM inspection reports are available upon request.",
            "ja": "錸億精密の最高加工公差は **±0.005 mm（5ミクロン）** です！恒温品質管理室に日本製の **東京精密 TOKYO SEIMITSU GS800D 三次元座標測定機（3D CMM）** を完備しており、出荷時に検査成績書を添付可能です。",
            "ko": "라이이 정밀공업은 최고 **±0.005 mm (5마이크론)**의 초정밀 치수 공차를 구현합니다! 항온 품질보증실에 일본 **도쿄정밀 TOKYO SEIMITSU GS800D 3차원 좌표측정기(3D CMM)**를 보유하고 있으며 공식 검사성적서 발급이 가능합니다."
        }
        action = {"route": "equipment", "label": {"zh-TW": "查看三次元與量測設備", "en": "View 3D CMM Equipment", "ja": "測定設備を見る", "ko": "측정 장비 보기"}[lang]}
    elif any(k in msg for k in ["龍門", "最大", "尺寸", "行程", "機台", "設備", "gantry", "size", "machine", "wele", "nb-2150", "門型", "겐트리", "설비"]):
        replies = {
            "zh-TW": "我們擁有完整的日本與台灣精密加工機隊！最大加工尺寸達 **2000 × 1500 × 810 mm**（由 **崴立 WELE NB-2150 大型 CNC 龍門加工機** 擔綱），另配備 **WELE AQ-1465** (1400mm)、**WELE AQ-1265 ×2台** (1200mm)、**WELE AA-965** 及 **東台 TONGTAI TMV-800A** 高速加工機。",
            "en": "Our maximum machining envelope reaches **2000 × 1500 × 810 mm** on our **WELE NB-2150 Large CNC Gantry Mill**! We also operate **WELE AQ-1465** (1400mm), **2x WELE AQ-1265** (1200mm), **WELE AA-965**, and **TONGTAI TMV-800A** high-speed machining centers.",
            "ja": "最大加工サイズは **2000 × 1500 × 810 mm**（**WELE NB-2150 大型門型マシニングセンタ**）です。さらに **WELE AQ-1465**、**AQ-1265（2台）**、**AA-965**、**東台 TMV-800A** 高速マシニングセンタを完備しています。",
            "ko": "최대 가공 범위는 **2000 × 1500 × 810 mm** (**WELE NB-2150 대형 겐트리 가공기**)이며, **WELE AQ-1465**, **AQ-1265 (2대)**, **AA-965** 및 **동타이 TMV-800A** 고속 머시닝센터를 가동하고 있습니다."
        }
        action = {"route": "equipment", "label": {"zh-TW": "瀏覽完整廠內設備", "en": "Explore CNC Fleet", "ja": "工場設備一覧へ", "ko": "보유 설비 보기"}[lang]}
    elif any(k in msg for k in ["材質", "材料", "鋁", "不鏽鋼", "鈦", "銅", "鐵", "合金", "material", "aluminum", "stainless", "titanium", "brass", "材質", "소재"]):
        replies = {
            "zh-TW": "我們支援 6 大類金屬與工程材質加工：\n1. **鋁合金**：6061-T6、7075-T6、2011-T3\n2. **不鏽鋼**：SUS303、SUS304、SUS316L、SUS420J2、SUS440C\n3. **合金鋼**：SCM415、SCM435、SCM440、SUJ2\n4. **鐵/碳鋼**：S15C、S45C、12L14\n5. **銅合金**：黃銅 C3604、紅銅\n6. **特殊合金**：純鈦、Ti-6Al-4V 鈦合金、鈹銅、磷青銅。",
            "en": "We machine 6 major material groups:\n1. **Aluminum**: 6061-T6, 7075-T6, 2011-T3\n2. **Stainless Steel**: SUS303, SUS304, SUS316L, SUS420J2, SUS440C\n3. **Alloy Steel**: SCM415, SCM435, SCM440, SUJ2\n4. **Carbon Steel**: S15C, S45C, 12L14\n5. **Brass/Copper**: C3601~C3604\n6. **Special Alloys**: Titanium (Gr2/Gr5), Beryllium Copper, Phosphor Bronze.",
            "ja": "6大材質グループに対応しています：\n1. **アルミ合金**：6061-T6、7075-T6\n2. **ステンレス**：SUS303、SUS304、SUS316L、SUS420J2、SUS440\n3. **合金鋼**：SCM415、SCM435、SCM440、SUJ2\n4. **炭素鋼**：S15C、S45C\n5. **真鍮・銅合金**：C3604等\n6. **特殊合金**：チタン合金、ベリリウム銅、リン青銅。",
            "ko": "6대 금속 소재 가공을 지원합니다:\n1. **알루미늄 합금**: 6061-T6, 7075-T6\n2. **스테인리스강**: SUS303, SUS304, SUS316L, SUS420J2, SUS440\n3. **합금강**: SCM415, SCM435, SCM440, SUJ2\n4. **탄소강**: S15C, S45C\n5. **황동/동합금**: C3604 등\n6. **특수합금**: 티타늄, 베릴륨동, 인청동."
        }
        action = {"route": "products", "label": {"zh-TW": "前往材質與產品檢索", "en": "Browse Materials & Parts", "ja": "材質・製品カタログへ", "ko": "소재 및 제품 보기"}[lang]}
    elif any(k in msg for k in ["報價", "詢價", "價格", "多少錢", "試算", "quote", "rfq", "price", "cost", "calculator", "見積", "견적", "단가"]):
        replies = {
            "zh-TW": "您可以先使用我們的 **「智慧 CNC 規格試算工具」** 輸入長寬高、材質與數量，立即獲得毛坯重量、最佳機台配置與參考價格區間；或直接前往 **「線上詢價單 (RFQ)」** 上傳工程圖檔（PDF/DWG/STEP），我們將於 24 小時內提供正式報價！",
            "en": "You can use our **Smart CNC Spec Calculator** to instantly estimate part weight, machine match, and reference pricing, or submit your 2D/3D CAD files via our **Online RFQ Form** for an official quote within 24 hours!",
            "ja": "**「スマートCNC加工試算ツール」** で重量・最適設備・参考価格を即時試算できるほか、**「オンライン見積依頼（RFQ）」** から図面（PDF/DWG/STEP）をアップロードいただければ24時間以内に正式回答いたします！",
            "ko": "**'스마트 CNC 가공 시산 도구'**에서 치수와 수량을 입력해 중량 및 참고 단가를 즉시 확인하시거나, **'온라인 견적 요청(RFQ)'**에서 도면(PDF/DWG/STEP)을 업로드하시면 24시간 내에 정식 견적을 회신드립니다!"
        }
        action = {"route": "calculator", "label": {"zh-TW": "開啟智慧規格試算工具", "en": "Open CNC Calculator", "ja": "試算ツールを開く", "ko": "시산 도구 열기"}[lang]}
    elif any(k in msg for k in ["電話", "聯絡", "地址", "在哪", "信箱", "contact", "phone", "address", "email", "tainan", "連絡", "연락", "주소"]):
        replies = {
            "zh-TW": "📍 **錸億精密工業有限公司**\n- **電話**：06-3565855 / 0929-045-504\n- **傳真**：06-3562100\n- **信箱**：laiyi.huang@msa.hinet.net\n- **廠址**：709029 台南市安南區安和路四段36巷276號",
            "en": "📍 **LAI YI Precision Industrial Co., Ltd.**\n- **Tel**: +886-6-3565855 / 0929-045-504\n- **Fax**: +886-6-3562100\n- **Email**: laiyi.huang@msa.hinet.net\n- **Address**: No. 276, Ln. 36, Sec. 4, Anhe Rd., Annan Dist., Tainan City 709029, Taiwan",
            "ja": "📍 **錸億精密工業有限会社**\n- **電話**：+886-6-3565855\n- **FAX**：+886-6-3562100\n- **メール**：laiyi.huang@msa.hinet.net\n- **所在地**：台湾台南市安南区安和路四段36巷276号",
            "ko": "📍 **라이이 정밀공업 유한공사**\n- **전화**: +886-6-3565855\n- **팩스**: +886-6-3562100\n- **이메일**: laiyi.huang@msa.hinet.net\n- **주소**: 대만 타이난시 안난구 안허로 4단 36항 276호"
        }
        action = {"route": "rfq", "label": {"zh-TW": "前往聯絡與線上詢價", "en": "Contact & Online RFQ", "ja": "お問い合わせ・見積依頼", "ko": "문의 및 견적 요청"}[lang]}
    else:
        replies = {
            "zh-TW": "您好！我是錸億精密 AI 工程顧問。我們專精於 **台南 CNC 精密銑床加工** 與 **2000mm 大型 CNC 龍門銑床加工**（精度達 ±0.005mm），服務涵蓋半導體設備、面板、AI 伺服器散熱件與精密檢具/治具。請問您想了解「加工尺寸與機台」、「材質規格」、「線上價格試算」還是「上傳圖檔詢價」呢？",
            "en": "Hello! I am LAI YI Precision's AI Engineering Advisor. We specialize in **±0.005mm CNC Milling** and **2000mm Large CNC Gantry Machining** for semiconductor, AI server, aerospace, and custom jig/gauge applications. Would you like to explore our CNC equipment, material specs, online cost calculator, or submit an RFQ?",
            "ja": "こんにちは！錸億精密のAIエンジニアリングアドバイザーです。公差 **±0.005mmのCNC精密フライス加工** と **最大2000mmの大型門型マシニング加工** を提供しております。設備仕様、加工材質、オンライン試算、または図面見積依頼のどれをご案内しましょうか？",
            "ko": "안녕하세요! 라이이 정밀공업 AI 엔지니어링 어드바이저입니다. 당사는 **±0.005mm 고정밀 CNC 밀링** 및 **2000mm 대형 겐트리 가공** 전문 기업입니다. 보유 설비, 가공 소재, 온라인 시산기, 도면 견적 요청 중 어떤 항목을 안내해 드릴까요?"
        }
        action = {"route": "products", "label": {"zh-TW": "瀏覽精密加工產品中心", "en": "Explore Product Center", "ja": "製品センターを見る", "ko": "제품 센터 보기"}[lang]}

    return jsonify({
        "ok": True,
        "reply": replies[lang],
        "action": action
    })


# ==============================================================================
# Edge-TTS Neural Voice Guide with Local Audio Cache (/api/tts)
# ==============================================================================
async def _generate_edge_tts(text: str, voice: str, out_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+2%")
    await communicate.save(out_path)


@app.route("/api/tts", methods=["GET", "POST"])
def api_tts():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        lang = payload.get("lang", "zh-TW")
    else:
        text = (request.args.get("text") or "").strip()
        lang = request.args.get("lang", "zh-TW")

    if not text:
        return jsonify({"ok": False, "error": "Empty text"}), 400

    text = text[:1200]  # Cap length for responsive synthesis
    voice = EDGE_TTS_VOICES.get(lang, EDGE_TTS_VOICES["zh-TW"])
    cache_key = hashlib.sha256(f"{voice}:{text}".encode("utf-8")).hexdigest()[:24]
    cached_mp3 = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")

    if not os.path.exists(cached_mp3) or os.path.getsize(cached_mp3) < 256:
        try:
            asyncio.run(_generate_edge_tts(text, voice, cached_mp3))
        except Exception as e:
            return jsonify({"ok": False, "error": f"Edge-TTS synthesis error: {e}", "fallback_web_speech": True}), 200

    return send_file(cached_mp3, mimetype="audio/mpeg", as_attachment=False, download_name=f"laiyi_tts_{cache_key}.mp3")


# ==============================================================================
# Online RFQ Submission with Multi-File Upload & Async Notification (/api/rfq)
# ==============================================================================
def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/api/rfq", methods=["POST"])
def api_submit_rfq():
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        items_raw = form.get("items", "[]")
        try:
            items = json.loads(items_raw)
        except Exception:
            items = []
        company = (form.get("company") or "").strip()
        contact_name = (form.get("contact_name") or "").strip()
        country = (form.get("country") or "TAIWAN (台灣)").strip()
        phone = (form.get("phone") or "").strip()
        email = (form.get("email") or "").strip()
        instant_messenger = (form.get("instant_messenger") or "").strip()
        target_delivery = (form.get("target_delivery") or "").strip()
        customer_notes = (form.get("customer_notes") or "").strip()
        lang = (form.get("lang") or "zh-TW").strip()
        uploaded_files = request.files.getlist("files")
    else:
        data = request.get_json(silent=True) or {}
        items = data.get("items", [])
        company = (data.get("company") or "").strip()
        contact_name = (data.get("contact_name") or "").strip()
        country = (data.get("country") or "TAIWAN (台灣)").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        instant_messenger = (data.get("instant_messenger") or "").strip()
        target_delivery = (data.get("target_delivery") or "").strip()
        customer_notes = (data.get("customer_notes") or "").strip()
        lang = (data.get("lang") or "zh-TW").strip()
        uploaded_files = []

    if not contact_name or not (phone or email):
        return jsonify({"ok": False, "error": "請填寫聯絡人姓名與至少一項聯絡方式（電話或信箱）"}), 400

    now = datetime.datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    rfqs = load_rfqs()
    seq = len(rfqs) + 1
    rfq_id = f"LY-{date_prefix}-{seq:04d}"
    while any(r.get("id") == rfq_id for r in rfqs):
        seq += 1
        rfq_id = f"LY-{date_prefix}-{seq:04d}"

    saved_attachments = []
    saved_paths = []
    for f in uploaded_files:
        if f and f.filename:
            orig_name = f.filename
            if not _allowed_file(orig_name):
                continue
            ext = orig_name.rsplit(".", 1)[1].lower()
            safe_stem = secure_filename(orig_name.rsplit(".", 1)[0]) or "drawing"
            stored_name = f"{rfq_id}_{int(time.time()*1000)%100000}_{safe_stem}.{ext}"
            full_path = os.path.join(UPLOADS_DIR, stored_name)
            f.save(full_path)
            saved_paths.append(full_path)
            saved_attachments.append({
                "original_name": orig_name,
                "stored_name": stored_name,
                "size_kb": round(os.path.getsize(full_path) / 1024.0, 1)
            })

    if not items:
        items = [{
            "sku": "CUSTOM-CNC",
            "name": "客製化 CNC 精密加工專案 (依上傳圖檔或備註)",
            "material": "依圖面指定",
            "dimensions": "依圖面指定",
            "tolerance": "±0.005 mm",
            "surface": "依圖面指定",
            "qty": 1
        }]

    new_record = {
        "id": rfq_id,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
        "company": company or "個人/未填寫公司",
        "contact_name": contact_name,
        "country": country,
        "phone": phone,
        "email": email,
        "instant_messenger": instant_messenger,
        "target_delivery": target_delivery,
        "customer_notes": customer_notes,
        "admin_notes": "",
        "items": items,
        "attachments": saved_attachments,
        "email_status": "排程寄送中 (Async Queued)",
        "lang": lang
    }

    rfqs.insert(0, new_record)
    save_rfqs(rfqs, trigger_cloud=True, new_attachment_paths=saved_paths)
    send_rfq_emails_async(rfq_id, attachment_paths=saved_paths)

    return jsonify({
        "ok": True,
        "rfq_id": rfq_id,
        "created_at": new_record["created_at"],
        "attachments_count": len(saved_attachments),
        "message": "詢價單已成功送出！系統已自動備份並觸發通知信。"
    })


# ==============================================================================
# Health Check & Cloud Anti-Sleep Status (/api/health)
# ==============================================================================
@app.route("/api/health", methods=["GET"])
def api_health():
    settings = load_settings()
    rfqs = load_rfqs()
    uptime_sec = int(time.time() - START_TIME)
    return jsonify({
        "status": "healthy",
        "service": "LAI YI Precision Industrial Portal & Smart RFQ CRM",
        "uptime_seconds": uptime_sec,
        "timestamp": datetime.datetime.now().isoformat(),
        "rfq_count": len(rfqs),
        "storage": {
            "local_json": os.path.exists( os.path.join(DATA_DIR, "rfqs.json") ),
            "github_cloud_backup_configured": bool(settings.get("github_token") and settings.get("github_repo")),
            "github_branch": settings.get("github_branch", "cloud-backup"),
            "postgres_configured": bool(settings.get("database_url")),
            "google_sheets_configured": bool(settings.get("google_sheets_webhook")),
            "last_backup_time": settings.get("last_backup_time"),
            "last_backup_status": settings.get("last_backup_status")
        }
    })


# ==============================================================================
# Admin CRM Routes & APIs (HMAC Protected)
# ==============================================================================
@app.route("/admin")
def route_admin_page():
    return render_template("admin.html", company=COMPANY_INFO)


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if verify_admin_password(password):
        token = generate_admin_token(ADMIN_PASSWORD)
        resp = make_response(jsonify({
            "ok": True,
            "token": token,
            "message": "登入成功 (HMAC 驗證通過)"
        }))
        resp.set_cookie("laiyi_admin_token", token, httponly=True, max_age=86400 * 7, samesite="Lax")
        return resp
    return jsonify({"ok": False, "error": "管理員密碼錯誤，請重新輸入"}), 401


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("laiyi_admin_token")
    return resp


@app.route("/api/admin/rfqs", methods=["GET"])
@require_admin
def api_admin_list_rfqs():
    rfqs = load_rfqs()
    settings = load_settings()
    stats = {
        "total": len(rfqs),
        "pending": sum(1 for r in rfqs if r.get("status") == "pending"),
        "reviewing": sum(1 for r in rfqs if r.get("status") == "reviewing"),
        "quoted": sum(1 for r in rfqs if r.get("status") == "quoted"),
        "won": sum(1 for r in rfqs if r.get("status") == "won"),
        "archived": sum(1 for r in rfqs if r.get("status") == "archived")
    }
    return jsonify({
        "ok": True,
        "rfqs": rfqs,
        "stats": stats,
        "cloud_status": {
            "last_backup_time": settings.get("last_backup_time"),
            "last_backup_status": settings.get("last_backup_status"),
            "last_restore_time": settings.get("last_restore_time"),
            "github_repo": settings.get("github_repo"),
            "github_branch": settings.get("github_branch", "cloud-backup")
        }
    })


@app.route("/api/admin/rfqs/<rfq_id>", methods=["PUT"])
@require_admin
def api_admin_update_rfq(rfq_id):
    data = request.get_json(silent=True) or {}
    rfqs = load_rfqs()
    updated = None
    for r in rfqs:
        if r.get("id") == rfq_id:
            if "status" in data:
                r["status"] = data["status"]
            if "admin_notes" in data:
                r["admin_notes"] = data["admin_notes"]
            r["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated = r
            break

    if not updated:
        return jsonify({"ok": False, "error": "找不到該筆詢價單"}), 404

    save_rfqs(rfqs, trigger_cloud=True)
    return jsonify({"ok": True, "rfq": updated})


@app.route("/api/admin/rfqs/<rfq_id>", methods=["DELETE"])
@require_admin
def api_admin_delete_rfq(rfq_id):
    rfqs = load_rfqs()
    new_rfqs = [r for r in rfqs if r.get("id") != rfq_id]
    if len(new_rfqs) == len(rfqs):
        return jsonify({"ok": False, "error": "找不到該筆詢價單"}), 404
    save_rfqs(new_rfqs, trigger_cloud=True)
    return jsonify({"ok": True})


@app.route("/api/admin/uploads/<path:filename>", methods=["GET"])
@require_admin
def api_admin_download_upload(filename):
    safe_name = os.path.basename(filename)
    return send_from_directory(UPLOADS_DIR, safe_name, as_attachment=request.args.get("download") == "1")


@app.route("/api/admin/export-csv", methods=["GET"])
@require_admin
def api_admin_export_csv():
    rfqs = load_rfqs()
    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Excel compatibility
    writer = csv.writer(output)
    writer.writerow([
        "詢價單號 (RFQ ID)", "建立時間", "狀態", "公司名稱", "聯絡人", "國家/地區",
        "聯絡電話", "電子信箱", "通訊軟體", "期望交期", "詢價品項摘要",
        "客戶備註", "業務內部備註", "附件數量", "郵件通知狀態"
    ])
    status_map = {
        "pending": "待處理",
        "reviewing": "評估報價中",
        "quoted": "已報價",
        "won": "已成交/生產中",
        "archived": "已結案"
    }
    for r in rfqs:
        items_summary = " | ".join(
            f"{i.get('name')} ({i.get('material')}, {i.get('dimensions')}) x{i.get('qty')}"
            for i in r.get("items", [])
        )
        writer.writerow([
            r.get("id", ""),
            r.get("created_at", ""),
            status_map.get(r.get("status", ""), r.get("status", "")),
            r.get("company", ""),
            r.get("contact_name", ""),
            r.get("country", ""),
            r.get("phone", ""),
            r.get("email", ""),
            r.get("instant_messenger", ""),
            r.get("target_delivery", ""),
            items_summary,
            r.get("customer_notes", ""),
            r.get("admin_notes", ""),
            len(r.get("attachments", [])),
            r.get("email_status", "")
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    fname = f"LaiYi_RFQs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@app.route("/api/admin/settings", methods=["GET", "PUT"])
@require_admin
def api_admin_settings():
    if request.method == "GET":
        settings = load_settings()
        return jsonify({"ok": True, "settings": settings})

    data = request.get_json(silent=True) or {}
    allowed_keys = [
        "smtp_enabled", "smtp_host", "smtp_port", "smtp_use_tls",
        "smtp_user", "smtp_password", "smtp_sender_name", "admin_notify_email",
        "github_backup_enabled", "github_token", "github_repo", "github_branch",
        "database_url", "google_sheets_webhook", "keep_alive_url"
    ]
    updates = {k: data[k] for k in allowed_keys if k in data}
    if "smtp_port" in updates:
        try:
            updates["smtp_port"] = int(updates["smtp_port"])
        except Exception:
            updates["smtp_port"] = 587
    updated = save_settings(updates)
    return jsonify({"ok": True, "settings": updated, "message": "系統與郵件/雲端備份參數已儲存！"})


@app.route("/api/admin/cloud-backup", methods=["POST"])
@require_admin
def api_admin_cloud_backup():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "backup")
    if action == "restore":
        ok, msg = restore_from_github_branch()
    else:
        ok, msg = backup_to_github_branch()
    return jsonify({"ok": ok, "message": msg, "settings": load_settings()})


@app.route("/api/admin/test-email", methods=["POST"])
@require_admin
def api_admin_test_email():
    settings = load_settings()
    if not settings.get("smtp_user") or not settings.get("smtp_password"):
        return jsonify({"ok": False, "error": "請先填寫並儲存 SMTP 寄件人帳號與應用程式密碼"}), 400
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.utils import formataddr

        msg = MIMEText(
            "這是一封來自【錸億精密工業 企業官網暨智慧詢價管理平台】的測試信件。\n"
            "若您收到此信，代表您的自動郵件通知參數已設定成功！",
            "plain", "utf-8"
        )
        msg["From"] = formataddr((settings.get("smtp_sender_name", "錸億精密"), settings["smtp_user"]))
        msg["To"] = settings.get("admin_notify_email", settings["smtp_user"])
        msg["Subject"] = "【錸億精密工業】後台 SMTP 郵件通知連線測試成功"

        with smtplib.SMTP(settings.get("smtp_host", "smtp.gmail.com"), int(settings.get("smtp_port", 587)), timeout=12) as server:
            if settings.get("smtp_use_tls", True):
                server.starttls()
            server.login(settings["smtp_user"], settings["smtp_password"])
            server.send_message(msg)
        return jsonify({"ok": True, "message": f"測試信已成功寄出至 {msg['To']}！"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"SMTP 連線或寄信失敗: {e}"}), 400


if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", 5000))
    if "--desktop" in sys.argv:
        # Launch PyWebView native desktop application
        import webview
        threading.Thread(
            target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
            daemon=True
        ).start()
        time.sleep(0.8)
        webview.create_window(
            "錸億精密工業有限公司｜企業級智慧詢價與設備管理系統",
            f"http://127.0.0.1:{port}",
            width=1440,
            height=900,
            min_size=(1024, 680)
        )
        webview.start()
    else:
        app.run(host="0.0.0.0", port=port, debug=False)

