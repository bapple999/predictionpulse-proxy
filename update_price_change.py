import os
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    supabase: Client = create_client(url, key)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    cutoff_iso = cutoff.isoformat()

    # fetch ticker and current_price for all markets
    resp = supabase.table("markets").select("ticker,current_price").execute()
    markets = resp.data or []

    for m in markets:
        ticker = m.get("ticker")
        current = m.get("current_price")
        if ticker is None or current is None:
            continue

        # price recorded as close as possible to 24h ago
        past_resp = (
            supabase.table("market_prices")
            .select("price,timestamp")
            .eq("market_ticker", ticker)
            .gte("timestamp", cutoff_iso)
            .order("timestamp")
            .limit(1)
            .execute()
        )
        past_rows = past_resp.data or []
        if not past_rows:
            continue
        past_price = past_rows[0]["price"]
        if past_price is None:
            continue

        delta = round(current - past_price, 4)
        pct = round(delta / past_price * 100, 2) if past_price else None

        supabase.table("markets").update(
            {"change_24h": delta, "percent_change_24h": pct}
        ).eq("ticker", ticker).execute()


if __name__ == "__main__":
    main()
