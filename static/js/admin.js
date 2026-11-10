/* ==========================================================================
   錸億精密工業有限公司 (LAI YI Precision Industrial Co., Ltd.)
   Admin CRM & Cloud Persistence Management Console Script
   (清新自然・安南區色系 & 嚴格統一按鍵規格)
   ========================================================================== */

(function () {
  "use strict";

  let adminToken = localStorage.getItem("laiyi_admin_token") || "";
  let allRfqs = [];
  let selectedStatusFilter = "all";

  const STATUS_LABELS = {
    pending: "待處理",
    reviewing: "評估報價中",
    quoted: "已報價",
    won: "已成交/生產中",
    archived: "已結案"
  };

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
    }, 3600);
  }

  function authHeaders() {
    return {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken
    };
  }

  function loadRfqs() {
    fetch("/api/admin/rfqs", { headers: authHeaders() })
      .then((r) => {
        if (r.status === 401) {
          showLoginScreen();
          throw new Error("Unauthorized");
        }
        return r.json();
      })
      .then((res) => {
        if (!res.ok) return;
        showDashboardScreen();
        allRfqs = res.rfqs || [];
        const s = res.stats || {};
        document.getElementById("kpi-total").textContent = s.total || 0;
        document.getElementById("kpi-pending").textContent = s.pending || 0;
        document.getElementById("kpi-reviewing").textContent = s.reviewing || 0;
        document.getElementById("kpi-quoted").textContent = s.quoted || 0;
        document.getElementById("kpi-won").textContent = s.won || 0;

        if (res.cloud_status) {
          document.getElementById("cloud-status-text").textContent = res.cloud_status.last_backup_status || "Ready";
          document.getElementById("cloud-last-backup").textContent = res.cloud_status.last_backup_time || "尚未推送";
          document.getElementById("cloud-last-restore").textContent = res.cloud_status.last_restore_time || "系統啟動自動檢查";
        }
        renderTable();
      })
      .catch(() => {});
  }

  function loadSettings() {
    fetch("/api/admin/settings", { headers: authHeaders() })
      .then((r) => r.json())
      .then((res) => {
        if (!res.ok || !res.settings) return;
        const st = res.settings;
        document.getElementById("set-smtp-enabled").checked = !!st.smtp_enabled;
        document.getElementById("set-smtp-host").value = st.smtp_host || "smtp.gmail.com";
        document.getElementById("set-smtp-port").value = st.smtp_port || 587;
        document.getElementById("set-smtp-sender-name").value = st.smtp_sender_name || "";
        document.getElementById("set-smtp-user").value = st.smtp_user || "";
        document.getElementById("set-smtp-password").value = st.smtp_password || "";
        document.getElementById("set-admin-email").value = st.admin_notify_email || "";

        document.getElementById("set-gh-enabled").checked = !!st.github_backup_enabled;
        document.getElementById("set-gh-repo").value = st.github_repo || "";
        document.getElementById("set-gh-token").value = st.github_token || "";
        document.getElementById("set-gh-branch").value = st.github_branch || "cloud-backup";
        document.getElementById("set-db-url").value = st.database_url || "";
        document.getElementById("set-gsheets-url").value = st.google_sheets_webhook || "";

        document.getElementById("cloud-status-text").textContent = st.last_backup_status || "Ready";
        document.getElementById("cloud-last-backup").textContent = st.last_backup_time || "尚未推送";
        document.getElementById("cloud-last-restore").textContent = st.last_restore_time || "系統啟動自動檢查";
      })
      .catch(() => {});
  }

  function showLoginScreen() {
    document.getElementById("admin-login-view").style.display = "block";
    document.getElementById("admin-dashboard-view").style.display = "none";
    document.getElementById("admin-logout-btn").style.display = "none";
  }

  function showDashboardScreen() {
    document.getElementById("admin-login-view").style.display = "none";
    document.getElementById("admin-dashboard-view").style.display = "block";
    document.getElementById("admin-logout-btn").style.display = "inline-flex";
  }

  function renderTable() {
    const tbody = document.getElementById("admin-rfq-tbody");
    if (!tbody) return;
    const kw = (document.getElementById("admin-search-input")?.value || "").trim().toLowerCase();

    const filtered = allRfqs.filter((r) => {
      if (selectedStatusFilter !== "all" && r.status !== selectedStatusFilter) return false;
      if (kw) {
        const hay = JSON.stringify(r).toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--text-muted);">找不到符合條件的詢價單紀錄</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map((r) => {
      const itemsHtml = (r.items || []).map((i) =>
        `<div style="margin-bottom:4px;">• <strong>${i.name}</strong> (${i.material || '-'}) × <strong style="color:var(--accent-primary);">${i.qty}</strong></div>`
      ).join("");

      const attHtml = (r.attachments && r.attachments.length > 0)
        ? r.attachments.map((a) =>
            `<a href="/api/admin/uploads/${encodeURIComponent(a.stored_name)}?download=1" target="_blank"
                style="display:inline-block;background:var(--bg-soft);border:1px solid #b7dbd0;color:var(--accent-primary);padding:3px 8px;border-radius:6px;font-size:0.76rem;margin:2px;font-weight:700;">
               📎 ${a.original_name} (${a.size_kb}KB)
             </a>`
          ).join("")
        : `<span style="color:var(--text-muted);font-size:0.8rem;">無附件</span>`;

      return `
        <tr>
          <td>
            <strong style="color:var(--text-main);font-family:monospace;">${r.id}</strong>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px;">${r.created_at}</div>
          </td>
          <td>
            <span class="status-badge status-${r.status || 'pending'}">${STATUS_LABELS[r.status] || r.status}</span>
          </td>
          <td>
            <strong style="color:var(--text-main);">${r.company}</strong>
            <div style="font-size:0.82rem;color:var(--text-secondary);">${r.contact_name} (${r.country || 'TW'})</div>
          </td>
          <td style="font-size:0.82rem;">
            <div>📞 ${r.phone || '-'}</div>
            <div>✉️ <a href="mailto:${r.email}" style="color:var(--accent-primary);font-weight:700;">${r.email || '-'}</a></div>
            ${r.instant_messenger ? `<div style="color:var(--accent-emerald);">💬 ${r.instant_messenger}</div>` : ""}
          </td>
          <td style="font-size:0.82rem;max-width:280px;">${itemsHtml}</td>
          <td>${attHtml}</td>
          <td style="max-width:220px;font-size:0.82rem;color:var(--accent-sun);font-weight:600;">${r.admin_notes || '<span style="color:var(--text-muted);font-weight:normal;">尚未填寫備註</span>'}</td>
          <td style="text-align:center;">
            <div class="admin-action-group">
              <button type="button" class="btn btn-sm btn-primary" onclick="window.AdminCRM.openModal('${r.id}')">檢視/編輯</button>
              <button type="button" class="btn btn-sm btn-danger" onclick="window.AdminCRM.deleteRfq('${r.id}')">刪除</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  function openModal(rfqId) {
    const r = allRfqs.find((x) => x.id === rfqId);
    if (!r) return;
    const modal = document.getElementById("admin-rfq-modal");
    const body = document.getElementById("admin-rfq-modal-body");

    const itemsRows = (r.items || []).map((i, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td style="font-weight:700;color:var(--text-main);">${i.name}</td>
        <td>${i.material || '-'}</td>
        <td>${i.dimensions || '-'}</td>
        <td>${i.tolerance || '±0.005 mm'}</td>
        <td style="font-weight:700;color:var(--accent-primary);">${i.qty}</td>
      </tr>
    `).join("");

    const attLinks = (r.attachments && r.attachments.length > 0)
      ? r.attachments.map((a) => `
          <a href="/api/admin/uploads/${encodeURIComponent(a.stored_name)}?download=1" target="_blank" class="btn btn-sm btn-secondary">
            📥 下載 ${a.original_name} (${a.size_kb} KB)
          </a>
        `).join(" ")
      : `<span style="color:var(--text-muted);">此詢價單未上傳附件</span>`;

    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <div>
          <span class="eyebrow-tag" style="margin-bottom:4px;">${r.id} · 建立於 ${r.created_at}</span>
          <h2 style="font-size:1.35rem;color:var(--text-main);">${r.company} — ${r.contact_name}</h2>
        </div>
        <button type="button" class="btn btn-sm btn-secondary" onclick="document.getElementById('admin-rfq-modal').classList.remove('open')">✕ 關閉</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;background:var(--bg-soft);padding:16px;border-radius:10px;margin-bottom:18px;font-size:0.88rem;border:1px solid #b7dbd0;">
        <div>📞 <strong>聯絡電話</strong>：${r.phone || '-'}</div>
        <div>✉️ <strong>電子信箱</strong>：${r.email || '-'}</div>
        <div>🌍 <strong>國家/地區</strong>：${r.country || '-'}</div>
        <div>💬 <strong>通訊軟體</strong>：${r.instant_messenger || '-'}</div>
        <div>📅 <strong>期望交期</strong>：${r.target_delivery || '未指定'}</div>
        <div>📨 <strong>郵件通知紀錄</strong>：<span style="color:var(--accent-emerald);font-weight:700;">${r.email_status || '-'}</span></div>
      </div>

      <h3 style="font-size:1rem;color:var(--accent-primary);margin-bottom:8px;">詢價品項明細</h3>
      <div class="table-responsive" style="margin-bottom:16px;">
        <table class="precision-table" style="font-size:0.84rem;">
          <thead>
            <tr><th>#</th><th>品項名稱</th><th>材質規格</th><th>尺寸</th><th>公差</th><th>數量</th></tr>
          </thead>
          <tbody>${itemsRows}</tbody>
        </table>
      </div>

      <div style="margin-bottom:16px;">
        <h3 style="font-size:0.95rem;color:var(--text-main);margin-bottom:6px;">客戶專案需求與備註</h3>
        <div style="background:var(--bg-deep);padding:12px;border-radius:8px;border:1px solid var(--border-subtle);font-size:0.88rem;">
          ${r.customer_notes || '無特殊備註'}
        </div>
      </div>

      <div style="margin-bottom:18px;">
        <h3 style="font-size:0.95rem;color:var(--text-main);margin-bottom:8px;">客戶上傳工程圖檔 / 附件下載</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">${attLinks}</div>
      </div>

      <hr style="border:none;border-top:1px solid var(--border-subtle);margin:18px 0;">

      <div style="display:grid;grid-template-columns:220px 1fr;gap:14px;align-items:start;">
        <div>
          <label style="display:block;font-size:0.84rem;margin-bottom:6px;color:var(--accent-sun);font-weight:700;">修改處理狀態</label>
          <select id="modal-rfq-status" class="form-select" style="width:100%;">
            <option value="pending" ${r.status === 'pending' ? 'selected' : ''}>待處理 (Pending)</option>
            <option value="reviewing" ${r.status === 'reviewing' ? 'selected' : ''}>評估報價中 (Reviewing)</option>
            <option value="quoted" ${r.status === 'quoted' ? 'selected' : ''}>已報價 (Quoted)</option>
            <option value="won" ${r.status === 'won' ? 'selected' : ''}>已成交/生產中 (Won)</option>
            <option value="archived" ${r.status === 'archived' ? 'selected' : ''}>已結案 (Archived)</option>
          </select>
        </div>
        <div>
          <label style="display:block;font-size:0.84rem;margin-bottom:6px;color:var(--accent-sun);font-weight:700;">業務內部備註 / 報價單號紀錄</label>
          <textarea id="modal-rfq-notes" rows="3" class="form-textarea" style="width:100%;" placeholder="輸入機台排程評估、報價金額或內部追蹤事項...">${r.admin_notes || ''}</textarea>
        </div>
      </div>

      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:18px;">
        <button type="button" class="btn btn-sm btn-secondary" onclick="document.getElementById('admin-rfq-modal').classList.remove('open')">取消</button>
        <button type="button" class="btn btn-sm btn-primary" onclick="window.AdminCRM.saveRfqUpdate('${r.id}')">💾 儲存狀態與備註</button>
      </div>
    `;
    modal.classList.add("open");
  }

  function saveRfqUpdate(rfqId) {
    const status = document.getElementById("modal-rfq-status").value;
    const admin_notes = document.getElementById("modal-rfq-notes").value;

    fetch(`/api/admin/rfqs/${encodeURIComponent(rfqId)}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ status, admin_notes })
    })
      .then((r) => r.json())
      .then((res) => {
        if (!res.ok) {
          showToast(`⚠️ ${res.error || '更新失敗'}`);
          return;
        }
        document.getElementById("admin-rfq-modal").classList.remove("open");
        showToast(`✅ 已更新詢價單 ${rfqId} 並觸發雲端備份！`);
        loadRfqs();
      });
  }

  function deleteRfq(rfqId) {
    if (!confirm(`確定要刪除詢價單號 ${rfqId} 嗎？此操作將同步更新雲端資料。`)) return;
    fetch(`/api/admin/rfqs/${encodeURIComponent(rfqId)}`, {
      method: "DELETE",
      headers: authHeaders()
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.ok) {
          showToast(`🗑️ 已刪除詢價單 ${rfqId}`);
          loadRfqs();
        }
      });
  }

  function saveSettings() {
    const payload = {
      smtp_enabled: document.getElementById("set-smtp-enabled").checked,
      smtp_host: document.getElementById("set-smtp-host").value.trim(),
      smtp_port: parseInt(document.getElementById("set-smtp-port").value, 10) || 587,
      smtp_sender_name: document.getElementById("set-smtp-sender-name").value.trim(),
      smtp_user: document.getElementById("set-smtp-user").value.trim(),
      smtp_password: document.getElementById("set-smtp-password").value.trim(),
      admin_notify_email: document.getElementById("set-admin-email").value.trim(),
      github_backup_enabled: document.getElementById("set-gh-enabled").checked,
      github_repo: document.getElementById("set-gh-repo").value.trim(),
      github_token: document.getElementById("set-gh-token").value.trim(),
      github_branch: document.getElementById("set-gh-branch").value.trim() || "cloud-backup",
      database_url: document.getElementById("set-db-url").value.trim(),
      google_sheets_webhook: document.getElementById("set-gsheets-url").value.trim()
    };

    fetch("/api/admin/settings", {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.ok) {
          showToast("✅ 郵件通知與雲端防遺失設定已成功儲存！");
        } else {
          showToast(`⚠️ ${res.error || "儲存失敗"}`);
        }
      });
  }

  function sendTestEmail() {
    showToast("📨 正在嘗試連線 SMTP 並發送測試信...");
    fetch("/api/admin/test-email", {
      method: "POST",
      headers: authHeaders()
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.ok) {
          showToast(`✅ ${res.message}`);
        } else {
          showToast(`⚠️ ${res.error}`);
        }
      });
  }

  function triggerCloudAction(action) {
    showToast(action === "restore" ? "📥 正在從 GitHub cloud-backup 分支還原資料..." : "☁️ 正在推送備份至 GitHub cloud-backup 分支 ([skip ci])...");
    fetch("/api/admin/cloud-backup", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ action })
    })
      .then((r) => r.json())
      .then((res) => {
        showToast(res.ok ? `✅ ${res.message}` : `⚠️ ${res.message}`);
        loadRfqs();
        loadSettings();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("admin-login-form");
    if (loginForm) {
      loginForm.addEventListener("submit", function (ev) {
        ev.preventDefault();
        const password = document.getElementById("admin-password-input").value;
        fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password })
        })
          .then((r) => r.json())
          .then((res) => {
            if (!res.ok) {
              showToast(`⚠️ ${res.error || "密碼錯誤"}`);
              return;
            }
            adminToken = res.token;
            localStorage.setItem("laiyi_admin_token", adminToken);
            showToast("🔓 HMAC 安全驗證通過，歡迎進入管理後台！");
            loadRfqs();
            loadSettings();
          });
      });
    }

    document.querySelectorAll("#admin-status-pills .cat-pill").forEach((pill) => {
      pill.addEventListener("click", function () {
        document.querySelectorAll("#admin-status-pills .cat-pill").forEach((p) => p.classList.remove("active"));
        this.classList.add("active");
        selectedStatusFilter = this.getAttribute("data-status") || "all";
        renderTable();
      });
    });

    loadRfqs();
    loadSettings();

    window.AdminCRM = {
      loadRfqs,
      renderTable,
      openModal,
      saveRfqUpdate,
      deleteRfq,
      saveSettings,
      sendTestEmail,
      triggerCloudAction,
      switchTab: function (tab) {
        document.getElementById("admin-tab-rfqs").style.display = tab === "rfqs" ? "block" : "none";
        document.getElementById("admin-tab-settings").style.display = tab === "settings" ? "block" : "none";
        document.getElementById("tab-btn-rfqs").classList.toggle("active", tab === "rfqs");
        document.getElementById("tab-btn-settings").classList.toggle("active", tab === "settings");
      },
      exportCsv: function () {
        window.location.href = "/api/admin/export-csv";
      },
      logout: function () {
        localStorage.removeItem("laiyi_admin_token");
        adminToken = "";
        fetch("/api/admin/logout", { method: "POST" }).finally(() => showLoginScreen());
      }
    };
  });
})();
