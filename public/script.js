// script.js – grouped event market view with robust guards

const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
// Public anon key (safe for client‑side)
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw";

let chart;

async function loadMarkets() {
  const url = `${SUPABASE_URL}/rest/v1/market_snapshots?select=market_id,source,price,volume,timestamp,markets!inner(market_name,event_name,expiration)&order=timestamp.desc&limit=500`;
  const res = await fetch(url, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    },
    mode: "cors"
  });
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    },
    mode: "cors"
  });

  const data = await res.json();
  if (!data.length) {
    document.getElementById("emptyMessage").style.display = "block";
    return;
  }

  // ───── group rows by event (fallbacks ensure no "Other" spam) ─────
  const grouped = data.reduce((acc, entry) => {
    const grp = entry.markets?.event_name || entry.markets?.market_name || entry.market_id.slice(0, 8);
    (acc[grp] ||= []).push(entry);
    return acc;
  }, {});

  const table = document.getElementById("marketTable");
  table.innerHTML = "";

  for (const [eventName, entries] of Object.entries(grouped)) {
    const sectionId = eventName.replace(/\s+/g, "-").toLowerCase();

    // event header row with toggle
    table.insertAdjacentHTML("beforeend", `
      <tr>
        <td colspan="6">
          <button class="toggle-btn" data-target="${sectionId}" style="margin-right:.5em;">➖</button>
          <strong>${eventName}</strong>
        </td>
      </tr>`);

    // group snapshots by individual market
    const byMarket = groupBy(entries, "market_id");

    for (const [mid, snaps] of Object.entries(byMarket)) {
      const latest   = snaps[0];
      const previous = snaps.find(s => hoursAgo(s.timestamp, 24));

      const price        = latest.price;
      const priceDisplay = price == null ? "—" : `${(price * 100).toFixed(1)}%`;

      const price24h   = previous?.price ?? null;
      const changePct  = price != null && price24h != null ? ((price - price24h) * 100).toFixed(2) : null;
      const priceChange= changePct == null ? "—" : `${changePct}%`;
      const trendArrow = changePct == null ? "" : changePct.startsWith("-") ? "⬇️" : "⬆️";

      const marketName = latest.markets?.market_name || mid;
      const expiration = latest.markets?.expiration ? new Date(latest.markets.expiration).toLocaleDateString() : "—";
      const volumeStr  = latest.volume == null ? "—" : `$${Number(latest.volume).toLocaleString()}`;

      table.insertAdjacentHTML("beforeend", `
        <tr class="event-section group-${sectionId}" data-source="${latest.source}" data-market-id="${mid}">
          <td>${marketName}</td>
          <td>${latest.source}</td>
          <td>${priceDisplay}</td>
          <td>${volumeStr}</td>
          <td>${expiration}</td>
          <td>${trendArrow} ${priceChange}</td>
        </tr>`);

      // click to draw trend chart
      table.lastElementChild.onclick = () => drawChart(snaps.slice().reverse(), marketName);
    }
  }

  // ─── toggle expand/collapse ───
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.onclick = () => {
      const tgt = btn.dataset.target;
      const rows = document.querySelectorAll(`.group-${tgt}`);
      const collapsed = btn.textContent === "➕";
      rows.forEach(r => r.style.display = collapsed ? "" : "none");
      btn.textContent = collapsed ? "➖" : "➕";
    };
  });
}

function hoursAgo(ts, hrs) {
  return Date.now() - new Date(ts).getTime() >= hrs * 3600 * 1000;
}

function groupBy(arr, key) {
  return arr.reduce((acc, obj) => {
    (acc[obj[key]] ||= []).push(obj);
    return acc;
  }, {});
}

function drawChart(entries, label) {
  const ctx = document.getElementById("trendChart").getContext("2d");
  const labels = entries.map(e => new Date(e.timestamp).toLocaleString());
  const data   = entries.map(e => e.price == null ? null : (e.price * 100).toFixed(2));
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets:[{ label:`Price Trend – ${label}`, data, borderColor:"blue", fill:false }] },
    options:{ responsive:true, plugins:{ legend:{display:true} }, scales:{ y:{ beginAtZero:true, max:100 } } }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();
  document.querySelectorAll(".filters button").forEach(btn => btn.onclick = () => {
    const filter = btn.dataset.filter;
    document.querySelectorAll("tbody tr.event-section").forEach(row => {
      row.style.display = filter === "all" || row.dataset.source === filter ? "" : "none";
    });
  });
});
