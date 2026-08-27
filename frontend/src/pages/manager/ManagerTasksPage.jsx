/**
 * Manager Tasks Page
 * 
 * /manager/tasks
 * 
 * Features:
 * - 1 active task rule
 * - Task queue with locked status
 * - Start/Complete actions
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useLang, getLocale } from '../../i18n';
import { 
  CheckCircle, 
  Clock, 
  Lock,
  Play,
  Flag,
  CalendarBlank,
  User,
  ArrowRight,
  Warning,
  Sparkle
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import BackButton from '../../components/ui/BackButton';
import Breadcrumb from '../../components/ui/Breadcrumb';
import RoleZoneBadge from '../../components/ui/RoleZoneBadge';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Priority Badge
const PriorityBadge = ({ priority }) => {
  const { t } = useLang();
  const config = {
    low: { color: 'zinc', label: t('priorityLow') },
    medium: { color: 'blue', label: t('priorityMedium') },
    high: { color: 'amber', label: t('priorityHigh') },
    urgent: { color: 'red', label: t('urgent') },
  };
  const { color, label } = config[priority] || config.medium;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-${color}-100 text-${color}-700`}>
      <Flag size={10} weight="fill" />
      {label}
    </span>
  );
};

// Task Card
const TaskCard = ({ task, onStart, onComplete, isLoading }) => {
  const { t } = useLang();
  const isActive = task.isActive;
  const isLocked = task.isLocked;
  const isOverdue = task.dueDate && new Date(task.dueDate) < new Date() && task.status !== 'completed';
  
  return (
    <div 
      className={`bg-white rounded-xl border p-4 transition-all relative
        ${isActive ? 'border-emerald-400 ring-2 ring-emerald-200 shadow-lg' : ''}
        ${isLocked ? 'opacity-60 border-zinc-200' : 'border-zinc-200 hover:shadow-md'}
        ${isOverdue && !isActive ? 'border-red-300 bg-red-50/50' : ''}`}
      data-testid={`task-card-${task.id}`}
    >
      {/* Locked Overlay */}
      {isLocked && (
        <div className="absolute inset-0 bg-zinc-100/50 rounded-xl flex items-center justify-center">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-200 rounded-full text-zinc-600 text-sm">
            <Lock size={14} />
            {t('managerTasksLocked')}
          </div>
        </div>
      )}
      
      {/* Active Badge */}
      {isActive && (
        <div className="absolute -top-2 -right-2 bg-emerald-500 text-white px-2 py-0.5 rounded-full text-xs font-bold flex items-center gap-1">
          <Sparkle size={12} weight="fill" />
          {t('managerTasksActive')}
        </div>
      )}
      
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-medium text-zinc-900">{task.title}</h3>
          {task.description && (
            <p className="text-sm text-zinc-500 mt-1 line-clamp-2">{task.description}</p>
          )}
        </div>
        <PriorityBadge priority={task.priority} />
      </div>
      
      {/* Meta */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500 mb-4">
        {task.dueDate && (
          <span className={`flex items-center gap-1 ${isOverdue ? 'text-red-600 font-medium' : ''}`}>
            <CalendarBlank size={12} />
            {isOverdue && <Warning size={12} />}
            {new Date(task.dueDate).toLocaleDateString(getLocale())}
          </span>
        )}
        {task.relatedEntityType && (
          <span className="flex items-center gap-1">
            <User size={12} />
            {task.relatedEntityType}: {task.relatedEntityId?.slice(0, 8)}...
          </span>
        )}
      </div>
      
      {/* Actions */}
      <div className="flex items-center gap-2">
        {!isActive && !isLocked && task.status === 'todo' && (
          <button
            onClick={() => onStart(task.id)}
            disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            data-testid={`start-task-${task.id}`}
          >
            <Play size={16} weight="fill" />{t('startAction')}</button>
        )}
        
        {isActive && (
          <button
            onClick={() => onComplete(task.id)}
            disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
            data-testid={`complete-task-${task.id}`}
          >
            <CheckCircle size={16} weight="fill" />
            {t('managerTasksComplete')}
          </button>
        )}
        
        {task.status === 'in_progress' && !isActive && (
          <span className="flex-1 text-center py-2 text-amber-600 bg-amber-50 rounded-lg text-sm">
            {t('managerTasksInProgress')}
          </span>
        )}
      </div>
    </div>
  );
};

