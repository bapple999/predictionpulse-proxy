// Import Supabase credentials from config.js (not committed to git)
import { SUPABASE_URL, SUPABASE_KEY } from "./config.js";

let chart, sortKey = "volume", sortDir = "desc";

function api(path) {
  if (!SUPABASE_URL || !SUPABASE_KEY || SUPABASE_URL.includes("YOUR_PROJECT")) {
    return Promise.reject(
      new Error(
        "Supabase credentials missing. Copy public/config.example.js to public/config.js and set your project URL and anon key."
      )
    );
  }
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
    let rows = await api(
      `/rest/v1/latest_snapshots` +
      `?select=market_id,source,price,volume,timestamp,market_name,event_name,expiration,summary` +
      `&limit=1000`
    );

    rows = rows.filter(r => (r.volume || 0) > 0);
    rows.sort((a, b) => (b.volume || 0) - (a.volume || 0));

    if (!rows.length) throw new Error("No rows after filter");

    const idList = rows.map(r => `'${r.market_id}'`).join(",");
    const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

    const prevRows = await api(
      `/rest/v1/market_snapshots?select=market_id,price` +
      `&market_id=in.(${idList})&timestamp=gt.${since}` +
      `&order=timestamp.desc`
    );

    const prevPrice = {};
    prevRows.forEach(p => (prevPrice[p.market_id] ??= p.price));

    const deduped = Object.values(rows.reduce((acc, r) => {
      acc[r.market_id] = r;
      return acc;
    }, {}));

    deduped.forEach(r => {
      r.cleanPrice = r.price != null && r.price >= 0 && r.price <= 1 ? r.price : null;
      r.price24h = prevPrice[r.market_id];
      r.changePct =
        r.cleanPrice != null && r.price24h != null
          ? ((r.cleanPrice - r.price24h) * 100).toFixed(2)
          : null;
      r.cleanSource = r.source.startsWith("polymarket") ? "polymarket" : r.source;
    });

    renderTable(deduped);
  } catch (err) {
    console.error(err);
    document.getElementById("emptyMessage").style.display = "block";
  }
}

function renderTable(rows) {
  const tbody = document.getElementById("marketTable");
  tbody.innerHTML = "";

  rows.sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    if (typeof va === "string" || typeof vb === "string") {
      const cmp = String(va).localeCompare(String(vb));
      return sortDir === "desc" ? -cmp : cmp;
    }
    const numA = va ?? -Infinity;
    const numB = vb ?? -Infinity;
    return sortDir === "desc" ? numB - numA : numA - numB;
  });

  rows.forEach(r => {
    const priceDisp = r.cleanPrice == null ? "—" : `${(r.cleanPrice * 100).toFixed(1)}%`;
    const changeDisp = r.changePct == null ? "—" : `${r.changePct}%`;
    const arrow = r.changePct == null ? "" : r.changePct.startsWith("-") ? "⬇️" : "⬆️";

    const rowHtml = `
      <tr class="event-section" data-source="${r.cleanSource}" data-market-id="${r.market_id}">
        <td>${r.market_name || r.market_id}</td>
        <td>${r.cleanSource}</td>
        <td>${priceDisp}</td>
        <td>${r.volume == null ? "—" : `$${Number(r.volume).toLocaleString()}`}</td>
        <td>${r.expiration ? new Date(r.expiration).toLocaleDateString() : "—"}</td>
        <td>${arrow} ${changeDisp}</td>
        <td>${r.summary ? r.summary : "—"}</td>
      </tr>`;

    tbody.insertAdjacentHTML("beforeend", rowHtml);
    tbody.lastElementChild.onclick = () =>
      drawChart(r.market_id, r.market_name || r.market_id);
  });
}

async function drawChart(marketId, label) {
  const rows = await api(
    `/rest/v1/market_snapshots?select=timestamp,price&market_id=eq.${marketId}&order=timestamp.asc`
  );

  const labels = rows.map(r => new Date(r.timestamp).toLocaleString());
  const data = rows.map(r => r.price == null ? null : (r.price * 100).toFixed(2));

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels,
      datasets: [{ label: `Price Trend – ${label}`, data, borderColor: "blue", fill: false }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } },
      scales: { y: { beginAtZero: true, max: 100 } }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();

  document.querySelectorAll(".filters button").forEach(btn => {
    btn.onclick = () => {
      const f = btn.dataset.filter;
      document.querySelectorAll("tbody tr.event-section").forEach(row => {
        row.style.display = f === "all" || row.dataset.source === f ? "" : "none";
      });
    };
  });

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
