import { useEffect, useState } from 'react'
import './App.css'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

function credentialsValid() {
  return (
    SUPABASE_URL &&
    SUPABASE_ANON_KEY &&
    !SUPABASE_URL.includes('your-project') &&
    !SUPABASE_ANON_KEY.includes('your-project')
  )
}

async function api(path) {
  if (!credentialsValid()) throw new Error('Supabase credentials missing')
  const res = await fetch(`${SUPABASE_URL}${path}`, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${SUPABASE_ANON_KEY}` },
    mode: 'cors'
  })
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`)
  return res.json()
}

function App() {
  const [rows, setRows] = useState([])
  const [sortKey, setSortKey] = useState('volume24h')
  const [sortDir, setSortDir] = useState('desc')
  const [filter, setFilter] = useState('all')
  const [category, setCategory] = useState('all')
  const categories = ['economics', 'politics', 'sports']
  const [error, setError] = useState('')

  useEffect(() => {
    if (!credentialsValid()) {
      setError('Supabase credentials missing')
      setRows([])
      return
    }
    loadMarkets()
  }, [sortKey, sortDir])

  async function loadMarkets() {
    setError('')
    if (!credentialsValid()) {
      setError('Supabase credentials missing')
      setRows([])
      return
    }
    try {
      const now = new Date().toISOString()
      const marketsRaw = await api(
        `/rest/v1/latest_snapshots` +
        `?select=market_id,source,market_name,expiration,tags,volume` +
        `&order=volume.desc&limit=500`
      )
      const markets = marketsRaw.filter(m => !m.expiration || m.expiration > now)
      console.log('Market data from Supabase:', markets.slice(0, 3))

      if (!markets.length) throw new Error('No active markets')

      const idList = markets.map(m => `'${m.market_id}'`).join(',')
      const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString()

      const outcomes = await api(
        `/rest/v1/market_outcomes` +
        `?select=market_id,outcome_name,price,volume,timestamp` +
        `&market_id=in.(${idList})&order=timestamp.desc`
      )

      const latest = {}
      outcomes.forEach(o => {
        const key = `${o.market_id}|${o.outcome_name}`
        if (!latest[key]) latest[key] = o
      })

      const prevRows = await api(
        `/rest/v1/market_outcomes` +
        `?select=market_id,outcome_name,price` +
        `&market_id=in.(${idList})&timestamp=lt.${since}&order=timestamp.desc`
      )

      const prevPrice = {}
      prevRows.forEach(p => {
        const key = `${p.market_id}|${p.outcome_name}`
        if (!prevPrice[key]) prevPrice[key] = p.price
      })

      const grouped = {}
      Object.values(latest).forEach(o => {
        o.price24h = prevPrice[`${o.market_id}|${o.outcome_name}`]
        if (o.price != null && o.price24h != null) {
          o.changePct = ((o.price - o.price24h) * 100).toFixed(2)
        } else {
          o.changePct = null
        }
        ;(grouped[o.market_id] ||= []).push(o)
      })

      const final = markets.map(m => {
        const outs = grouped[m.market_id] || []
        outs.sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
        const top = outs[0] || {}
        return {
          market_id: m.market_id,
          market_name: m.market_name,
          source: m.source.startsWith('polymarket') ? 'polymarket' : m.source,
          expiration: m.expiration,
          tags: m.tags,
          volume24h: top.volume,
          topOutcome: top.outcome_name,
          price: top.price,
          changePct: top.changePct,
          outcomes: outs
        }
      })

      setRows(final)
    } catch (err) {
      console.error(err)
      setError('Failed to load market data.')
      setRows([])
    }
  }

  const displayed = rows
    .filter(r => filter === 'all' || r.source === filter)
    .filter(r =>
      category === 'all' || (r.tags || []).map(t => t.toLowerCase()).includes(category)
    )
    .sort((a, b) => {
      const va = a[sortKey] ?? -Infinity
      const vb = b[sortKey] ?? -Infinity
      return sortDir === 'desc' ? vb - va : va - vb
    })

  return (
    <div className="App">
      <h1>Prediction Pulse: Top Markets</h1>
      <div className="filters">
        <button
          onClick={() => setFilter('all')}
          className={filter === 'all' ? 'active' : ''}
        >
          All
        </button>
        <button
          onClick={() => setFilter('kalshi')}
          className={filter === 'kalshi' ? 'active' : ''}
        >
          Kalshi
        </button>
        <button
          onClick={() => setFilter('polymarket')}
          className={filter === 'polymarket' ? 'active' : ''}
        >
          Polymarket
        </button>
      </div>
      <div className="categories">
        <button onClick={() => setCategory('all')} className={category === 'all' ? 'active' : ''}>
          All
        </button>
        {categories.map(c => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={category === c ? 'active' : ''}
          >
            {c.charAt(0).toUpperCase() + c.slice(1)}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {!rows.length && !error && <p style={{ color: 'gray' }}>Loading...</p>}
      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th
                onClick={() => toggleSort('market_name')}
                data-sort="market_name"
              >
                Market{' '}
                {sortKey === 'market_name' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th>Top Outcome</th>
              <th onClick={() => toggleSort('price')} data-sort="price">
                Price {sortKey === 'price' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th onClick={() => toggleSort('changePct')} data-sort="changePct">
                24h Change{' '}
                {sortKey === 'changePct' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th onClick={() => toggleSort('volume24h')} data-sort="volume24h">
                24h Volume{' '}
                {sortKey === 'volume24h' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th onClick={() => toggleSort('expiration')} data-sort="expiration">
                End Date{' '}
                {sortKey === 'expiration' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map(row => (
              <>
                <tr key={row.market_id} className="market-row">
                  <td>{row.market_name || row.market_id}</td>
                  <td>{row.topOutcome || '—'}</td>
                  <td>{row.price == null ? '—' : `${(row.price * 100).toFixed(1)}%`}</td>
                  <td>{row.changePct == null ? '—' : `${row.changePct}%`}</td>
                  <td>{row.volume24h == null ? '—' : row.volume24h.toLocaleString()}</td>
                  <td>{row.expiration ? new Date(row.expiration).toLocaleDateString() : '—'}</td>
                  <td>{(row.tags || []).join(', ')}</td>
                </tr>
                {row.outcomes.slice(1).map(o => (
                  <tr key={`${row.market_id}-${o.outcome_name}`} className="outcome-row">
                    <td></td>
                    <td>{o.outcome_name}</td>
                    <td>{o.price == null ? '—' : `${(o.price * 100).toFixed(1)}%`}</td>
                    <td>{o.changePct == null ? '—' : `${o.changePct}%`}</td>
                    <td>{o.volume == null ? '—' : o.volume.toLocaleString()}</td>
                    <td colSpan="3"></td>
                  </tr>
                ))}
              </>
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
