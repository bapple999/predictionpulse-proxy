import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

export async function fetchLatestSnapshots() {
  const { data, error } = await supabase
    .from('latest_snapshots')
    .select('*')
    .order('volume', { ascending: false })
  console.log('Market data from Supabase:', data)
  if (error) throw error
  return data
}
