import { useMemo, useState } from 'react'
import './App.css'

const SAMPLE_ROWS = [
  {
    event_id: 'E1',
    title: 'US Presidential Election 2024',
    source: 'kalshi',
    category: 'politics',
    outcome_name: 'Trump',
    last_price: 0.55,
    price_24h: 0.53,
    dollar_volume: 100000
  },
  {
    event_id: 'E1',
    title: 'US Presidential Election 2024',
    source: 'kalshi',
    category: 'politics',
    outcome_name: 'Biden',
    last_price: 0.4,
    price_24h: 0.42,
    dollar_volume: 75000
  },
  {
    event_id: 'E2',
    title: 'Bitcoin above $50k Dec 2025',
    source: 'polymarket',
    category: 'crypto',
    outcome_name: 'Yes',
    last_price: 0.65,
    price_24h: 0.6,
    dollar_volume: 50000
  },
  {
    event_id: 'E2',
    title: 'Bitcoin above $50k Dec 2025',
    source: 'polymarket',
    category: 'crypto',
    outcome_name: 'No',
    last_price: 0.35,
    price_24h: 0.4,
    dollar_volume: 25000
  },
  {
    event_id: 'E3',
    title: 'Will CPI exceed 4% in 2025?',
    source: 'kalshi',
    category: 'economics',
    outcome_name: 'Yes',
    last_price: 0.25,
    price_24h: 0.3,
    dollar_volume: 15000
  },
  {
    event_id: 'E3',
    title: 'Will CPI exceed 4% in 2025?',
    source: 'kalshi',
    category: 'economics',
    outcome_name: 'No',
    last_price: 0.75,
    price_24h: 0.7,
    dollar_volume: 15000
  }
]

function groupRows(rows) {
  const grouped = {}
  rows.forEach(r => {
    const g = grouped[r.event_id] || {
      event_id: r.event_id,
      title: r.title,
      source: r.source,
      category: r.category,
      outcomes: [],
      dollar_volume: 0,
      price: null,
      change: null
    }

    const change =
      r.last_price != null && r.price_24h != null
        ? (r.last_price - r.price_24h) * 100
        : null

    g.outcomes.push({
      name: r.outcome_name,
      last_price: r.last_price,
      price_24h: r.price_24h,
      dollar_volume: r.dollar_volume,
      change
    })
    g.dollar_volume = Math.max(g.dollar_volume, r.dollar_volume ?? 0)
    grouped[r.event_id] = g
  })

  return Object.values(grouped).map(g => {
    g.outcomes.sort((a, b) => (b.last_price ?? 0) - (a.last_price ?? 0))
    g.price = g.outcomes[0]?.last_price ?? null
    g.change = g.outcomes[0]?.change ?? null
    return g
  })
}

function formatPrice(p) {
  return p == null ? '—' : `${(p * 100).toFixed(2)}%`
}

function formatChange(c) {
  if (c == null) return '—'
  const arrow = c < 0 ? '↓' : '↑'
  return `${arrow} ${Math.abs(c).toFixed(2)}%`
}

export default function App() {
  const events = useMemo(() => groupRows(SAMPLE_ROWS), [])
  const categories = useMemo(
    () => Array.from(new Set(events.map(e => e.category))),
    [events]
  )

  const [sourceFilter, setSourceFilter] = useState('all')
  const [catFilter, setCatFilter] = useState('all')
  const [sortKey, setSortKey] = useState('dollar_volume')
  const [sortDir, setSortDir] = useState('desc')

  const filtered = events.filter(e => {
    const matchSource = sourceFilter === 'all' || e.source === sourceFilter
    const matchCat = catFilter === 'all' || e.category === catFilter
    return matchSource && matchCat
  })

  const sorted = [...filtered].sort((a, b) => {
    const va = a[sortKey] ?? -Infinity
    const vb = b[sortKey] ?? -Infinity
    return sortDir === 'desc' ? vb - va : va - vb
  })

  const toggleSort = key => {
    setSortDir(prev => (sortKey === key && prev === 'desc' ? 'asc' : 'desc'))
    setSortKey(key)
  }

  return (
    <div id="rootInner">
      <h1>Prediction Markets</h1>
      <div className="filters">
        <label>
          Source:
          <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="kalshi">Kalshi</option>
            <option value="polymarket">Polymarket</option>
          </select>
        </label>
        <label>
          Category:
          <select value={catFilter} onChange={e => setCatFilter(e.target.value)}>
            <option value="all">All</option>
            {categories.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <table className="market-table">
        <thead>
          <tr>
            <th>Event</th>
            <th>Outcome</th>
            <th onClick={() => toggleSort('price')} data-sort="price">Price</th>
            <th onClick={() => toggleSort('change')} data-sort="change">24h Change</th>
            <th onClick={() => toggleSort('dollar_volume')} data-sort="dollar_volume">Dollar Volume</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(ev => (
            <>
              {ev.outcomes.map((o, idx) => (
                <tr key={`${ev.event_id}-${o.name}`}> 
                  {idx === 0 ? (
                    <td rowSpan={ev.outcomes.length}>{ev.title}</td>
                  ) : null}
                  <td>{o.name}</td>
                  <td>{formatPrice(o.last_price)}</td>
                  <td>{formatChange(o.change)}</td>
                  <td>{o.dollar_volume.toLocaleString()}</td>
                  {idx === 0 ? (
                    <td rowSpan={ev.outcomes.length}>{ev.source}</td>
                  ) : null}
                </tr>
              ))}
            </>
          ))}
        </tbody>
      </table>
      <div className="cards">
        {sorted.map(ev => (
          <div key={ev.event_id} className="card">
            <div className="card-header">
              <span>{ev.title}</span>
              <span>{ev.source}</span>
            </div>
            {ev.outcomes.map(o => (
              <div key={o.name} className="card-outcome">
                <span>{o.name}</span>
                <span>{formatPrice(o.last_price)}</span>
                <span>{formatChange(o.change)}</span>
                <span>{o.dollar_volume.toLocaleString()}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

