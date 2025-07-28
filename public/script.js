// Import Supabase credentials from config.js (not committed to git)
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";
import { Chart } from "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.esm.min.js";

let chart, sortKey = "volume", sortDir = "desc";
let sourceFilter = "all", categoryFilter = "all";

function api(path) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || SUPABASE_URL.includes("YOUR_PROJECT")) {
    return Promise.reject(
      new Error(
        "Supabase credentials missing. Copy public/config.example.js to public/config.js and set your project URL and anon key."
      )
    );
  }
  return fetch(`${SUPABASE_URL}${path}`, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${SUPABASE_ANON_KEY}` },
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
      `?select=market_id,source,price,volume,timestamp,market_name,event_name,expiration,summary,tags` +
      `&limit=1000`
    );

    rows = rows.filter(r => (r.volume || 0) > 0);
    rows.sort((a, b) => (b.volume || 0) - (a.volume || 0));

    if (!rows.length) throw new Error("No rows after filter");

    const MAX_IDS = 200;
    const idList = rows
      .slice(0, MAX_IDS)
      .map(r => `'${encodeURIComponent(r.market_id)}'`)
      .join(",");
    const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

    const prevRows = await api(
      `/rest/v1/market_snapshots?select=market_id,price` +
      `&market_id=in.(${idList})&timestamp=gt.${since}` +
      `&order=timestamp.desc`
    );

    const since7d = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString();

    const prevRows7d = await api(
      `/rest/v1/market_snapshots?select=market_id,price` +
      `&market_id=in.(${idList})&timestamp=gt.${since7d}` +
      `&order=timestamp.desc`
    );

    const prevPrice = {};
    prevRows.forEach(p => (prevPrice[p.market_id] ??= p.price));

    const prevPrice7d = {};
    prevRows7d.forEach(p => (prevPrice7d[p.market_id] ??= p.price));

    const deduped = Object.values(rows.reduce((acc, r) => {
      acc[r.market_id] = r;
      return acc;
    }, {}));
    deduped.sort((a, b) => (b.volume || 0) - (a.volume || 0));
    const top = deduped.slice(0, 25);

    top.forEach(r => {
      r.cleanPrice = r.price != null && r.price >= 0 && r.price <= 1 ? r.price : null;
      r.price24h = prevPrice[r.market_id];
      r.price7d = prevPrice7d[r.market_id];
      r.changePct =
        r.cleanPrice != null && r.price24h != null
          ? ((r.cleanPrice - r.price24h) * 100).toFixed(2)
          : null;
      r.change7dPct =
        r.cleanPrice != null && r.price7d != null
          ? ((r.cleanPrice - r.price7d) * 100).toFixed(2)
          : null;
      r.cleanSource = r.source.startsWith("polymarket") ? "polymarket" : r.source;
    });

    const trendingList = document.getElementById("trendingList");
    trendingList.innerHTML = "";
    const trending = [...top].sort((a, b) => {
      const av = Math.max(Math.abs(Number(a.changePct || 0)), Math.abs(Number(a.change7dPct || 0)));
      const bv = Math.max(Math.abs(Number(b.changePct || 0)), Math.abs(Number(b.change7dPct || 0)));
      return bv - av;
    }).slice(0, 5);

    trending.forEach(r => {
      const use7 = Math.abs(Number(r.change7dPct || 0)) > Math.abs(Number(r.changePct || 0));
      const pct = use7 ? r.change7dPct : r.changePct;
      const label = use7 ? "7d" : "24h";
      const arrow = pct == null ? "" : String(pct).startsWith("-") ? "⬇️" : "⬆️";
      const url = r.cleanSource === "kalshi"
        ? `https://kalshi.com/markets/${r.market_id}`
        : `https://polymarket.com/market/${r.market_id}`;
      trendingList.insertAdjacentHTML(
        "beforeend",
        `<li><a href="${url}" target="_blank">${r.market_name || r.market_id} — ${arrow} ${pct}% (${label})</a></li>`
      );
    });

    renderTable(top);
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
    const change7Disp = r.change7dPct == null ? "—" : `${r.change7dPct}%`;
    const arrow7 = r.change7dPct == null ? "" : r.change7dPct.startsWith("-") ? "⬇️" : "⬆️";
    const url = r.cleanSource === "kalshi"
      ? `https://kalshi.com/markets/${r.market_id}`
      : `https://polymarket.com/market/${r.market_id}`;

    const rowHtml = `
      <tr class="event-section" data-source="${r.cleanSource}" data-tags="${(r.tags || []).join(',').toLowerCase()}" data-market-id="${r.market_id}">
        <td><a href="${url}" target="_blank">${r.market_name || r.market_id}</a></td>
        <td>${r.cleanSource}</td>
        <td>${priceDisp}</td>
        <td>${r.volume == null ? "—" : `$${Number(r.volume).toLocaleString()}`}</td>
        <td>${r.expiration ? new Date(r.expiration).toLocaleDateString() : "—"}</td>
        <td>${arrow} ${changeDisp}</td>
        <td>${arrow7} ${change7Disp}</td>
        <td>${r.summary ? r.summary : "—"}</td>
      </tr>`;

    tbody.insertAdjacentHTML("beforeend", rowHtml);
  });

  applyFilters();
}

function applyFilters() {
  document.querySelectorAll("tbody tr.event-section").forEach(row => {
    const matchSource = sourceFilter === "all" || row.dataset.source === sourceFilter;
    const tags = (row.dataset.tags || "").split(",");
    const matchCat = categoryFilter === "all" || tags.includes(categoryFilter);
    row.style.display = matchSource && matchCat ? "" : "none";
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
    if (btn.dataset.filter) {
      btn.onclick = () => {
        sourceFilter = btn.dataset.filter;
        applyFilters();
      };
    } else if (btn.dataset.cat) {
      btn.onclick = () => {
        categoryFilter = btn.dataset.cat;
        applyFilters();
      };
    }
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
