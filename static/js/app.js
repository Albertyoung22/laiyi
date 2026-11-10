/* ==========================================================================
   錸億精密工業有限公司 (LAI YI Precision Industrial Co., Ltd.)
   Enterprise SSR + SPA Router, Multi-Filter Catalog, CNC Calculator,
   Edge-TTS Voice Player, RFQ Cart & AI Customer Service Assistant
   (清新自然・台南安南區風情 & 嚴格統一按鍵規範版)
   ========================================================================== */

(function () {
  "use strict";

  const STATE = window.__INITIAL_STATE__ || {
    activeRoute: "home",
    lang: "zh-TW",
    company: {},
    routeSeo: {},
    materials: [],
    products: [],
    equipment: [],
    faqs: []
  };

  let currentLang = STATE.lang || "zh-TW";
  let currentRoute = STATE.activeRoute || "home";
  let selectedCategory = "all";
  let selectedMaterialFilter = "all";
  let searchKeyword = "";
  let selectedEqTab = "all";
  let currentAudio = null;
  let uploadedFilesList = [];
  let lastCalcResult = null;

  // Persistent RFQ Cart in localStorage
  let rfqCart = [];
  try {
    const saved = localStorage.getItem("laiyi_rfq_cart_v1");
    if (saved) rfqCart = JSON.parse(saved);
  } catch (e) {
    rfqCart = [];
  }

  function saveCart() {
    try {
      localStorage.setItem("laiyi_rfq_cart_v1", JSON.stringify(rfqCart));
    } catch (e) {}
    updateCartBadge();
    renderRfqCartTable();
  }

  function t(key) {
    const dict = (window.I18N_DICT && window.I18N_DICT[currentLang]) || window.I18N_DICT["zh-TW"] || {};
    return dict[key] || (window.I18N_DICT["zh-TW"] && window.I18N_DICT["zh-TW"][key]) || key;
  }

  function showToast(msg) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const item = document.createElement("div");
    item.className = "toast-item";
    item.innerHTML = msg;
    container.appendChild(item);
    setTimeout(() => {
      item.style.opacity = "0";
      setTimeout(() => item.remove(), 260);
    }, 3400);
  }

  // ==========================================================================
  // SSR + SPA Hybrid Router (HTML5 History API pushState / popstate)
  // ==========================================================================
  function navigateTo(routeKey, pushHistory = true) {
    if (!STATE.routeSeo[routeKey]) routeKey = "home";
    currentRoute = routeKey;

    document.querySelectorAll(".spa-view").forEach((el) => {
      el.classList.toggle("active", el.id === `view-${routeKey}`);
    });

    document.querySelectorAll(".nav-link[data-route]").forEach((link) => {
      link.classList.toggle("active", link.getAttribute("data-route") === routeKey);
    });

    const mainNav = document.getElementById("main-nav");
    if (mainNav) mainNav.classList.remove("mobile-open");

    const seo = STATE.routeSeo[routeKey] || STATE.routeSeo["home"];
    if (seo) {
      const titleText = (seo.title && seo.title[currentLang]) || document.title;
      const descText = (seo.description && seo.description[currentLang]) || "";
      document.title = titleText;
      const metaDesc = document.querySelector('meta[name="description"]');
      if (metaDesc) metaDesc.setAttribute("content", descText);
      const ogTitle = document.querySelector('meta[property="og:title"]');
      if (ogTitle) ogTitle.setAttribute("content", titleText);
      const ogDesc = document.querySelector('meta[property="og:description"]');
      if (ogDesc) ogDesc.setAttribute("content", descText);

      let targetUrl = seo.path || "/";
      if (currentLang !== "zh-TW") {
        targetUrl += `?lang=${encodeURIComponent(currentLang)}`;
      }
      if (pushHistory && window.history && window.history.pushState) {
        window.history.pushState({ route: routeKey, lang: currentLang }, titleText, targetUrl);
      }
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  window.addEventListener("popstate", function (ev) {
    if (ev.state && ev.state.route) {
      if (ev.state.lang && ev.state.lang !== currentLang) {
        setLanguage(ev.state.lang, false);
      }
      navigateTo(ev.state.route, false);
    }
  });

  // ==========================================================================
  // 4-Language Reactive Switcher (zh-TW, en, ja, ko)
  // ==========================================================================
  function setLanguage(lang, updateUrl = true) {
    if (!["zh-TW", "en", "ja", "ko"].includes(lang)) lang = "zh-TW";
    currentLang = lang;
    document.documentElement.lang = lang;

    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-lang") === lang);
    });

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.setAttribute("placeholder", t(key));
    });

    const compNameEl = document.getElementById("header-company-name");
    if (compNameEl && STATE.company.short_name) {
      compNameEl.textContent = STATE.company.short_name[currentLang] || STATE.company.short_name["zh-TW"];
    }
    const aboutIntroEl = document.getElementById("about-company-intro");
    if (aboutIntroEl && STATE.company.intro) {
      aboutIntroEl.textContent = STATE.company.intro[currentLang] || STATE.company.intro["zh-TW"];
    }
    const footerAddrEl = document.getElementById("footer-address");
    if (footerAddrEl && STATE.company.address) {
      footerAddrEl.textContent = STATE.company.address[currentLang] || STATE.company.address["zh-TW"];
    }

    renderHomeMaterials();
    renderHomeFeaturedProducts();
    renderMaterialFilterOptions();
    renderProductsCatalog();
    renderMaterialsTable();
    renderEquipmentCatalog();
    renderCalculatorMaterialOptions();
    runCalculation();
    renderFaqList();
    renderRfqCartTable();

    if (updateUrl) {
      navigateTo(currentRoute, true);
    }
  }

  // ==========================================================================
  // Edge-TTS Neural Voice Guide Player
  // ==========================================================================
  function speakText(text) {
    if (!text) return;
    stopTts();

    const bar = document.getElementById("tts-player-bar");
    const statusEl = document.getElementById("tts-status-text");
    if (bar && statusEl) {
      bar.classList.add("active");
      statusEl.textContent = "🔊 AI 語音合成導覽載入中 (Edge-TTS)...";
    }

    const url = `/api/tts?lang=${encodeURIComponent(currentLang)}&text=${encodeURIComponent(text)}`;
    const audio = new Audio(url);
    currentAudio = audio;

    audio.addEventListener("canplay", () => {
      if (statusEl) statusEl.textContent = `🔊 正在朗讀導覽 (${currentLang})...`;
      audio.play().catch(() => {
        fallbackWebSpeech(text);
      });
    });

    audio.addEventListener("ended", () => {
      stopTts();
    });

    audio.addEventListener("error", () => {
      fallbackWebSpeech(text);
    });
  }

  function fallbackWebSpeech(text) {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = currentLang;
      utter.onend = () => stopTts();
      window.speechSynthesis.speak(utter);
    } else {
      stopTts();
    }
  }

  function stopTts() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    const bar = document.getElementById("tts-player-bar");
    if (bar) bar.classList.remove("active");
  }

  // ==========================================================================
  // Dynamic Catalog Renderers (統一按鍵高度與網格對齊)
  // ==========================================================================
  function renderHomeMaterials() {
    const grid = document.getElementById("home-materials-grid");
    if (!grid) return;
    grid.innerHTML = STATE.materials.map((m) => {
      const name = m.name[currentLang] || m.name["zh-TW"];
      const summary = m.summary[currentLang] || m.summary["zh-TW"];
      return `
        <div class="tech-card">
          <div class="card-thumb">
            <img src="${m.image}" alt="${name}" loading="lazy">
            <span class="card-tag-top">${m.code}</span>
            <span class="card-tag-tol">${m.hardness}</span>
          </div>
          <div class="card-body">
            <h3 class="card-title">${name}</h3>
            <p class="card-desc">${summary}</p>
            <div class="spec-pill-list">
              ${m.grades.slice(0, 5).map((g) => `<span class="spec-pill">${g}</span>`).join("")}
            </div>
            <div class="card-footer-actions">
              <button type="button" class="btn btn-sm btn-secondary" onclick="window.LaiYiApp.filterByMaterial('${m.id}')">${t("btn.detail")}</button>
              <button type="button" class="btn btn-sm btn-primary" onclick="window.LaiYiApp.addMaterialToRfq('${m.id}')">${t("btn.addRfq")}</button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderHomeFeaturedProducts() {
    const grid = document.getElementById("home-featured-products");
    if (!grid) return;
    const featured = STATE.products.slice(0, 6);
    grid.innerHTML = featured.map((p) => buildProductCardHtml(p)).join("");
  }

  function buildProductCardHtml(p) {
    const name = p.name[currentLang] || p.name["zh-TW"];
    const desc = p.description[currentLang] || p.description["zh-TW"];
    const catLabel = t(`cat.${p.category}`);
    return `
      <div class="tech-card">
        <div class="card-thumb">
          <img src="${p.image}" alt="${name}" loading="lazy">
          <span class="card-tag-top">${catLabel}</span>
          <span class="card-tag-tol">${p.tolerance}</span>
        </div>
        <div class="card-body">
          <div class="card-sku">SKU: ${p.sku} · MOQ: ${p.moq} PCS</div>
          <h3 class="card-title">${name}</h3>
          <p class="card-desc">${desc}</p>
          <div class="spec-pill-list">
            <span class="spec-pill">材質: ${p.material_grade}</span>
            <span class="spec-pill">尺寸: ${p.dimensions}</span>
            <span class="spec-pill">${p.machine_used}</span>
          </div>
          <div class="card-footer-actions cols-3">
            <button type="button" class="btn btn-sm btn-secondary" onclick="window.LaiYiApp.openProductModal('${p.id}')">${t("btn.detail")}</button>
            <button type="button" class="btn btn-sm btn-tts" onclick="window.LaiYiApp.speakProduct('${p.id}')" title="Edge-TTS">${t("btn.listen")}</button>
            <button type="button" class="btn btn-sm btn-primary" onclick="window.LaiYiApp.addProductToRfq('${p.id}', 1)">${t("btn.addRfq")}</button>
          </div>
        </div>
      </div>
    `;
  }

  function renderMaterialFilterOptions() {
    const sel = document.getElementById("product-material-filter");
    if (!sel) return;
    const currentVal = sel.value || "all";
    sel.innerHTML = `<option value="all">${t("filter.allMaterials")}</option>` +
      STATE.materials.map((m) => `<option value="${m.id}">${m.name[currentLang] || m.name["zh-TW"]}</option>`).join("");
    sel.value = currentVal;
  }

  function renderProductsCatalog() {
    const grid = document.getElementById("products-catalog-grid");
    const countEl = document.getElementById("products-count-badge");
    if (!grid) return;

    const kw = (searchKeyword || "").trim().toLowerCase();
    const filtered = STATE.products.filter((p) => {
      if (selectedCategory !== "all" && p.category !== selectedCategory) return false;
      if (selectedMaterialFilter !== "all" && p.material_id !== selectedMaterialFilter && p.material_id_alt !== selectedMaterialFilter) return false;
      if (kw) {
        const hay = [
          p.sku,
          p.material_grade,
          p.dimensions,
          p.machine_used,
          p.name["zh-TW"], p.name["en"], p.name["ja"], p.name["ko"],
          p.description["zh-TW"], p.description["en"]
        ].join(" ").toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });

    if (countEl) countEl.textContent = `${filtered.length} ITEMS`;
    grid.innerHTML = filtered.map((p) => buildProductCardHtml(p)).join("");
  }

  function renderMaterialsTable() {
    const tbody = document.getElementById("materials-spec-tbody");
    if (!tbody) return;
    tbody.innerHTML = STATE.materials.map((m) => {
      const name = m.name[currentLang] || m.name["zh-TW"];
      const surf = m.surface_treatments[currentLang] || m.surface_treatments["zh-TW"];
      return `
        <tr>
          <td style="font-weight:800;color:var(--accent-primary);">${name}</td>
          <td>${m.grades.join("、")}</td>
          <td>${m.density} g/cm³</td>
          <td><span class="spec-pill">${m.hardness}</span></td>
          <td>${surf}</td>
          <td>
            <button type="button" class="btn btn-sm btn-primary" onclick="window.LaiYiApp.addMaterialToRfq('${m.id}')">
              ${t("btn.addRfq")}
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderEquipmentCatalog() {
    const grid = document.getElementById("equipment-catalog-grid");
    const tbody = document.getElementById("equipment-spec-tbody");
    if (!grid) return;

    const filtered = STATE.equipment.filter((eq) => {
      if (selectedEqTab === "all") return true;
      return eq.type === selectedEqTab;
    });

    grid.innerHTML = filtered.map((eq) => {
      const name = eq.name[currentLang] || eq.name["zh-TW"];
      const feat = eq.feature[currentLang] || eq.feature["zh-TW"];
      const badge = eq.type === "machining" ? "CNC MACHINING" : "3D CMM / METROLOGY";
      return `
        <div class="tech-card">
          <div class="card-thumb">
            <img src="${eq.image}" alt="${name}" loading="lazy">
            <span class="card-tag-top">${badge}</span>
            <span class="card-tag-tol">${eq.accuracy}</span>
          </div>
          <div class="card-body">
            <div class="card-sku">${eq.brand} · MODEL: ${eq.model} (${eq.units} SET)</div>
            <h3 class="card-title">${name}</h3>
            <p class="card-desc">${feat}</p>
            <div class="spec-pill-list">
              <span class="spec-pill">行程/範圍: ${eq.work_range}</span>
              <span class="spec-pill">數量: ${eq.units} 台</span>
            </div>
            <div class="card-footer-actions">
              <button type="button" class="btn btn-sm btn-tts" onclick="window.LaiYiApp.speakEquipment('${eq.id}')">${t("btn.listen")}</button>
              <button type="button" class="btn btn-sm btn-primary" onclick="window.LaiYiApp.navigateTo('calculator')">試算此機台加工</button>
            </div>
          </div>
        </div>
      `;
    }).join("");

    if (tbody) {
      tbody.innerHTML = STATE.equipment.map((eq) => `
        <tr>
          <td style="font-weight:800;color:var(--accent-primary);">${eq.brand}</td>
          <td style="font-weight:700;color:var(--text-main);">${eq.name[currentLang] || eq.name["zh-TW"]}</td>
          <td style="font-family:monospace;">${eq.work_range}</td>
          <td><span class="spec-pill">${eq.accuracy}</span></td>
          <td style="font-weight:700;">${eq.units} 台/套</td>
        </tr>
      `).join("");
    }
  }

  // ==========================================================================
  // Smart CNC Spec Calculator & 2D Worktable SVG Nesting Visualizer
  // ==========================================================================
  function renderCalculatorMaterialOptions() {
    const sel = document.getElementById("calc-material");
    if (!sel) return;
    const prev = sel.value || "mat-aluminum";
    sel.innerHTML = STATE.materials.map((m) =>
      `<option value="${m.id}">${m.name[currentLang] || m.name["zh-TW"]} (${m.grades[0]} / ${m.density}g/cm³)</option>`
    ).join("");
    sel.value = prev;
  }

  function runCalculation() {
    const lEl = document.getElementById("calc-length");
    const wEl = document.getElementById("calc-width");
    const hEl = document.getElementById("calc-height");
    const qEl = document.getElementById("calc-qty");
    const mEl = document.getElementById("calc-material");
    const tolEl = document.getElementById("calc-tolerance");
    const compEl = document.getElementById("calc-complexity");
    const surfEl = document.getElementById("calc-surface");
    if (!lEl || !wEl || !hEl || !qEl || !mEl) return;

    const length = parseFloat(lEl.value) || 280;
    const width = parseFloat(wEl.value) || 180;
    const height = parseFloat(hEl.value) || 45;
    const qty = parseInt(qEl.value, 10) || 10;
    const matId = mEl.value || "mat-aluminum";
    const tolerance = tolEl ? tolEl.value : "±0.005 mm";
    const complexity = compEl ? compEl.value : "medium";
    const surface = surfEl ? surfEl.options[surfEl.selectedIndex].text : "";

    document.getElementById("val-calc-length").textContent = `${length} mm`;
    document.getElementById("val-calc-width").textContent = `${width} mm`;
    document.getElementById("val-calc-height").textContent = `${height} mm`;
    document.getElementById("val-calc-qty").textContent = `${qty} PCS`;

    fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        length, width, height, qty,
        material_id: matId,
        tolerance,
        complexity,
        surface
      })
    })
      .then((r) => r.json())
      .then((res) => {
        if (!res.ok) return;
        const matObj = STATE.materials.find((m) => m.id === matId) || STATE.materials[2];
        lastCalcResult = {
          length, width, height, qty,
          material_name: matObj.name[currentLang] || matObj.name["zh-TW"],
          tolerance, surface,
          ...res
        };
        document.getElementById("res-unit-price").textContent = `NT$ ${res.est_unit_twd.toLocaleString()}`;
        document.getElementById("res-total-price").textContent = `NT$ ${res.est_total_twd.toLocaleString()} (批量折扣 -${res.discount_pct}%)`;
        document.getElementById("res-raw-weight").textContent = `${res.raw_weight_kg} kg`;
        document.getElementById("res-net-weight").textContent = `${res.finished_weight_kg} kg`;
        document.getElementById("res-ship-weight").textContent = `${res.total_shipment_kg} kg`;
        document.getElementById("res-machine").textContent = res.recommended_machine;
        document.getElementById("res-qc").textContent = res.qc_equipment;
        document.getElementById("res-lead-time").textContent = `${res.lead_time_days} Days`;

        drawWorktableNestingSvg(res.table_x, res.table_y, length, width, res.parts_per_setup);
      })
      .catch(() => {});
  }

  function drawWorktableNestingSvg(tableX, tableY, partL, partW, partsPerSetup) {
    const wrap = document.getElementById("blueprint-svg-container");
    if (!wrap) return;
    const svgW = 460;
    const svgH = Math.round(svgW * (tableY / tableX));
    const scaleX = (svgW - 40) / tableX;
    const scaleY = (svgH - 40) / tableY;
    const scale = Math.min(scaleX, scaleY);

    const drawTableW = tableX * scale;
    const drawTableH = tableY * scale;
    const offsetX = (svgW - drawTableW) / 2;
    const offsetY = (svgH - drawTableH) / 2;

    const pW = Math.max(8, partL * scale);
    const pH = Math.max(8, partW * scale);
    const gap = Math.max(3, 15 * scale);

    let rectsHtml = "";
    let count = 0;
    for (let y = offsetY + 8; y + pH <= offsetY + drawTableH - 4 && count < 36; y += pH + gap) {
      for (let x = offsetX + 8; x + pW <= offsetX + drawTableW - 4 && count < 36; x += pW + gap) {
        count++;
        rectsHtml += `
          <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${pW.toFixed(1)}" height="${pH.toFixed(1)}"
                fill="rgba(15, 118, 110, 0.20)" stroke="#0f766e" stroke-width="1.5" rx="3"/>
        `;
      }
    }

    wrap.innerHTML = `
      <svg viewBox="0 0 ${svgW} ${svgH + 28}" width="100%" height="230" style="max-width:480px;margin:0 auto;display:block;">
        <rect x="${offsetX}" y="${offsetY}" width="${drawTableW}" height="${drawTableH}"
              fill="#ecfdf5" stroke="#d97706" stroke-width="2" stroke-dasharray="6,3" rx="6"/>
        ${rectsHtml}
        <text x="${svgW / 2}" y="${svgH + 18}" fill="#35524c" font-size="12" font-weight="600" text-anchor="middle" font-family="monospace">
          CNC Worktable: ${tableX}×${tableY}mm | Workpiece: ${partL}×${partW}mm | ~${partsPerSetup} pcs/setup
        </text>
      </svg>
    `;
  }

  // ==========================================================================
  // FAQ Accordion Renderer (統一按鍵高度)
  // ==========================================================================
  function renderFaqList() {
    const container = document.getElementById("faq-list-container");
    if (!container) return;
    container.innerHTML = STATE.faqs.map((f, i) => {
      const q = f.q[currentLang] || f.q["zh-TW"];
      const a = f.a[currentLang] || f.a["zh-TW"];
      return `
        <div class="tech-card" style="margin-bottom:14px;padding:20px 24px;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;cursor:pointer;"
               onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
            <h3 style="font-size:1.05rem;font-weight:800;color:var(--accent-primary);">Q${i + 1}. ${q}</h3>
            <button type="button" class="btn btn-sm btn-tts" onclick="event.stopPropagation(); window.LaiYiApp.speakRaw(${JSON.stringify(q + ' ' + a).replace(/"/g, '&quot;')})">
              ${t("btn.listen")}
            </button>
          </div>
          <div style="margin-top:12px;color:var(--text-secondary);font-size:0.94rem;border-top:1px solid var(--border-subtle);padding-top:12px;">
            ${a}
          </div>
        </div>
      `;
    }).join("");
  }

  // ==========================================================================
  // Multi-Item RFQ Cart & Submission
  // ==========================================================================
  function updateCartBadge() {
    const badge = document.getElementById("header-rfq-badge");
    if (badge) {
      const totalItems = rfqCart.reduce((acc, item) => acc + (parseInt(item.qty, 10) || 1), 0);
      badge.textContent = rfqCart.length > 0 ? `${rfqCart.length} (${totalItems})` : "0";
    }
  }

  function addProductToRfq(prodId, qty = 1) {
    const p = STATE.products.find((x) => x.id === prodId);
    if (!p) return;
    const existing = rfqCart.find((x) => x.sku === p.sku);
    if (existing) {
      existing.qty = (parseInt(existing.qty, 10) || 1) + qty;
    } else {
      rfqCart.push({
        sku: p.sku,
        name: p.name[currentLang] || p.name["zh-TW"],
        material: p.material_grade,
        dimensions: p.dimensions,
        tolerance: p.tolerance,
        surface: "依標準製程",
        qty: qty
      });
    }
    saveCart();
    showToast(`✅ <strong>${p.name[currentLang] || p.name["zh-TW"]}</strong> ${t("toast.addedRfq")}`);
  }

  function addMaterialToRfq(matId) {
    const m = STATE.materials.find((x) => x.id === matId);
    if (!m) return;
    rfqCart.push({
      sku: `MAT-${m.code}`,
      name: `客製化零件 (${m.name[currentLang] || m.name["zh-TW"]})`,
      material: m.grades[0],
      dimensions: "依上傳工程圖面",
      tolerance: "±0.005 mm",
      surface: (m.surface_treatments[currentLang] || m.surface_treatments["zh-TW"]).split("、")[0],
      qty: 10
    });
    saveCart();
    showToast(`✅ <strong>${m.name[currentLang] || m.name["zh-TW"]}</strong> ${t("toast.addedRfq")}`);
    navigateTo("rfq");
  }

  function addCalculatedSpecToRfq() {
    if (!lastCalcResult) runCalculation();
    const c = lastCalcResult;
    if (!c) return;
    rfqCart.push({
      sku: `CALC-${c.length}x${c.width}x${c.height}`,
      name: `線上試算客製件 (${c.recommended_machine.split(" ")[0]} ${c.recommended_machine.split(" ")[1] || ""})`,
      material: c.material_name,
      dimensions: `${c.length} × ${c.width} × ${c.height} mm`,
      tolerance: c.tolerance,
      surface: c.surface,
      qty: c.qty
    });
    saveCart();
    showToast(`✅ ${t("toast.addedRfq")} (預估單價 NT$ ${c.est_unit_twd.toLocaleString()})`);
    navigateTo("rfq");
  }

  function addCustomRfqRow() {
    rfqCart.push({
      sku: `CUSTOM-${rfqCart.length + 1}`,
      name: "客製化 CNC 銑床/龍門加工件",
      material: "6061-T6 / SUS304 / S45C",
      dimensions: "依工程圖檔",
      tolerance: "±0.005 mm",
      surface: "本色陽極 / 原色",
      qty: 5
    });
    saveCart();
  }

  function removeRfqRow(idx) {
    rfqCart.splice(idx, 1);
    saveCart();
  }

  function updateRfqRowField(idx, field, val) {
    if (!rfqCart[idx]) return;
    rfqCart[idx][field] = field === "qty" ? Math.max(1, parseInt(val, 10) || 1) : val;
    try {
      localStorage.setItem("laiyi_rfq_cart_v1", JSON.stringify(rfqCart));
    } catch (e) {}
    updateCartBadge();
  }

  function renderRfqCartTable() {
    const tbody = document.getElementById("rfq-items-tbody");
    if (!tbody) return;
    if (rfqCart.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">
            目前清單尚無指定品項（可直接於右側上傳工程圖檔送出詢價，或點選上方「＋ 新增自訂加工品項」）。
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = rfqCart.map((item, idx) => `
      <tr>
        <td>
          <input type="text" class="form-input" style="width:100%;height:36px;padding:0 10px;font-size:0.84rem;"
                 value="${item.name.replace(/"/g, '&quot;')}"
                 onchange="window.LaiYiApp.updateRfqRowField(${idx}, 'name', this.value)">
        </td>
        <td>
          <input type="text" class="form-input" style="width:115px;height:36px;padding:0 10px;font-size:0.84rem;"
                 value="${(item.material || '').replace(/"/g, '&quot;')}"
                 onchange="window.LaiYiApp.updateRfqRowField(${idx}, 'material', this.value)">
        </td>
        <td>
          <input type="text" class="form-input" style="width:130px;height:36px;padding:0 10px;font-size:0.84rem;"
                 value="${(item.dimensions || '').replace(/"/g, '&quot;')}"
                 onchange="window.LaiYiApp.updateRfqRowField(${idx}, 'dimensions', this.value)">
        </td>
        <td>
          <input type="text" class="form-input" style="width:92px;height:36px;padding:0 10px;font-size:0.84rem;"
                 value="${(item.tolerance || '±0.005 mm').replace(/"/g, '&quot;')}"
                 onchange="window.LaiYiApp.updateRfqRowField(${idx}, 'tolerance', this.value)">
        </td>
        <td>
          <input type="number" min="1" class="form-input" style="width:72px;height:36px;padding:0 8px;font-size:0.84rem;text-align:right;"
                 value="${item.qty || 1}"
                 onchange="window.LaiYiApp.updateRfqRowField(${idx}, 'qty', this.value)">
        </td>
        <td style="text-align:center;">
          <button type="button" class="btn btn-sm btn-danger" onclick="window.LaiYiApp.removeRfqRow(${idx})">✕</button>
        </td>
      </tr>
    `).join("");
  }

  // ==========================================================================
  // Product Detail Modal (清新亮色與等高按鍵)
  // ==========================================================================
  function openProductModal(prodId) {
    const p = STATE.products.find((x) => x.id === prodId);
    if (!p) return;
    const modal = document.getElementById("product-detail-modal");
    const content = document.getElementById("product-modal-content");
    if (!modal || !content) return;

    const name = p.name[currentLang] || p.name["zh-TW"];
    const desc = p.description[currentLang] || p.description["zh-TW"];

    content.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:start;gap:16px;margin-bottom:18px;">
        <div>
          <span class="eyebrow-tag" style="margin-bottom:6px;">SKU: ${p.sku}</span>
          <h2 style="font-size:1.4rem;font-weight:800;color:var(--text-main);">${name}</h2>
        </div>
        <button type="button" class="btn btn-sm btn-secondary" onclick="document.getElementById('product-detail-modal').classList.remove('open')">✕ 關閉</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center;">
        <div style="border-radius:12px;overflow:hidden;border:1px solid var(--border-subtle);background:var(--bg-soft);">
          <img src="${p.image}" alt="${name}" style="width:100%;height:280px;object-fit:cover;">
        </div>
        <div>
          <p style="color:var(--text-secondary);margin-bottom:16px;font-size:0.95rem;">${desc}</p>
          <table class="precision-table" style="margin-bottom:18px;font-size:0.86rem;">
            <tr><th>適用材質</th><td>${p.material_grade}</td></tr>
            <tr><th>參考尺寸範圍</th><td>${p.dimensions}</td></tr>
            <tr><th>尺寸精度保證</th><td><strong style="color:var(--accent-sun);">${p.tolerance}</strong> (東京精密 3D CMM)</td></tr>
            <tr><th>主力生產機台</th><td>${p.machine_used}</td></tr>
            <tr><th>標準交期 / MOQ</th><td>${p.lead_time_days} 工作天 / 最低 ${p.moq} PCS</td></tr>
          </table>
          <div class="card-footer-actions">
            <button type="button" class="btn btn-tts" onclick="window.LaiYiApp.speakProduct('${p.id}')">${t("btn.listen")}</button>
            <button type="button" class="btn btn-primary" onclick="window.LaiYiApp.addProductToRfq('${p.id}', ${p.moq}); document.getElementById('product-detail-modal').classList.remove('open');">
              ${t("btn.addRfq")}
            </button>
          </div>
        </div>
      </div>
    `;
    modal.classList.add("open");
  }

  // ==========================================================================
  // AI Customer Service Assistant Widget
  // ==========================================================================
  function toggleAiChat() {
    const win = document.getElementById("ai-chat-window");
    if (win) win.classList.toggle("open");
  }

  function sendAiMessage(customText) {
    const input = document.getElementById("ai-chat-input");
    const msgContainer = document.getElementById("ai-chat-messages");
    const text = (customText !== undefined ? customText : (input ? input.value : "")).trim();
    if (!text || !msgContainer) return;
    if (input && customText === undefined) input.value = "";

    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user";
    userBubble.textContent = text;
    msgContainer.appendChild(userBubble);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, lang: currentLang })
    })
      .then((r) => r.json())
      .then((res) => {
        const botBubble = document.createElement("div");
        botBubble.className = "chat-bubble bot";
        const formatted = (res.reply || "").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
        let html = `<div>${formatted}</div>`;
        if (res.action && res.action.route) {
          html += `<div style="margin-top:10px;">
            <button type="button" class="btn btn-sm btn-primary"
                    onclick="window.LaiYiApp.navigateTo('${res.action.route}')">
              ${res.action.label} →
            </button>
          </div>`;
        }
        botBubble.innerHTML = html;
        msgContainer.appendChild(botBubble);
        msgContainer.scrollTop = msgContainer.scrollHeight;
      })
      .catch(() => {});
  }

  // ==========================================================================
  // Event Binding & Initialization
  // ==========================================================================
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-route]").forEach((el) => {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        const r = this.getAttribute("data-route");
        if (r) navigateTo(r, true);
      });
    });

    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        const lang = this.getAttribute("data-lang");
        setLanguage(lang, true);
      });
    });

    document.querySelectorAll("#product-cat-pills .cat-pill").forEach((pill) => {
      pill.addEventListener("click", function () {
        document.querySelectorAll("#product-cat-pills .cat-pill").forEach((p) => p.classList.remove("active"));
        this.classList.add("active");
        selectedCategory = this.getAttribute("data-cat") || "all";
        renderProductsCatalog();
      });
    });

    const matFilterSel = document.getElementById("product-material-filter");
    if (matFilterSel) {
      matFilterSel.addEventListener("change", function () {
        selectedMaterialFilter = this.value;
        renderProductsCatalog();
      });
    }

    const searchInput = document.getElementById("product-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        searchKeyword = this.value;
        renderProductsCatalog();
      });
    }

    document.querySelectorAll("#eq-tab-pills .cat-pill").forEach((pill) => {
      pill.addEventListener("click", function () {
        document.querySelectorAll("#eq-tab-pills .cat-pill").forEach((p) => p.classList.remove("active"));
        this.classList.add("active");
        selectedEqTab = this.getAttribute("data-eqtab") || "all";
        renderEquipmentCatalog();
      });
    });

    ["calc-length", "calc-width", "calc-height", "calc-qty", "calc-material", "calc-tolerance", "calc-complexity", "calc-surface"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", runCalculation);
        el.addEventListener("change", runCalculation);
      }
    });

    const dropzone = document.getElementById("rfq-dropzone");
    const fileInput = document.getElementById("rfq-file-input");
    const fileListEl = document.getElementById("rfq-selected-files");

    function updateSelectedFilesView() {
      if (!fileListEl) return;
      if (uploadedFilesList.length === 0) {
        fileListEl.innerHTML = "";
        return;
      }
      fileListEl.innerHTML = uploadedFilesList.map((f, i) => `
        <div style="display:flex;justify-content:space-between;align-items:center;background:var(--bg-soft);padding:8px 12px;border-radius:8px;margin-top:6px;font-size:0.84rem;border:1px solid var(--border-subtle);">
          <span>📎 ${f.name} (${(f.size / 1024).toFixed(1)} KB)</span>
          <button type="button" class="btn btn-sm btn-danger" style="height:28px;min-height:28px;padding:0 10px;" onclick="window.LaiYiApp.removeUploadFile(${i})">✕</button>
        </div>
      `).join("");
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", () => fileInput.click());
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });
      dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files) {
          Array.from(e.dataTransfer.files).forEach((f) => uploadedFilesList.push(f));
          updateSelectedFilesView();
        }
      });
      fileInput.addEventListener("change", () => {
        if (fileInput.files) {
          Array.from(fileInput.files).forEach((f) => uploadedFilesList.push(f));
          updateSelectedFilesView();
        }
      });
    }

    const rfqForm = document.getElementById("online-rfq-form");
    if (rfqForm) {
      rfqForm.addEventListener("submit", function (ev) {
        ev.preventDefault();
        const submitBtn = document.getElementById("rfq-submit-btn");
        if (submitBtn) submitBtn.disabled = true;

        const fd = new FormData();
        fd.append("company", document.getElementById("rfq-company").value);
        fd.append("contact_name", document.getElementById("rfq-contact-name").value);
        fd.append("country", document.getElementById("rfq-country").value);
        fd.append("phone", document.getElementById("rfq-phone").value);
        fd.append("email", document.getElementById("rfq-email").value);
        fd.append("instant_messenger", document.getElementById("rfq-im").value);
        fd.append("target_delivery", document.getElementById("rfq-delivery").value);
        fd.append("customer_notes", document.getElementById("rfq-notes").value);
        fd.append("lang", currentLang);
        fd.append("items", JSON.stringify(rfqCart));

        uploadedFilesList.forEach((file) => {
          fd.append("files", file);
        });

        fetch("/api/rfq", {
          method: "POST",
          body: fd
        })
          .then((r) => r.json())
          .then((res) => {
            if (submitBtn) submitBtn.disabled = false;
            if (!res.ok) {
              showToast(`⚠️ ${res.error || "提交失敗"}`);
              return;
            }
            rfqCart = [];
            uploadedFilesList = [];
            saveCart();
            updateSelectedFilesView();
            rfqForm.reset();

            const confirmBox = document.getElementById("rfq-success-banner");
            if (confirmBox) {
              confirmBox.style.display = "block";
              confirmBox.innerHTML = `
                <h3 style="color:var(--accent-primary);margin-bottom:6px;">🎉 詢價單提交成功！您的追蹤單號：<span style="font-family:monospace;color:var(--accent-sun);">${res.rfq_id}</span></h3>
                <p style="font-size:0.92rem;color:var(--text-secondary);">系統已透過非同步執行緒寄發通知信與確認信，並自動同步備份至雲端防遺失儲存庫。我們將於 24 小時內與您聯繫！</p>
              `;
            }
            showToast(`🎉 ${t("toast.rfqSubmitted")} (#${res.rfq_id})`);
          })
          .catch(() => {
            if (submitBtn) submitBtn.disabled = false;
            showToast("⚠️ 網路連線異常，請稍後再試");
          });
      });
    }

    setLanguage(currentLang, false);
    navigateTo(currentRoute, false);
    updateCartBadge();

    window.LaiYiApp = {
      navigateTo,
      setLanguage,
      openProductModal,
      addProductToRfq,
      addMaterialToRfq,
      addCalculatedSpecToRfq,
      addCustomRfqRow,
      removeRfqRow,
      updateRfqRowField,
      clearCart: function () {
        rfqCart = [];
        saveCart();
      },
      removeUploadFile: function (idx) {
        uploadedFilesList.splice(idx, 1);
        updateSelectedFilesView();
      },
      filterByMaterial: function (matId) {
        selectedMaterialFilter = matId;
        const sel = document.getElementById("product-material-filter");
        if (sel) sel.value = matId;
        renderProductsCatalog();
        navigateTo("products", true);
      },
      speakCompanyIntro: function () {
        const text = (STATE.company.intro && STATE.company.intro[currentLang]) || STATE.company.intro["zh-TW"];
        speakText(text);
      },
      speakProduct: function (prodId) {
        const p = STATE.products.find((x) => x.id === prodId);
        if (!p) return;
        const text = `${p.name[currentLang] || p.name["zh-TW"]}。${p.description[currentLang] || p.description["zh-TW"]}`;
        speakText(text);
      },
      speakEquipment: function (eqId) {
        const eq = STATE.equipment.find((x) => x.id === eqId);
        if (!eq) return;
        const text = `${eq.name[currentLang] || eq.name["zh-TW"]}。${eq.feature[currentLang] || eq.feature["zh-TW"]}`;
        speakText(text);
      },
      speakRaw: speakText,
      stopTts,
      toggleAiChat,
      sendAiMessage
    };
  });
})();
