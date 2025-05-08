const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw";

let chart;

async function loadMarkets() {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/market_snapshots?select=market_id,source,price,volume,timestamp,markets(market_name,event_name,expiration)&order=timestamp.desc&limit=1000`, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    }
  });

  const data = await res.json();
  console.log("Fetched data:", data);

  if (!data.length) {
    document.getElementById("emptyMessage").style.display = "block";
    return;
  }

  const table = document.getElementById("marketTable");
  table.innerHTML = "";

  const grouped = groupBy(data, "market_id");

  Object.entries(grouped).forEach(([marketId, entries]) => {
    const latest = entries[0];
    const previous = entries.find(e => hoursAgo(e.timestamp, 24));

    const price = latest.price;
    const priceDisplay = price !== null ? `${(price * 100).toFixed(1)}%` : "-";

    const price24h = previous?.price ?? null;
    const priceChange = price !== null && price24h !== null ? ((price - price24h) * 100).toFixed(2) + "%" : "—";

    const marketName = latest.markets?.event_name || latest.markets?.market_name || marketId;
    const expiration = latest.markets?.expiration ? new Date(latest.markets.expiration).toLocaleDateString() : "—";
    const volume = latest.volume ? `$${Number(latest.volume).toLocaleString()}` : "$0";
    const trendArrow = priceChange.includes("-") ? "⬇️" : priceChange === "—" ? "" : "⬆️";

    const row = document.createElement("tr");
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

    row.addEventListener("click", () => drawChart(entries.slice().reverse(), marketName));
    table.appendChild(row);
  });
}

function hoursAgo(timestamp, hours) {
  const time = new Date(timestamp).getTime();
  const now = Date.now();
  return now - time >= hours * 60 * 60 * 1000;
}

function groupBy(arr, key) {
  return arr.reduce((acc, item) => {
    const k = item[key];
    if (!acc[k]) acc[k] = [];
    acc[k].push(item);
    return acc;
  }, {});
}

function drawChart(entries, label) {
  const ctx = document.getElementById("trendChart").getContext("2d");
  const labels = entries.map(e => new Date(e.timestamp).toLocaleString());
  const data = entries.map(e => e.price !== null ? (e.price * 100).toFixed(2) : null);

  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: `Price Trend – ${label}`,
        data,
        borderColor: "blue",
        fill: false
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } },
      scales: {
        y: { beginAtZero: true, max: 100 }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadMarkets();

  document.querySelectorAll(".filters button").forEach(button => {
    button.addEventListener("click", () => {
      const filter = button.dataset.filter;
      document.querySelectorAll("tbody tr").forEach(row => {
        row.style.display = filter === "all" || row.dataset.source === filter ? "" : "none";
      });
    });
  });
});
