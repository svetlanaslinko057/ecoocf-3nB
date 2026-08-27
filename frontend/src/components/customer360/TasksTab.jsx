/**
 * Customer360 — TasksTab (Sprint 4 + i18n)
 * -----------------------------------------
 * Customer-scoped to-do list. Reuses the global ``db.tasks`` collection
 * via the customer wrapper API; SLA Engine + notifications keep working.
 *
 * Filters: All / Open / Overdue / Done.
 * Quick-toggle status with a click. Inline edit of title + due date.
 *
 * All strings localised to uk / en / bg (admin language set). Russian is
 * NOT supported by the BIBI CRM — historical hardcoded strings removed
 * in 2026-06.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  CheckSquare,
  Square,
  Calendar,
  Plus,
  Trash,
  WarningCircle,
  Clock,
  Flag,
} from '@phosphor-icons/react';
import { useAuth } from '../../App';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const priorityClass = {
  low:      'text-zinc-500',
  medium:   'text-amber-500',
  high:     'text-orange-500',
  critical: 'text-red-500',
};

const T = {
  en: {
    open: 'Open',     overdue: 'Overdue',   done: 'Done',
    all: 'All',       new_task: 'New task', empty: 'No tasks yet. Click "New task" to create one.',
    confirm_delete: 'Delete this task?',
    modal_title: 'New task',
    title: 'Title', description: 'Description', due: 'Due date', priority: 'Priority',
    cancel: 'Cancel', create: 'Create',     created: 'Task created',
    failed_load: 'Failed to load tasks',  failed: 'Failed',
    reopen: 'Reopen', mark_done: 'Mark complete',
    delete: 'Delete', due_label: 'Due',
  },
  bg: {
    open: 'Отворени', overdue: 'Просрочени', done: 'Готови',
    all: 'Всички',    new_task: 'Нова задача', empty: 'Няма задачи. Натиснете „Нова задача“ за създаване.',
    confirm_delete: 'Изтриване на задачата?',
    modal_title: 'Нова задача',
    title: 'Заглавие', description: 'Описание', due: 'Краен срок', priority: 'Приоритет',
    cancel: 'Отказ',  create: 'Създай',      created: 'Задачата е създадена',
    failed_load: 'Грешка при зареждане',  failed: 'Грешка',
    reopen: 'Възобнови', mark_done: 'Маркирай като готова',
    delete: 'Изтрий', due_label: 'Срок',
  },
  uk: {
    open: 'Відкриті', overdue: 'Прострочені', done: 'Виконано',
    all: 'Усі',       new_task: 'Нова задача', empty: 'Задач немає. Натисніть «Нова задача» для створення.',
    confirm_delete: 'Видалити задачу?',
    modal_title: 'Нова задача',
    title: 'Назва',   description: 'Опис',   due: 'Дедлайн', priority: 'Пріоритет',
    cancel: 'Скасувати', create: 'Створити', created: 'Задачу створено',
    failed_load: 'Не вдалося завантажити задачі', failed: 'Помилка',
    reopen: 'Відновити', mark_done: 'Позначити як виконану',
    delete: 'Видалити', due_label: 'Дедлайн',
  },
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString(); } catch { return ''; }
};

const TasksTab = ({ customerId }) => {
  const { user } = useAuth();
  const { lang } = useLang();
  const t = T[lang] || T.en;

  const FILTERS = useMemo(() => [
    { key: 'all',     label: t.all },
    { key: 'open',    label: t.open },
    { key: 'overdue', label: t.overdue },
    { key: 'done',    label: t.done },
  ], [t]);

  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({ open: 0, completed: 0, overdue: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/customers/${customerId}/tasks`, { headers: authHeaders() });
      setItems(res.data?.items || []);
      setSummary(res.data?.summary || { open: 0, completed: 0, overdue: 0 });
    } catch (e) {
      toast.error(e.response?.data?.detail || t.failed_load);
    } finally {
      setLoading(false);
    }
  }, [customerId, t.failed_load]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/tasks`, { headers: authHeaders() });
        if (!cancelled) {
          setItems(res.data?.items || []);
          setSummary(res.data?.summary || { open: 0, completed: 0, overdue: 0 });
        }
      } catch (e) {
        if (!cancelled) toast.error(e.response?.data?.detail || t.failed_load);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId, t.failed_load]);

  const toggle = async (task) => {
    const next = (task.status || '').toLowerCase() === 'completed' ? 'pending' : 'completed';
    try {
      await axios.patch(
        `${API_URL}/api/customers/${customerId}/tasks/${task.id || task.taskId}`,
        { status: next },
        { headers: authHeaders() },
      );
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t.failed);
    }
  };

  const remove = async (task) => {
    if (!window.confirm(t.confirm_delete)) return;
    try {
      await axios.delete(`${API_URL}/api/customers/${customerId}/tasks/${task.id || task.taskId}`, { headers: authHeaders() });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t.failed);
    }
  };

  const filtered = useMemo(() => {
    return items.filter((tt) => {
      const st = (tt.status || '').toLowerCase();
      if (filter === 'open')    return st === 'pending' || st === 'in_progress';
      if (filter === 'overdue') return !!tt.overdue;
      if (filter === 'done')    return st === 'completed';
      return true;
    });
  }, [items, filter]);

  if (loading) return <div className="flex items-center justify-center h-32" data-testid="tasks-loading"><div className="animate-spin w-7 h-7 border-2 border-[#4F46E5] border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-4" data-testid="customer360-tasks-tab">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-zinc-500">{t.open}: <span className="font-bold text-zinc-900">{summary.open}</span></span>
          <span className="text-red-500">{t.overdue}: <span className="font-bold">{summary.overdue}</span></span>
          <span className="text-emerald-600">{t.done}: <span className="font-bold">{summary.completed}</span></span>
        </div>
        <button onClick={() => setShowNew(true)} className="inline-flex items-center gap-2 px-3 py-2 bg-[#18181B] text-white rounded-xl hover:bg-[#27272A] text-sm font-medium" data-testid="task-new-btn">
          <Plus size={14} weight="bold" /> {t.new_task}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${filter === f.key ? 'bg-[#18181B] text-white border-[#18181B]' : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50'}`}
            data-testid={`tasks-filter-${f.key}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="section-card text-center py-12" data-testid="tasks-empty">
          <CheckSquare size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">{t.empty}</p>
        </div>
      )}

      <div className="space-y-2">
        {filtered.map((tk) => {
          const done = (tk.status || '').toLowerCase() === 'completed';
          return (
            <div key={tk.id || tk.taskId} className={`section-card flex items-start gap-3 ${tk.overdue && !done ? 'border-l-4 border-red-400' : ''}`} data-testid={`task-row-${tk.id || tk.taskId}`}>
              <button onClick={() => toggle(tk)} className="shrink-0 mt-0.5" title={done ? t.reopen : t.mark_done}>
                {done ? <CheckSquare size={20} weight="fill" className="text-emerald-500" /> : <Square size={20} className="text-zinc-300 hover:text-zinc-500" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`font-medium text-sm ${done ? 'line-through text-zinc-400' : 'text-zinc-900'}`}>{tk.title}</span>
                  {tk.priority && tk.priority !== 'medium' && (
                    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold ${priorityClass[tk.priority] || 'text-zinc-400'}`}>
                      <Flag size={10} weight="fill" /> {tk.priority}
                    </span>
                  )}
                  {tk.overdue && !done && (
                    <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 border border-red-200 font-bold uppercase">
                      <WarningCircle size={10} weight="fill" /> {t.overdue}
                    </span>
                  )}
                </div>
                {tk.description && <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{tk.description}</p>}
                <div className="mt-2 flex items-center gap-3 text-[11px] text-zinc-500">
                  {tk.dueDate && (
                    <span className="inline-flex items-center gap-1">
                      <Calendar size={11} /> {t.due_label}: {fmtDate(tk.dueDate)}
                    </span>
                  )}
                  {tk.assigneeName && (
                    <span className="inline-flex items-center gap-1">
                      <Clock size={11} /> {tk.assigneeName}
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => remove(tk)} className="shrink-0 p-1.5 hover:bg-red-50 rounded-md" title={t.delete}>
                <Trash size={14} className="text-red-400" />
              </button>
            </div>
          );
        })}
      </div>

      {showNew && (
        <NewTaskModal customerId={customerId} onClose={() => setShowNew(false)} onCreated={() => { setShowNew(false); load(); }} t={t} />
      )}
    </div>
  );
};

const NewTaskModal = ({ customerId, onClose, onCreated, t }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [priority, setPriority] = useState('medium');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const ttl = title.trim();
    if (!ttl) return;
    setSaving(true);
    try {
      await axios.post(
        `${API_URL}/api/customers/${customerId}/tasks`,
        {
          title: ttl,
          description: description.trim() || undefined,
          dueDate: dueDate || undefined,
          priority,
        },
        { headers: authHeaders() },
      );
      toast.success(t.created);
      onCreated?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || t.failed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="task-new-modal">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-zinc-900 mb-4">{t.modal_title}</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{t.title}</label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" autoFocus data-testid="task-title-input" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{t.description}</label>
            <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{t.due}</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{t.priority}</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg">{t.cancel}</button>
          <button onClick={submit} disabled={saving || !title.trim()} className="px-4 py-2 bg-[#18181B] text-white text-sm rounded-lg hover:bg-[#27272A] disabled:opacity-50" data-testid="task-save-btn">
            {saving ? '…' : t.create}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TasksTab;
