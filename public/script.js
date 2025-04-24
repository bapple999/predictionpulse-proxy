const SUPABASE_URL = "https://oedvfgnnheevwhpubvzf.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9lZHZmZ25uaGVldndocHVidnpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2ODM4MDYsImV4cCI6MjA2MDI1OTgwNn0.xWP63veWq8vWtMvpLwQw8kx0IACs0QBIVzqQYW9wviw"; // safe to use in frontend

async function loadMarkets() {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/market_snapshots?select=market_id,source,price,volume,timestamp&order=timestamp.desc&limit=20`, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    }
  });

  const data = await res.json();
  const table = document.getElementById("marketTable");
  table.innerHTML = "";

  data.forEach(market => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${market.market_id}</td>
      <td>${market.source}</td>
      <td>${market.price.toFixed(2)}</td>
      <td>${market.volume.toLocaleString()}</td>
      <td>${new Date(market.timestamp).toLocaleString()}</td>
    `;
    table.appendChild(row);
  });
}

loadMarkets();
