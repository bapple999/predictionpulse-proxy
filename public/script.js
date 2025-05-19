/*  script.js – volume‑ordered table with 24 h change & sortable headers  */

const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
const SUPABASE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw";

let chart, sortKey = "volume", sortDir = "desc";

/* ---------- helper that throws on non‑2xx ---------- */
function api(path) {
  return fetch(`${SUPABASE_URL}${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
    mode: "cors"
  }).then(async res => {
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    return res.json();
  });
}

async function loadMarkets() {
  try {
    /* newest 1 000 latest-rows – NO server-side sort */
    let rows = await api(
      `/rest/v1/latest_snapshots` +
      `?select=market_id,source,price,volume,timestamp,market_name,event_name,expiration` +
      `&limit=1000`
    );

    rows = rows.filter(r => (r.volume || 0) > 0);
    rows.sort((a, b) => (b.volume || 0) - (a.volume || 0));

    /* ----------- one snapshot ≤ 24 h old for change calc ----------- */
    if (!rows.length) throw new Error("No rows after filter");
    const idList = rows.map(r => `'${r.market_id}'`).join(",");
    const since  = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

    const prevRows = await api(
      `/rest/v1/market_snapshots?select=market_id,price` +
      `&market_id=in.(${idList})&timestamp=gt.${since}` +
      `&order=timestamp.desc`
    );

    const prevPrice = {};
    prevRows.forEach(p => (prevPrice[p.market_id] ??= p.price));

    rows.forEach(r => {
      r.cleanPrice = r.price != null && r.price >= 0 && r.price <= 1 ? r.price : null;
      r.price24h   = prevPrice[r.market_id];
      r.changePct =
        r.cleanPrice != null && r.price24h != null
          ? ((r.cleanPrice - r.price24h) * 100).toFixed(2)
          : null;
      r.cleanSource = r.source.startsWith("polymarket") ? "polymarket" : r.source;
    });

    renderTable(rows);
  } catch (err) {
    console.error(err);
    document.getElementById("emptyMessage").style.display = "block";
  }
}

/* ---------- table render ---------- */
function renderTable(rows) {
  const grouped = rows.reduce((acc, r) => {
    const k = r.event_name || r.market_name || r.market_id.slice(0, 8);
    (acc[k] ||= []).push(r);
    return acc;
  }, {});

  const groupArr = Object.entries(grouped).sort((a, b) => {
    const volA = a[1].reduce((s, r) => s + (r.volume || 0), 0);
    const volB = b[1].reduce((s, r) => s + (r.volume || 0), 0);
    return volB - volA;
  });

  const tbody = document.getElementById("marketTable");
  tbody.innerHTML = "";

  groupArr.forEach(([eventName, list]) => {
    list.sort((a, b) => {
      const va = a[sortKey] ?? -Infinity;
      const vb = b[sortKey] ?? -Infinity;
      return sortDir === "desc" ? vb - va : va - vb;
    });

    const secId = eventName.replace(/\s+/g, "-").toLowerCase();

    if (list.length > 1) {
      tbody.insertAdjacentHTML(
        "beforeend",
        `<tr><td colspan="6">
           <button class="toggle-btn" data-target="${secId}" style="margin-right:.5em;">➖</button>
           <strong>${eventName}</strong>
         </td></tr>`
      );
    }

    list.forEach(r => {
      const priceDisp =
        r.cleanPrice == null ? "—" : `${(r.cleanPrice * 100).toFixed(1)}%`;
      const changeDisp =
        r.changePct == null ? "—" : `${r.changePct}%`;
      const arrow =
        r.changePct == null ? "" : r.changePct.startsWith("-") ? "⬇️" : "⬆️";

      tbody.insertAdjacentHTML(
        "beforeend",
        `<tr class="event-section group-${secId}"
             data-source="${r.cleanSource}" data-market-id="${r.market_id}">
           <td>${r.market_name || r.market_id}</td>
           <td>${r.cleanSource}</td>
           <td>${priceDisp}</td>
           <td>${r.volume == null ? "—" : `$${Number(r.volume).toLocaleString()}`}</td>
           <td>${r.expiration ? new Date(r.expiration).toLocaleDateString() : "—"}</td>
           <td>${arrow} ${changeDisp}</td>
         </tr>`
      );

      tbody.lastElementChild.onclick = () =>
        drawChart(r.market_id, r.market_name || r.market_id);
    });
  });

  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.onclick = () => {
      const rows = document.querySelectorAll(`.group-${btn.dataset.target}`);
      const collapsed = btn.textContent === "➕";
      rows.forEach(r => (r.style.display = collapsed ? "" : "none"));
      btn.textContent = collapsed ? "➖" : "➕";
    };
  });
}

/* ---------- history chart ---------- */
async function drawChart(marketId, label) {
  const rows = await api(
    `/rest/v1/market_snapshots?select=timestamp,price&market_id=eq.${marketId}&order=timestamp.asc`
  );

  const labels = rows.map(r => new Date(r.timestamp).toLocaleString());
  const data   = rows.map(r => r.price == null ? null : (r.price * 100).toFixed(2));

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: { labels, datasets: [{ label:`Price Trend – ${label}`, data, borderColor:"blue", fill:false }] },
    options: { responsive:true, plugins:{legend:{display:true}}, scales:{y:{beginAtZero:true,max:100}} }
  });
}

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();

  /* Kalshi / Polymarket filter buttons */
  document.querySelectorAll(".filters button").forEach(btn => {
    btn.onclick = () => {
      const f = btn.dataset.filter;
      document.querySelectorAll("tbody tr.event-section").forEach(row => {
        row.style.display = f === "all" || row.dataset.source === f ? "" : "none";
      });
    };
  });

  /* clickable sort headers */
  document.querySelectorAll("th[data-sort]").forEach(th => {
    th.style.cursor = "pointer";
    th.onclick = () => {
      const key = th.dataset.sort;
      sortDir = sortKey === key && sortDir === "desc" ? "asc" : "desc";
      sortKey = key;
      loadMarkets();
    };
  });
});
