// script.js – grouped event‑market view, now reading from latest_snapshots

const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
const SUPABASE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw";

let chart;

async function loadMarkets() {
  const url =
    `${SUPABASE_URL}/rest/v1/latest_snapshots` +
    `?select=market_id,source,price,volume,timestamp,` +
    `market_name,event_name,expiration&limit=300`;

  const res = await fetch(url, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    },
    mode: "cors"
  });

  if (!res.ok) {
    console.error("Supabase error →", await res.text());
    document.getElementById("emptyMessage").style.display = "block";
    return;
  }

  const data = await res.json();
  if (data.length === 0) {
    document.getElementById("emptyMessage").style.display = "block";
    return;
  }

  /* ─── group rows by event (fallbacks ensure no giant “Other”) ─── */
  const grouped = data.reduce((acc, row) => {
    const key =
      row.event_name ||
      row.market_name ||
      row.market_id.slice(0, 8);
    (acc[key] ||= []).push(row);
    return acc;
  }, {});

  const table = document.getElementById("marketTable");
  table.innerHTML = "";

  for (const [eventName, rows] of Object.entries(grouped)) {
    const sectionId = eventName.replace(/\s+/g, "-").toLowerCase();

    /* event header row with toggle */
    table.insertAdjacentHTML(
      "beforeend",
      `<tr>
         <td colspan="6">
           <button class="toggle-btn" data-target="${sectionId}" style="margin-right:.5em;">➖</button>
           <strong>${eventName}</strong>
         </td>
       </tr>`
    );

    /* rows are already “latest per market” */
    rows.forEach(r => {
      const priceDisp =
        r.price == null ? "—" : `${(r.price * 100).toFixed(1)}%`;

      table.insertAdjacentHTML(
        "beforeend",
        `<tr class="event-section group-${sectionId}"
             data-source="${r.source}" data-market-id="${r.market_id}">
           <td>${r.market_name || r.market_id}</td>
           <td>${r.source}</td>
           <td>${priceDisp}</td>
           <td>${r.volume == null ? "—" : `$${Number(r.volume).toLocaleString()}`}</td>
           <td>${r.expiration ? new Date(r.expiration).toLocaleDateString() : "—"}</td>
           <td>—</td>
         </tr>`
      );

      /* click row → fetch full history & draw chart */
      table.lastElementChild.onclick = () =>
        drawChart(r.market_id, r.market_name || r.market_id);
    });
  }

  /* expand / collapse groups */
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.onclick = () => {
      const tgt = btn.dataset.target;
      const rows = document.querySelectorAll(`.group-${tgt}`);
      const collapsed = btn.textContent === "➕";
      rows.forEach(r => (r.style.display = collapsed ? "" : "none"));
      btn.textContent = collapsed ? "➖" : "➕";
    };
  });
}

/* fetch full history for a market to populate the trend chart */
async function drawChart(marketId, label) {
  const url =
    `${SUPABASE_URL}/rest/v1/market_snapshots` +
    `?select=timestamp,price&market_id=eq.${marketId}` +
    `&order=timestamp.asc`;

  const res = await fetch(url, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    },
    mode: "cors"
  });

  const rows = await res.json();
  const ctx = document.getElementById("trendChart").getContext("2d");
  const labels = rows.map(r => new Date(r.timestamp).toLocaleString());
  const data   = rows.map(r => r.price == null ? null : (r.price * 100).toFixed(2));

  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ label:`Price Trend – ${label}`, data, borderColor:"blue", fill:false }] },
    options:{ responsive:true, plugins:{ legend:{display:true} },
      scales:{ y:{ beginAtZero:true, max:100 } } }
  });
}

function groupBy(arr, key) {
  return arr.reduce((acc, obj) => {
    (acc[obj[key]] ||= []).push(obj);
    return acc;
  }, {});
}

document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();

  /* simple source filter buttons */
  document.querySelectorAll(".filters button").forEach(btn => {
    btn.onclick = () => {
      const filter = btn.dataset.filter;
      document.querySelectorAll("tbody tr.event-section").forEach(row => {
        row.style.display =
          filter === "all" || row.dataset.source === filter ? "" : "none";
      });
    };
  });
});
