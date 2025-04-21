import requests
from datetime import datetime
from data_store import update_market

def fetch_polymarket():
    query = {
        "query": """
        {
            markets(first: 1000, orderBy: volume, orderDirection: desc) {
                id
                question
                volume
                outcomes {
                    name
                    price
                }
            }
        }
        """
    }
    r = requests.post("https://api.thegraph.com/subgraphs/name/polymarket/polymarket", json=query)
    data = r.json()['data']['markets']

    for market in data:
        if not market['outcomes']:
            continue
        avg_price = sum([o['price'] for o in market['outcomes'] if o['price'] is not None]) / len(market['outcomes'])
        update_market(
            market_id=market['id'],
            price=avg_price,
            volume=float(market.get('volume', 0)),
            source='polymarket'
        )

if __name__ == "__main__":
    fetch_polymarket()
