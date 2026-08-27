/**
 * BIBI Cars - Admin Cadences Management
 * Control Layer: Manage automated follow-up sequences
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';
import {
  Timer,
  Plus,
  Play,
  Pause,
  Lightning,
  Bell,
  Phone,
  ChatText,
  ListChecks,
  ClockCountdown,
  CaretRight,
  Eye,
  X,
  Warning,
  Check
} from '@phosphor-icons/react';
import ControlSubNav from '../../components/admin/ControlSubNav';
import ControlPageHeader from '../../components/admin/ControlPageHeader';

const CadencesPage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [cadences, setCadences] = useState([]);
  const [activeRuns, setActiveRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCadence, setSelectedCadence] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cadencesRes, runsRes] = await Promise.all([
        axios.get(`${API_URL}/api/cadence/definitions`),
        axios.get(`${API_URL}/api/cadence/runs`)
      ]);
      setCadences(cadencesRes.data || []);
      setActiveRuns(runsRes.data || []);
    } catch (err) {
      console.error('Error fetching cadences:', err);
      toast.error(t('loadingError'));
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (actionType) => {
    switch (actionType) {
      case 'task': return ListChecks;
      case 'alert': return Bell;
      case 'notification': return Bell;
      case 'telegram': return ChatText;
      case 'call': return Phone;
      default: return Lightning;
    }
  };

  const getActionColor = (actionType) => {
    switch (actionType) {
      case 'task': return { bg: '#EEF2FF', text: '#4F46E5' };
      case 'alert': return { bg: '#FEF2F2', text: '#DC2626' };
      case 'notification': return { bg: '#FEF3C7', text: '#D97706' };
      case 'telegram': return { bg: '#ECFDF5', text: '#059669' };
      case 'call': return { bg: '#F3E8FF', text: '#7C3AED' };
      default: return { bg: '#F4F4F5', text: '#71717A' };
    }
  };

  if (loading) {
    return (
      <div data-testid="cadences-page">
        <ControlSubNav />
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
        </div>
      </div>
    );
  }

  return (
    <motion.div 
      data-testid="cadences-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
    >
      <ControlSubNav />

      <div className="space-y-5 sm:space-y-6">
        <ControlPageHeader
          icon={Timer}
          title={t('cadencesTitle')}
          subtitle={t('cadencesSubtitle')}
          action={
            <div className="flex items-center gap-1.5 px-3 h-10 bg-[#F4F4F5] rounded-lg whitespace-nowrap">
              <Timer size={15} className="text-[#18181B]" weight="duotone" />
              <span className="text-xs sm:text-sm font-medium text-[#18181B] whitespace-nowrap">
                {activeRuns.length} {t('active')}
              </span>
            </div>
          }
        />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6">
        {/* Cadence Definitions */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Lightning size={20} className="text-[#18181B]" weight="duotone" />
              <h3 className="font-semibold text-[#18181B]">{t('adm_cadence_definition')}</h3>
            </div>
          </div>
          
          {cadences.length === 0 ? (
            <div className="p-8 text-center text-sm text-[#71717A]">
              {t('adm_no_defined_cadences_they_are_automatically_created')}
            </div>
          ) : (
            <div className="divide-y divide-[#E4E4E7]">
              {cadences.map((cadence, idx) => (
                <motion.div
                  key={cadence._id || cadence.code}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.05 }}
                  className="p-5 hover:bg-[#FAFAFA] transition-colors cursor-pointer"
                  onClick={() => setSelectedCadence(cadence)}
                  data-testid={`cadence-${cadence.code}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h4 className="font-semibold text-[#18181B] mb-1">{cadence.name}</h4>
                      <p className="text-sm text-[#71717A]">{cadence.description || cadence.triggerEvent}</p>
                    </div>
                    <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${
                      cadence.isActive !== false 
                        ? 'bg-[#ECFDF5] text-[#059669]' 
                        : 'bg-[#F4F4F5] text-[#71717A]'
                    }`}>
                      {cadence.isActive !== false ? t('adm3_6c4bee09e1') : t('adm3_86a6e3e43d')}
                    </span>
                  </div>

                  {/* Trigger Event */}
                  <div className="mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#FEF3C7] text-[#D97706] text-xs font-medium rounded-lg">
                      <Lightning size={12} weight="fill" />
                      Trigger: {cadence.triggerEvent}
                    </span>
                  </div>

                  {/* Steps Preview */}
                  <div className="flex flex-wrap gap-2">
                    {(cadence.steps || []).slice(0, 4).map((step, i) => {
                      const Icon = getActionIcon(step.actionType);
                      const colors = getActionColor(step.actionType);
                      return (
                        <div 
                          key={i}
                          className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs"
                          style={{ backgroundColor: colors.bg, color: colors.text }}
                        >
                          <Icon size={12} weight="duotone" />
                          <span>{step.delayMinutes}m</span>
                        </div>
                      );
                    })}
                    {(cadence.steps || []).length > 4 && (
                      <span className="text-xs text-[#71717A]">+{cadence.steps.length - 4} more</span>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Active Runs */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Play size={20} className="text-[#059669]" weight="duotone" />
              <h3 className="font-semibold text-[#18181B]">{t('adm_active_launches')}</h3>
            </div>
            <span className="px-2 py-0.5 bg-[#ECFDF5] text-[#059669] text-xs font-medium rounded-full">
              {activeRuns.length}
            </span>
          </div>
          
          <div className="divide-y divide-[#E4E4E7] max-h-[500px] overflow-auto">
            {activeRuns.length === 0 ? (
              <div className="p-6 text-center text-sm text-[#71717A]">
                {t('adm_no_active_launches')}
              </div>
            ) : (
              activeRuns.slice(0, 20).map((run) => (
                <div 
                  key={run._id} 
                  className="p-4 hover:bg-[#FAFAFA] transition-colors cursor-pointer"
                  onClick={() => setSelectedRun(run)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-[#18181B]">{run.cadenceCode}</span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                      run.status === 'running' 
                        ? 'bg-[#EEF2FF] text-[#4F46E5]' 
                        : run.status === 'completed'
                        ? 'bg-[#ECFDF5] text-[#059669]'
                        : 'bg-[#F4F4F5] text-[#71717A]'
                    }`}>
                      {run.status}
                    </span>
                  </div>
                  <div className="text-xs text-[#71717A]">
                    {run.entityType}: {run.entityId?.slice(-6)}
                  </div>
                  <div className="text-xs text-[#A1A1AA] mt-1">
                    Step {run.currentStep + 1}/{run.totalSteps || '?'}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Cadence Detail Modal */}
      <AnimatePresence>
        {selectedCadence && (
          <CadenceDetailModal
            cadence={selectedCadence}
            onClose={() => setSelectedCadence(null)}
          />
        )}
      </AnimatePresence>

      {/* Run Detail Modal */}
      <AnimatePresence>
        {selectedRun && (
          <RunDetailModal
            run={selectedRun}
            onClose={() => setSelectedRun(null)}
          />
        )}
      </AnimatePresence>
      </div>
    </motion.div>
  );
};

const CadenceDetailModal = ({ cadence, onClose }) => {
  const { t } = useLang();
  const getActionIcon = (actionType) => {
    switch (actionType) {
      case 'task': return ListChecks;
      case 'alert': return Bell;
      case 'notification': return Bell;
      case 'telegram': return ChatText;
      case 'call': return Phone;
      default: return Lightning;
    }
  };

  const getActionColor = (actionType) => {
    switch (actionType) {
      case 'task': return { bg: '#EEF2FF', text: '#4F46E5', border: '#C7D2FE' };
      case 'alert': return { bg: '#FEF2F2', text: '#DC2626', border: '#FECACA' };
      case 'notification': return { bg: '#FEF3C7', text: '#D97706', border: '#FDE68A' };
      case 'telegram': return { bg: '#ECFDF5', text: '#059669', border: '#A7F3D0' };
      case 'call': return { bg: '#F3E8FF', text: '#7C3AED', border: '#DDD6FE' };
      default: return { bg: '#F4F4F5', text: '#71717A', border: '#E4E4E7' };
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-[#E4E4E7] flex items-center justify-between sticky top-0 bg-white">
          <div>
            <h3 className="font-semibold text-lg text-[#18181B]">{cadence.name}</h3>
            <p className="text-sm text-[#71717A]">{cadence.description}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded-lg">
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {/* Trigger */}
          <div className="mb-6">
            <h4 className="text-sm font-medium text-[#71717A] mb-2">{t('adm_event_trigger')}</h4>
            <span className="inline-flex items-center gap-2 px-3 py-2 bg-[#FEF3C7] text-[#D97706] rounded-xl font-medium">
              <Lightning size={18} weight="fill" />
              {cadence.triggerEvent}
            </span>
          </div>

          {/* Steps Timeline */}
          <div>
            <h4 className="text-sm font-medium text-[#71717A] mb-4">{t('adm3_de3ed80d10')}{(cadence.steps || []).length})</h4>
            <div className="space-y-4">
              {(cadence.steps || []).map((step, i) => {
                const Icon = getActionIcon(step.actionType);
                const colors = getActionColor(step.actionType);
                return (
                  <div key={i} className="flex gap-4">
                    {/* Timeline */}
                    <div className="flex flex-col items-center">
                      <div 
                        className="w-10 h-10 rounded-xl flex items-center justify-center border"
                        style={{ backgroundColor: colors.bg, borderColor: colors.border }}
                      >
                        <Icon size={20} style={{ color: colors.text }} weight="duotone" />
                      </div>
                      {i < (cadence.steps || []).length - 1 && (
                        <div className="w-0.5 flex-1 bg-[#E4E4E7] mt-2"></div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 pb-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-[#18181B]">{t('adm3_a739d3d308')} {step.stepOrder}</span>
                        <span className="px-2 py-0.5 bg-[#F4F4F5] text-[#71717A] text-xs rounded-full">
                          {step.actionType}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-[#71717A]">
                        <ClockCountdown size={14} />
                        <span>{t('adm3_d1b8c8844e')} {step.delayMinutes} {t('adm3_24a6c98c78')}</span>
                      </div>
                      {step.payload && Object.keys(step.payload).length > 0 && (
                        <div className="mt-2 p-3 bg-[#F4F4F5] rounded-lg text-xs font-mono text-[#71717A]">
                          {JSON.stringify(step.payload, null, 2)}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

const RunDetailModal = ({ run, onClose }) => {
  const { t } = useLang();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, [run._id]);

  const fetchLogs = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/cadence/runs/${run._id}/logs`);
      setLogs(res.data || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-[#E4E4E7] flex items-center justify-between sticky top-0 bg-white">
          <div>
            <h3 className="font-semibold text-lg text-[#18181B]">Run: {run.cadenceCode}</h3>
            <p className="text-sm text-[#71717A]">{run.entityType}: {run.entityId}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded-lg">
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {/* Status */}
          <div className="mb-4 p-4 bg-[#F4F4F5] rounded-xl">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#71717A]">{t('statusGeneric')}</span>
              <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${
                run.status === 'running' 
                  ? 'bg-[#EEF2FF] text-[#4F46E5]' 
                  : run.status === 'completed'
                  ? 'bg-[#ECFDF5] text-[#059669]'
                  : 'bg-[#FEF2F2] text-[#DC2626]'
              }`}>
                {run.status}
              </span>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-[#71717A]">{t('progress')}</span>
              <span className="text-sm font-medium text-[#18181B]">
                {t('r9_step')} {run.currentStep + 1} {t('r9_of')} {run.totalSteps || '?'}
              </span>
            </div>
          </div>

          {/* Logs */}
          <div>
            <h4 className="text-sm font-medium text-[#71717A] mb-3">{t('adm_execution_log')}</h4>
            {loading ? (
              <div className="text-center py-4">
                <div className="animate-spin w-6 h-6 border-2 border-[#4F46E5] border-t-transparent rounded-full mx-auto"></div>
              </div>
            ) : logs.length === 0 ? (
              <div className="text-sm text-[#71717A] text-center py-4">
                {t('adm_no_records')}
              </div>
            ) : (
              <div className="space-y-2">
                {logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-[#FAFAFA] rounded-lg">
                    {log.success ? (
                      <Check size={16} className="text-[#059669] mt-0.5" weight="bold" />
                    ) : (
                      <Warning size={16} className="text-[#DC2626] mt-0.5" weight="bold" />
                    )}
                    <div className="flex-1">
                      <div className="text-sm text-[#18181B]">
                        Step {log.stepOrder}: {log.actionType}
                      </div>
                      {log.error && (
                        <div className="text-xs text-[#DC2626] mt-1">{log.error}</div>
                      )}
                      <div className="text-xs text-[#A1A1AA] mt-1">
                        {log.executedAt && format(new Date(log.executedAt), 'dd.MM HH:mm', { locale: uk })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default CadencesPage;
