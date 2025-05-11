// script.js – grouped event market view with toggles

const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
// Public anon key (safe for client‑side)
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw";

let chart;

async function loadMarkets() {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/market_snapshots?select=market_id,source,price,volume,timestamp,markets(market_name,event_name,expiration)&order=timestamp.desc&limit=1000`, {
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

  const grouped = data.reduce((acc, entry) => {
    const group = entry.markets?.event_name || "Other";
    if (!acc[group]) acc[group] = [];
    acc[group].push(entry);
    return acc;
  }, {});

  const tableContainer = document.getElementById("marketTable");
  tableContainer.innerHTML = "";

  for (const [eventName, entries] of Object.entries(grouped)) {
    const sectionId = eventName.replace(/\s+/g, '-').toLowerCase();

    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `
      <td colspan="6">
        <button class="toggle-btn" data-target="${sectionId}" style="margin-right: 0.5em;">➖</button>
        <strong>${eventName}</strong>
      </td>`;
    tableContainer.appendChild(headerRow);

    const byMarket = groupBy(entries, 'market_id');

    for (const [marketId, snapshots] of Object.entries(byMarket)) {
      const latest = snapshots[0];
      const previous = snapshots.find(e => hoursAgo(e.timestamp, 24));

      const price = latest.price;
      const priceDisplay = price !== null ? `${(price * 100).toFixed(1)}%` : "-";

      const price24h = previous?.price ?? null;
      const priceChange = price !== null && price24h !== null ? ((price - price24h) * 100).toFixed(2) + "%" : "—";
      const trendArrow = priceChange.includes("-") ? "⬇️" : priceChange === "—" ? "" : "⬆️";

      const marketName = latest.markets?.market_name || marketId;
      const expiration = latest.markets?.expiration ? new Date(latest.markets.expiration).toLocaleDateString() : "—";
      const volume = latest.volume ? `$${Number(latest.volume).toLocaleString()}` : "$0";

      const row = document.createElement("tr");
      row.classList.add("event-section", `group-${sectionId}`);
      row.innerHTML = `
        <td>${marketName}</td>
        <td>${latest.source}</td>
        <td>${priceDisplay}</td>
        <td>${volume}</td>
        <td>${expiration}</td>
        <td>${trendArrow} ${priceChange}</td>
      `;
      row.dataset.source = latest.source;
      row.dataset.marketId = marketId;

      row.addEventListener("click", () => drawChart(snapshots.slice().reverse(), marketName));
      tableContainer.appendChild(row);
    }
  }

  // Toggle expand / collapse
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      const rows = document.querySelectorAll(`.group-${target}`);
      const collapsed = btn.textContent === "➕";
      rows.forEach(r => r.style.display = collapsed ? "" : "none");
      btn.textContent = collapsed ? "➖" : "➕";
    });
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
  const data   = entries.map(e => e.price !== null ? (e.price * 100).toFixed(2) : null);
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ label: `Price Trend – ${label}`, data, borderColor: "blue", fill: false }] },
    options: { responsive: true, plugins:{ legend:{ display:true } }, scales:{ y:{ beginAtZero:true, max:100 } } }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();
  document.querySelectorAll(".filters button").forEach(btn => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      document.querySelectorAll("tbody tr").forEach(row => {
        row.style.display = filter === "all" || row.dataset.source === filter ? "" : "none";
      });
    });
  });
});