// Active Task Banner
const ActiveTaskBanner = ({ task, onComplete, isLoading }) => {
  const { t } = useLang();
  if (!task) return null;
  
  return (
    <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-2xl p-6 text-white mb-8 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
      
      <div className="relative">
        <div className="flex items-center gap-2 text-emerald-100 text-sm mb-2">
          <Sparkle size={16} weight="fill" />
          {t('adm_current_task')}
        </div>
        
        <h2 className="text-2xl font-bold mb-2">{task.title}</h2>
        {task.description && (
          <p className="text-emerald-100 mb-4">{task.description}</p>
        )}
        
        <div className="flex items-center gap-4">
          <button
            onClick={() => onComplete(task.id)}
            disabled={isLoading}
            className="flex items-center gap-2 px-6 py-2 bg-white text-emerald-700 rounded-lg hover:bg-emerald-50 transition-colors font-medium disabled:opacity-50"
            data-testid="complete-active-task"
          >
            <CheckCircle size={18} weight="fill" />
            {t('adm_complete_task')}
          </button>
          
          {task.dueDate && (
            <span className="text-emerald-100 flex items-center gap-1">
              <CalendarBlank size={16} />
              {t('r9_to_label')}: {new Date(task.dueDate).toLocaleDateString(getLocale())}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

const ManagerTasksPage = () => {
  const { t } = useLang();
  const [tasks, setTasks] = useState([]);
  const [activeTask, setActiveTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [stats, setStats] = useState(null);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      const [queueRes, activeRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/tasks/queue`, { headers }),
        axios.get(`${API_URL}/api/tasks/active`, { headers }),
        axios.get(`${API_URL}/api/tasks/stats`, { headers }),
      ]);
      
      const tasksData = Array.isArray(queueRes.data) ? queueRes.data : (queueRes.data?.data || queueRes.data?.tasks || []);
      setTasks(tasksData);
      setActiveTask(activeRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
      toast.error(t('tasksLoadError'));
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStart = async (taskId) => {
    setActionLoading(true);
    try {
      await axios.post(`${API_URL}/api/tasks/${taskId}/start`, {}, { headers });
      toast.success(t('taskStarted'));
      fetchData();
    } catch (error) {
      const message = error.response?.data?.message || t('adm3_e1b3e4fa88');
      toast.error(message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async (taskId) => {
    setActionLoading(true);
    try {
      await axios.post(`${API_URL}/api/tasks/${taskId}/complete`, {}, { headers });
      toast.success(t('adm_task_completed'));
      fetchData();
    } catch (error) {
      toast.error(t('taskCompleteError'));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const todoTasks = tasks.filter(t => t.status === 'todo');
  const inProgressTasks = tasks.filter(t => t.status === 'in_progress' && !t.isActive);

  return (
    <div className="space-y-6" data-testid="manager-tasks-page">
      <Breadcrumb items={[
        { label: 'My Workspace', to: '/manager' },
        { label: 'My Tasks' },
      ]} />

      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-zinc-900 mb-2">{t('myTasksPage')}</h1>
        <p className="text-zinc-600">{t('managerTasksFocusSubtitle')}</p>
      </div>

      {/* Shared Tasks zone marker — same `tasks` collection, manager executor viewport */}
      <div className="mb-6">
        <RoleZoneBadge variant="tasks" />
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl border border-zinc-200 p-4">
            <div className="text-sm text-zinc-500">{t('totalCount')}</div>
            <div className="text-2xl font-bold text-zinc-900">{stats.total}</div>
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 p-4">
            <div className="text-sm text-zinc-500">{t('inQueue')}</div>
            <div className="text-2xl font-bold text-blue-600">{stats.byStatus?.todo || 0}</div>
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 p-4">
            <div className="text-sm text-zinc-500">{t('completedShort')}</div>
            <div className="text-2xl font-bold text-emerald-600">{stats.byStatus?.completed || 0}</div>
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 p-4">
            <div className="text-sm text-zinc-500">{t('overdueShort')}</div>
            <div className="text-2xl font-bold text-red-600">{stats.overdue || 0}</div>
          </div>
        </div>
      )}

      {/* Active Task Banner */}
      <ActiveTaskBanner 
        task={activeTask} 
        onComplete={handleComplete}
        isLoading={actionLoading}
      />

      {/* Info Banner (if no active task) */}
      {!activeTask && todoTasks.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-8 flex items-start gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Lock size={20} className="text-blue-600" />
          </div>
          <div>
            <h3 className="font-medium text-blue-900">{t('oneTaskRule')}</h3>
            <p className="text-sm text-blue-700 mt-1">
              {t('managerTasksFocusHint')}
            </p>
          </div>
        </div>
      )}

      {/* Todo Tasks */}
      {todoTasks.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
            <Clock size={20} className="text-blue-500" />
            {t('managerTasksInQueue')} ({todoTasks.length})
          </h2>
          <div className="grid gap-4">
            {todoTasks.map(task => (
              <TaskCard 
                key={task.id} 
                task={task}
                onStart={handleStart}
                onComplete={handleComplete}
                isLoading={actionLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* In Progress (other) */}
      {inProgressTasks.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
            <Play size={20} className="text-amber-500" />
            {t('managerTasksInProgress')} ({inProgressTasks.length})
          </h2>
          <div className="grid gap-4">
            {inProgressTasks.map(task => (
              <TaskCard 
                key={task.id} 
                task={task}
                onStart={handleStart}
                onComplete={handleComplete}
                isLoading={actionLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {tasks.length === 0 && (
        <div className="text-center py-12 bg-zinc-50 rounded-xl">
          <CheckCircle size={48} className="text-emerald-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-900 mb-2">{t('allTasksDone')}</h3>
          <p className="text-zinc-600">{t('greatWorkNewTasks')}</p>
        </div>
      )}
    </div>
  );
};

export default ManagerTasksPage;
