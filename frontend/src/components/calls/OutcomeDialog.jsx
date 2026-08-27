// Shared Outcome dialog — fixes a call's result, comment and (optionally)
// the call-back date. Powers the "manager must fill the result before the
// lead can close" workflow. Backend: POST /api/manager/calls/{id}/outcome
import React, { useEffect, useState } from "react";
import { Phone, Clock, User, Save, Sparkles } from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { OUTCOME_OPTIONS, OUTCOME_MAP, durFmt } from "@/lib/callsMeta";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

function toIso(localValue) {
  if (!localValue) return null;
  try { return new Date(localValue).toISOString(); } catch { return null; }
}

export default function OutcomeDialog({ open, onOpenChange, call, onSaved }) {
  const [outcome, setOutcome] = useState("");
  const [note, setNote] = useState("");
  const [callbackAt, setCallbackAt] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setOutcome(call?.outcome || "");
      setNote(call?.outcome_note || "");
      setCallbackAt("");
    }
  }, [open, call]);

  const requiresDate = OUTCOME_MAP[outcome]?.requiresDate;
  const valid = outcome && note.trim() && (!requiresDate || callbackAt);

  const save = async () => {
    if (!outcome || !note.trim()) { toast.error("Вкажіть результат і коментар"); return; }
    if (requiresDate && !callbackAt) { toast.error("Вкажіть дату й час передзвону"); return; }
    const callId = call?.call_id || call?._id || call?.id;
    if (!callId) { toast.error("Немає ідентифікатора дзвінка"); return; }
    setSaving(true);
    try {
      await CrmAPI.saveOutcome(callId, {
        outcome,
        outcome_note: note.trim(),
        callback_at: requiresDate ? toIso(callbackAt) : null,
      });
      toast.success("Результат дзвінка збережено");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти результат");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="outcome-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Phone className="h-5 w-5 text-emerald-600" /> Результат дзвінка</DialogTitle>
          <DialogDescription>Зафіксуйте підсумок розмови — без цього лід не закриється.</DialogDescription>
        </DialogHeader>

        {call && (
          <div className="rounded-xl border border-[hsl(var(--border))] bg-secondary/40 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
              <span className="font-mono font-semibold text-slate-900">{call.from || call.caller_number || "—"}</span>
              {(call.lead?.name || call.lead_name) && (
                <span className="inline-flex items-center gap-1 text-slate-600"><User className="h-3.5 w-3.5" /> {call.lead?.name || call.lead_name}</span>
              )}
              {call.duration ? (
                <span className="inline-flex items-center gap-1 text-slate-500"><Clock className="h-3.5 w-3.5" /> {durFmt(call.duration)}</span>
              ) : null}
            </div>
          </div>
        )}

        <div className="grid gap-4 pt-1">
          <div className="grid gap-1.5">
            <Label>Результат розмови *</Label>
            <Select value={outcome} onValueChange={setOutcome}>
              <SelectTrigger data-testid="outcome-select"><SelectValue placeholder="Оберіть результат" /></SelectTrigger>
              <SelectContent>
                {OUTCOME_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value} data-testid={`outcome-opt-${o.value}`}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {requiresDate && (
            <div className="grid gap-1.5">
              <Label>Коли передзвонити *</Label>
              <Input type="datetime-local" value={callbackAt} onChange={(e) => setCallbackAt(e.target.value)} data-testid="outcome-callback-at" />
            </div>
          )}

          <div className="grid gap-1.5">
            <Label>Коментар *</Label>
            <Textarea
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Про що домовились, наступний крок…"
              data-testid="outcome-note"
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); } }}
            />
            <p className="text-xs text-muted-foreground">Ctrl/⌘ + Enter — швидке збереження</p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={save} disabled={!valid || saving} className="gap-2" data-testid="outcome-save">
            <Save className="h-4 w-4" /> {saving ? "Збереження…" : "Зберегти результат"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
