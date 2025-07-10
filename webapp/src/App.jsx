import { useEffect, useState } from 'react'
import './App.css'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

async function api(path) {
  const res = await fetch(`${SUPABASE_URL}${path}`, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${SUPABASE_ANON_KEY}` },
    mode: 'cors'
  })
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`)
  return res.json()
}

function App() {
  const [rows, setRows] = useState([])
  const [sortKey, setSortKey] = useState('volume')
  const [sortDir, setSortDir] = useState('desc')
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState('')

  useEffect(() => {
    loadMarkets()
  }, [sortKey, sortDir])

  async function loadMarkets() {
    setError('')
    try {
      let r = await api(
        `/rest/v1/latest_snapshots?select=market_id,source,price,volume,timestamp,market_name,event_name,expiration&limit=1000`
      )
      r = r.filter(row => (row.volume || 0) > 0)
      r.sort((a, b) => (b.volume || 0) - (a.volume || 0))
      if (!r.length) throw new Error('No rows after filter')
      const idList = r.map(m => `'${m.market_id}'`).join(',')
      const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
      const prev = await api(
        `/rest/v1/market_snapshots?select=market_id,price&market_id=in.(${idList})&timestamp=gt.${since}&order=timestamp.desc`
      )
      const prevPrice = {}
      prev.forEach(p => (prevPrice[p.market_id] ??= p.price))
      const dedup = Object.values(r.reduce((acc, row) => { acc[row.market_id] = row; return acc }, {}))
      dedup.forEach(d => {
        d.cleanPrice = d.price != null && d.price >= 0 && d.price <= 1 ? d.price : null
        d.price24h = prevPrice[d.market_id]
        d.changePct = d.cleanPrice != null && d.price24h != null ? ((d.cleanPrice - d.price24h) * 100).toFixed(2) : null
        d.cleanSource = d.source.startsWith('polymarket') ? 'polymarket' : d.source
      })
      setRows(dedup)
    } catch (err) {
      console.error(err)
      setError('Failed to load market data.')
      setRows([])
    }
  }

  const displayed = rows
    .filter(r => filter === 'all' || r.cleanSource === filter)
    .sort((a, b) => {
      const va = a[sortKey] ?? -Infinity
      const vb = b[sortKey] ?? -Infinity
      return sortDir === 'desc' ? vb - va : va - vb
    })

  return (
    <div className="App">
      <h1>Prediction Pulse: Top Markets</h1>
      <div className="filters">
        <button onClick={() => setFilter('all')}>All</button>
        <button onClick={() => setFilter('kalshi')}>Kalshi</button>
        <button onClick={() => setFilter('polymarket')}>Polymarket</button>
      </div>
      {error && <p className="error">{error}</p>}
      {!rows.length && !error && <p style={{ color: 'gray' }}>Loading...</p>}
      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('market_name')} data-sort="market_name">Market</th>
              <th onClick={() => toggleSort('cleanSource')} data-sort="cleanSource">Source</th>
              <th onClick={() => toggleSort('cleanPrice')} data-sort="cleanPrice">Price</th>
              <th onClick={() => toggleSort('volume')} data-sort="volume">Volume</th>
              <th onClick={() => toggleSort('expiration')} data-sort="expiration">Expiration</th>
              <th onClick={() => toggleSort('changePct')} data-sort="changePct">24h Change</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map(row => (
              <tr key={row.market_id}>
                <td>{row.market_name || row.market_id}</td>
                <td>{row.cleanSource}</td>
                <td>{row.cleanPrice == null ? '—' : `${(row.cleanPrice * 100).toFixed(1)}%`}</td>
                <td>{row.volume == null ? '—' : `$${Number(row.volume).toLocaleString()}`}</td>
                <td>{row.expiration ? new Date(row.expiration).toLocaleDateString() : '—'}</td>
                <td>{row.changePct == null ? '—' : `${row.changePct}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )

  function toggleSort(key) {
    setSortDir(prev => (sortKey === key && prev === 'desc' ? 'asc' : 'desc'))
    setSortKey(key)
  }
}

export default App
