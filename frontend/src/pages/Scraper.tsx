import React, { useState } from 'react';
import { Play, Loader2 } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';

export default function Scraper() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [isScraping, setIsScraping] = useState(false);

  const handleStartScrape = async () => {
    if (!query) return alert("Please enter some hashtags!");
    setIsScraping(true);
    try {
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      await fetch(`${API_URL}/scrape/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hashtags: [query], limit: 10 })
      });
      alert("Scraper started successfully in the background!");
    } catch (error) {
      alert("Failed to connect to backend. Is main.py running?");
    } finally {
      setIsScraping(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Scraper Command</h1>
        <p className="text-slate-400">Configure and launch your extraction pipelines.</p>
      </div>

      <GlassCard className="p-6 space-y-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Target Hashtags (comma separated)</label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="capetownbusiness, joburg, durban"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Profile Limit per Hashtag</label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
          </div>

          <button
            onClick={handleStartScrape}
            disabled={isScraping}
            className="w-full py-4 flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-medium transition-colors"
          >
            {isScraping ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
            {isScraping ? "Pipeline Running..." : "Launch Scraper Pipeline"}
          </button>
        </div>
      </GlassCard>
    </div>
  );
}