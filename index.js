import express from 'express';
import fetch from 'node-fetch';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.get('/kalshi', async (req, res) => {
  try {
    const response = await fetch('https://trading-api.kalshi.com/trade-api/v2/markets/', {
      headers: {
        Authorization: `Bearer ${process.env.KALSHI_API_KEY}`
      }
    });
    const data = await response.json();
    res.json(data);
  } catch (error) {
    console.error('Error fetching Kalshi data:', error);
    res.status(500).json({ error: 'Failed to fetch Kalshi data' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
