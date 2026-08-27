// ActivityPage — Phase D1.5 Slice 2. Full-page universal activity stream.
import React from "react";
import { Activity } from "lucide-react";
import ActivityFeed from "@/components/unified/ActivityFeed";

export default function ActivityPage() {
  return (
    <div className="space-y-5" data-testid="activity-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-800">
          <Activity className="h-6 w-6 text-[#0E5E3A]" /> Стрічка активності
        </h1>
        <p className="mt-1 text-sm text-slate-400">Усі події платформи: CRM · Відходи · Операції · Контент · SEO · Документи</p>
      </div>
      <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
        <ActivityFeed limit={60} />
      </div>
    </div>
  );
}
