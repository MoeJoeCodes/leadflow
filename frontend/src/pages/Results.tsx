import React, { useState, useEffect } from 'react';
import { Users, Mail, Phone, ExternalLink, RefreshCw } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { Badge } from '../components/ui/Badge';

export default function Results() {
  const [leads, setLeads] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchLeads = async () => {
    setIsLoading(true);
    try {
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/leads`);
      const data = await res.json();
      setLeads(data);
    } catch (error) {
      console.error("Error fetching leads", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Lead Manager</h1>
          <p className="text-slate-400">View and filter your extracted Instagram data.</p>
        </div>
        <button onClick={fetchLeads} disabled={isLoading} className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg transition-colors">
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh Data
        </button>
      </div>

      <GlassCard className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                <th className="p-4 text-sm font-medium text-slate-300">Profile</th>
                <th className="p-4 text-sm font-medium text-slate-300">Status</th>
                <th className="p-4 text-sm font-medium text-slate-300">Contact</th>
                <th className="p-4 text-sm font-medium text-slate-300">Followers</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-slate-400">
                    No leads found. Go to the Scraper Command to start a job.
                  </td>
                </tr>
              ) : (
                leads.map((lead, index) => (
                  <tr key={index} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400">
                          <Users className="w-5 h-5" />
                        </div>
                        <div>
                          <a href={`https://instagram.com/${lead.username}`} target="_blank" rel="noreferrer" className="text-white font-medium hover:text-cyan-400 flex items-center gap-1">
                            @{lead.username} <ExternalLink className="w-3 h-3" />
                          </a>
                          <p className="text-xs text-slate-400 w-48 truncate">{lead.bio || "No bio available"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      {lead.is_business ? (
                        <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Business</Badge>
                      ) : (
                        <Badge className="bg-slate-500/10 text-slate-400 border border-slate-500/20">Personal</Badge>
                      )}
                    </td>
                    <td className="p-4 space-y-1">
                      {lead.email && <div className="text-sm text-slate-300 flex items-center gap-2"><Mail className="w-3 h-3" /> {lead.email}</div>}
                      {lead.phone && <div className="text-sm text-slate-300 flex items-center gap-2"><Phone className="w-3 h-3" /> {lead.phone}</div>}
                      {!lead.email && !lead.phone && <span className="text-xs text-slate-500">N/A</span>}
                    </td>
                    <td className="p-4 text-sm text-slate-300">
                      {lead.followers ? lead.followers.toLocaleString() : "N/A"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}