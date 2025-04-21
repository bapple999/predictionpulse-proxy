from datetime import datetime, timedelta

market_data = {}
market_24h = {}

def update_market(market_id, price, volume, source):
    now = datetime.utcnow()
    market_data[market_id] = {
        "price": price,
        "volume": volume,
        "source": source,
        "timestamp": now
    }

    if market_id not in market_24h or now - market_24h[market_id]['timestamp'] > timedelta(hours=24):
        market_24h[market_id] = {
            "price": price,
            "timestamp": now
        }

def get_top_movers(limit=10):
    movers = []
    for market_id in market_data:
        if market_id in market_24h:
            price_now = market_data[market_id]['price']
            price_then = market_24h[market_id]['price']
            change = ((price_now - price_then) / price_then) * 100 if price_then != 0 else 0
            movers.append({
                "market_id": market_id,
                "price": price_now,
                "volume": market_data[market_id]['volume'],
                "source": market_data[market_id]['source'],
                "change_24h": round(change, 2)
            })
    return sorted(movers, key=lambda x: abs(x['change_24h']), reverse=True)[:limit]

def get_all_markets():
    return market_data
