import React, { useEffect, useState, useCallback } from "react";
import { Camera, CheckCircle2, AlertTriangle, Upload, Loader2 } from "lucide-react";
import { FilesAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

/**
 * PickupPhotoChecklist — Wave 5B-v2 photo workflow.
 *
 * Renders the five required/optional photo stages of a Pickup
 *   before_loading / after_loading / container / transport / signed_act
 * with a per-stage uploader and a top-level "can close?" indicator.
 *
 * Backed by:
 *   GET  /api/waste/pickups/{id}/photo-checklist
 *   POST /api/storage/files  (with photo_stage + pickup_id form fields)
 */
export default function PickupPhotoChecklist({ pickupId, companyId, onUploaded }) {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyStage, setBusyStage] = useState(null);

  const load = useCallback(async () => {
    if (!pickupId) return;
    setLoading(true);
    try {
      const r = await FilesAPI.pickupChecklist(pickupId);
      setState(r);
    } catch (e) {
      toast.error("Не вдалося завантажити чеклист фото");
    } finally {
      setLoading(false);
    }
  }, [pickupId]);

  useEffect(() => { load(); }, [load]);

  const upload = async (stage, file) => {
    if (!file) return;
    setBusyStage(stage);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("purpose", "photo");
      fd.append("photo_stage", stage);
      fd.append("pickup_id", pickupId);
      if (companyId) fd.append("company_id", companyId);
      const r = await FilesAPI.upload(fd);
      toast.success(`Фото додано: ${stage}`);
      onUploaded && onUploaded(r.file);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося завантажити");
    } finally {
      setBusyStage(null);
    }
  };

  if (loading) return <div className="h-24 animate-pulse rounded-xl bg-slate-100" data-testid="pickup-checklist-loading" />;
  if (!state) return null;

  const ok = state.can_close;

  return (
    <div className="rounded-xl border border-emerald-100 bg-white" data-testid="pickup-photo-checklist">
      <div className={`flex items-center justify-between gap-2 rounded-t-xl border-b px-4 py-3 ${ok ? "bg-emerald-50 border-emerald-100" : "bg-amber-50 border-amber-100"}`}>
        <div className="flex items-center gap-2">
          {ok ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertTriangle className="h-5 w-5 text-amber-600" />}
          <div>
            <div className="text-sm font-semibold text-slate-900">
              {ok ? "Вивіз можна закривати" : "Не вистачає обов'язкових фото"}
            </div>
            <div className="text-xs text-slate-600">
              {ok ? "Усі вимоги чеклисту виконано." : `Спочатку додайте: ${(state.missing || []).join(", ")}`}
            </div>
          </div>
        </div>
      </div>
      <ul className="grid gap-2 p-3">
        {(state.stages || []).map((s) => (
          <li key={s.key} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2" data-testid={`pickup-stage-${s.key}`}>
            <div className={`flex h-7 w-7 items-center justify-center rounded-full ${s.present ? "bg-emerald-500 text-white" : (s.required ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-400")}`}>
              {s.present ? <CheckCircle2 className="h-4 w-4" /> : <Camera className="h-4 w-4" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                {s.label}
                {s.required && <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">ОБОВ&apos;ЯЗКОВО</span>}
              </div>
              <div className="text-xs text-slate-500">{s.count > 0 ? `${s.count} фото` : "Не додано"}</div>
            </div>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-800">
              {busyStage === s.key ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {busyStage === s.key ? "Завантаження…" : "Додати фото"}
              <input
                type="file" accept="image/*" capture="environment" className="hidden"
                disabled={busyStage === s.key}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(s.key, f); e.target.value = ""; }}
                data-testid={`pickup-stage-upload-${s.key}`}
              />
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
