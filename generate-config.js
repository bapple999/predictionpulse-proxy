const fs = require('fs');
const path = require('path');

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_KEY;

if (!url || !key) {
  console.error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_KEY');
  process.exit(1);
}

const outDir = path.join(__dirname, 'webapp', 'public');
fs.mkdirSync(outDir, { recursive: true });

const content = `export const SUPABASE_URL = ${JSON.stringify(url)};\nexport const SUPABASE_KEY = ${JSON.stringify(key)};\n`;
fs.writeFileSync(path.join(outDir, 'config.js'), content);
console.log('Wrote', path.join(outDir, 'config.js'));

