/**
 * BIBI Cars - Admin Routing Rules Management
 * Control Layer: Manage lead routing rules
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Path,
  Plus,
  Pencil,
  Trash,
  X,
  Users,
  Globe,
  Tag,
  ToggleLeft,
  ToggleRight,
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import ControlSubNav from '../../components/admin/ControlSubNav';
import ControlPageHeader from '../../components/admin/ControlPageHeader';

const RoutingRulesPage = () => {
  const { t } = useLang();
  // eslint-disable-next-line no-unused-vars
  const { user } = useAuth();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [queueStatus, setQueueStatus] = useState(null);

  useEffect(() => {
    fetchRules();
    fetchQueueStatus();
  }, []);

  const fetchRules = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/routing/rules`);
      const rulesData = Array.isArray(res.data)
        ? res.data
        : res.data?.data || res.data?.rules || [];
      setRules(rulesData);
    } catch (err) {
      console.error('Error fetching routing rules:', err);
      toast.error(t('rulesLoadError'));
      setRules([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchQueueStatus = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/routing/queue/status`);
      setQueueStatus(res.data);
    } catch (err) {
      console.error('Error fetching queue status:', err);
    }
  };

  const handleSaveRule = async (ruleData) => {
    try {
      if (editingRule?._id) {
        await axios.patch(
          `${API_URL}/api/routing/rules/${editingRule._id}`,
          ruleData
        );
        toast.success(t('ruleUpdated'));
      } else {
        await axios.post(`${API_URL}/api/routing/rules`, ruleData);
        toast.success(t('ruleCreated'));
      }
      setShowForm(false);
      setEditingRule(null);
      fetchRules();
    } catch (err) {
      toast.error(t('saveError'));
    }
  };

  const handleDeleteRule = async (id) => {
    if (!window.confirm(t('adm2_4e3e8cac4a'))) return;
    try {
      await axios.delete(`${API_URL}/api/routing/rules/${id}`);
      toast.success(t('ruleDeleted'));
      fetchRules();
    } catch (err) {
      toast.error(t('deleteError'));
    }
  };

  const handleToggleActive = async (rule) => {
    try {
      await axios.patch(`${API_URL}/api/routing/rules/${rule._id}`, {
        isActive: !rule.isActive,
      });
      toast.success(
        rule.isActive ? t('adm2_f75de2fbc9') : t('adm2_032de0678c')
      );
      fetchRules();
    } catch (err) {
      toast.error(t('errorGeneric'));
    }
  };

  if (loading) {
    return (
      <div data-testid="routing-rules-page">
        <ControlSubNav />
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      data-testid="routing-rules-page"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <ControlSubNav />

      <div className="space-y-5 sm:space-y-6">
        <ControlPageHeader
          icon={Path}
          title={t('routingRulesTitle')}
          subtitle={t('routingRulesSubtitle')}
          action={
            <button
              onClick={() => {
                setEditingRule(null);
                setShowForm(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 sm:px-4 h-10 bg-[#18181B] text-white rounded-lg hover:bg-[#27272A] transition-colors text-xs sm:text-sm font-medium whitespace-nowrap shadow-sm"
              data-testid="create-rule-btn"
              aria-label={t('addRule')}
            >
              <Plus size={16} weight="bold" />
              <span className="hidden sm:inline">{t('addRule')}</span>
            </button>
          }
        />

        {/* Queue Status — 2 cols mobile / 4 cols desktop, comfortable padding */}
        {queueStatus && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(queueStatus.queues || {}).map(([name, count]) => (
              <div
                key={name}
                className="bg-white rounded-xl p-4 border border-[#E4E4E7] min-w-0"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Users
                    size={15}
                    className="text-[#4F46E5] flex-shrink-0"
                    weight="duotone"
                  />
                  <span className="text-xs font-medium text-[#71717A] truncate">
                    {name}
                  </span>
                </div>
                <div className="text-xl sm:text-2xl font-bold text-[#18181B] leading-none">
                  {count}
                </div>
                <div className="text-[11px] text-[#A1A1AA] mt-1">
                  {t('adm_in_queue_2')}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Rules List */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center gap-2">
            <Path size={18} className="text-[#4F46E5]" weight="duotone" />
            <h3 className="font-semibold text-sm text-[#18181B]">
              {t('adm3_fa4f8e337d')}
              {rules.length})
            </h3>
          </div>

          {rules.length === 0 ? (
            <div className="p-8 text-center text-sm text-[#71717A]">
              {t('adm_no_routing_rules_create_the_first_rule')}
            </div>
          ) : (
            <div className="divide-y divide-[#E4E4E7]">
              {rules
                .sort((a, b) => a.priority - b.priority)
                .map((rule, idx) => (
                  <motion.div
                    key={rule._id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: idx * 0.04 }}
                    className={`px-4 sm:px-5 py-4 hover:bg-[#FAFAFA] transition-colors ${
                      !rule.isActive ? 'opacity-60' : ''
                    }`}
                    data-testid={`rule-${rule._id}`}
                  >
                    {/* Top row: title + actions */}
                    <div className="flex items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <span className="inline-flex items-center justify-center w-7 h-7 bg-[#F4F4F5] rounded-md text-xs font-bold text-[#71717A] flex-shrink-0">
                          {rule.priority}
                        </span>
                        <h4 className="font-semibold text-sm text-[#18181B] truncate">
                          {rule.name}
                        </h4>
                        <span
                          className={`px-2 py-0.5 text-[10px] font-medium rounded-full whitespace-nowrap flex-shrink-0 ${
                            rule.isActive
                              ? 'bg-[#ECFDF5] text-[#059669]'
                              : 'bg-[#F4F4F5] text-[#71717A]'
                          }`}
                        >
                          {rule.isActive
                            ? t('adm2_c9921496ef')
                            : t('adm2_6e3f76873c')}
                        </span>
                      </div>
                      <div className="flex items-center gap-0.5 flex-shrink-0">
                        <button
                          onClick={() => handleToggleActive(rule)}
                          className={`p-2 rounded-md transition-colors ${
                            rule.isActive
                              ? 'text-[#059669] hover:bg-[#ECFDF5]'
                              : 'text-[#71717A] hover:bg-[#F4F4F5]'
                          }`}
                          title={
                            rule.isActive
                              ? t('adm2_ad2cf79efb')
                              : t('adm2_a053dc5a68')
                          }
                        >
                          {rule.isActive ? (
                            <ToggleRight size={20} weight="fill" />
                          ) : (
                            <ToggleLeft size={20} />
                          )}
                        </button>
                        <button
                          onClick={() => {
                            setEditingRule(rule);
                            setShowForm(true);
                          }}
                          className="p-2 text-[#71717A] hover:text-[#4F46E5] hover:bg-[#EEF2FF] rounded-md transition-colors"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule._id)}
                          className="p-2 text-[#71717A] hover:text-[#DC2626] hover:bg-[#FEF2F2] rounded-md transition-colors"
                        >
                          <Trash size={16} />
                        </button>
                      </div>
                    </div>

                    {/* Conditions — inline chips */}
                    {(rule.conditions?.source ||
                      rule.conditions?.country ||
                      rule.conditions?.language ||
                      rule.conditions?.budget?.min) && (
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {rule.conditions?.source && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#EEF2FF] text-[#4F46E5] text-[11px] rounded-md">
                            <Tag size={10} /> {rule.conditions.source}
                          </span>
                        )}
                        {rule.conditions?.country && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#FEF3C7] text-[#D97706] text-[11px] rounded-md">
                            <Globe size={10} /> {rule.conditions.country}
                          </span>
                        )}
                        {rule.conditions?.language && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#FCE7F3] text-[#DB2777] text-[11px] rounded-md">
                            {rule.conditions.language}
                          </span>
                        )}
                        {rule.conditions?.budget?.min && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#ECFDF5] text-[#059669] text-[11px] rounded-md">
                            ${rule.conditions.budget.min}+
                          </span>
                        )}
                      </div>
                    )}

                    {/* Assignment */}
                    <div className="text-xs text-[#71717A]">
                      <span className="font-medium text-[#52525B]">
                        {t('adm_assignment')}{' '}
                      </span>
                      {rule.assignToType === 'manager' &&
                        `${t('r9_manager_label')}: ${rule.assignToId || 'Auto'}`}
                      {rule.assignToType === 'team' &&
                        `${t('r9_team_label')}: ${rule.assignToId || 'Auto'}`}
                      {rule.assignToType === 'queue' &&
                        `${t('r9_queue_label')}: ${rule.queueName || 'default'}`}
                    </div>
                  </motion.div>
                ))}
            </div>
          )}
        </div>
      </div>

      {/* Rule Form Modal */}
      <AnimatePresence>
        {showForm && (
          <RuleFormModal
            rule={editingRule}
            onSave={handleSaveRule}
            onClose={() => {
              setShowForm(false);
              setEditingRule(null);
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
};

const RuleFormModal = ({ rule, onSave, onClose }) => {
  const { t } = useLang();
  const [form, setForm] = useState({
    name: rule?.name || '',
    priority: rule?.priority || 10,
    isActive: rule?.isActive !== false,
    assignToType: rule?.assignToType || 'queue',
    assignToId: rule?.assignToId || '',
    queueName: rule?.queueName || 'default',
    conditions: {
      source: rule?.conditions?.source || '',
      country: rule?.conditions?.country || '',
      language: rule?.conditions?.language || '',
      budget: {
        min: rule?.conditions?.budget?.min || '',
        max: rule?.conditions?.budget?.max || '',
      },
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const data = {
      ...form,
      conditions: {
        ...(form.conditions.source && { source: form.conditions.source }),
        ...(form.conditions.country && { country: form.conditions.country }),
        ...(form.conditions.language && { language: form.conditions.language }),
        ...((form.conditions.budget.min || form.conditions.budget.max) && {
          budget: {
            ...(form.conditions.budget.min && {
              min: Number(form.conditions.budget.min),
            }),
            ...(form.conditions.budget.max && {
              max: Number(form.conditions.budget.max),
            }),
          },
        }),
      },
    };
    onSave(data);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-3 sm:p-6"
      onClick={onClose}
      data-testid="routing-rule-modal-overlay"
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0, y: 8 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0, y: 8 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="bg-white rounded-2xl border border-[#E4E4E7] shadow-[0_24px_80px_rgba(0,0,0,0.22)] w-[calc(100vw-24px)] sm:w-full max-w-2xl max-h-[90vh] grid grid-rows-[auto_minmax(0,1fr)_auto]"
        onClick={(e) => e.stopPropagation()}
        data-testid="routing-rule-modal-panel"
      >
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 border-b border-[#E4E4E7] rounded-t-2xl">
          <div className="px-5 sm:px-6 py-4 flex items-start gap-3">
            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-semibold text-[#18181B] leading-6" data-testid="routing-rule-modal-title">
                {rule ? t('adm2_c73609acb0') : t('adm2_642d68f83c')}
              </h2>
              <p className="mt-0.5 text-sm text-zinc-500 leading-5">
                {t('adm_assignment_type')} · {t('adm2_c0d9b1cc0d')}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto shrink-0 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
              data-testid="routing-rule-modal-close-button"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Scroll body */}
        <form
          id="routing-rule-form"
          onSubmit={handleSubmit}
          className="min-h-0 overflow-y-auto px-5 sm:px-6 py-5"
          data-testid="routing-rule-modal-form"
        >
          <div className="space-y-6">
          {/* Name & Priority — auto-fit so on narrow it stacks */}
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B] mb-2">
                {t('adm_name_3')}
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                placeholder={t('hotLeadsRule')}
                data-testid="rule-name-input"
              />
            </div>
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B] mb-2">
                {t('adm_priority_2')}
              </label>
              <input
                type="number"
                value={form.priority}
                onChange={(e) =>
                  setForm({ ...form, priority: Number(e.target.value) })
                }
                min="1"
                className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                data-testid="rule-priority-input"
              />
            </div>
          </div>

          {/* Assignment Type */}
          <div className="min-w-0">
            <label className="block text-sm font-medium text-[#18181B] mb-2">
              {t('adm_assignment_type')}
            </label>
            <WhiteSelect
              value={form.assignToType}
              onChange={(e) =>
                setForm({ ...form, assignToType: e.target.value })
              }
              data-testid="rule-assign-type-select"
            >
              <option value="queue">{t('adm_queue')}</option>
              <option value="manager">{t('adm_specific_manager')}</option>
              <option value="team">{t('adm_team')}</option>
            </WhiteSelect>
          </div>

          {form.assignToType === 'queue' && (
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B] mb-2">
                {t('adm_queue_name')}
              </label>
              <input
                type="text"
                value={form.queueName}
                onChange={(e) =>
                  setForm({ ...form, queueName: e.target.value })
                }
                className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                placeholder="default"
                data-testid="rule-queue-name-input"
              />
            </div>
          )}

          {form.assignToType !== 'queue' && (
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B] mb-2">
                {t('adm_destination_id')}
              </label>
              <input
                type="text"
                value={form.assignToId}
                onChange={(e) =>
                  setForm({ ...form, assignToId: e.target.value })
                }
                className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                placeholder="manager-id or team-id"
                data-testid="rule-destination-id-input"
              />
            </div>
          )}

          {/* Conditions */}
          <div className="pt-2">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-[#18181B]">
                {t('adm2_c0d9b1cc0d')}
              </h3>
              <span className="text-xs text-zinc-500">
                {t('sourceShort')} · {t('filterCountry')} · {t('footerLanguageLabel')} · {t('minBudget')}
              </span>
            </div>
            <div className="mt-3 border-t border-[#E4E4E7]" />
            <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
              <div className="min-w-0">
                <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                  {t('sourceShort')}
                </label>
                <input
                  type="text"
                  value={form.conditions.source}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      conditions: { ...form.conditions, source: e.target.value },
                    })
                  }
                  className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                  placeholder={t('adm_facebook_google')}
                  data-testid="rule-condition-source-input"
                />
              </div>
              <div className="min-w-0">
                <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                  {t('filterCountry')}
                </label>
                <input
                  type="text"
                  value={form.conditions.country}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      conditions: {
                        ...form.conditions,
                        country: e.target.value,
                      },
                    })
                  }
                  className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                  placeholder={t('adm_ua_us_de')}
                  data-testid="rule-condition-country-input"
                />
              </div>
              <div className="min-w-0">
                <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                  {t('footerLanguageLabel')}
                </label>
                <input
                  type="text"
                  value={form.conditions.language}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      conditions: {
                        ...form.conditions,
                        language: e.target.value,
                      },
                    })
                  }
                  className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                  placeholder={t('adm_uk_en')}
                  data-testid="rule-condition-language-input"
                />
              </div>
              <div className="min-w-0">
                <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                  {t('minBudget')}
                </label>
                <input
                  type="number"
                  value={form.conditions.budget.min}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      conditions: {
                        ...form.conditions,
                        budget: {
                          ...form.conditions.budget,
                          min: e.target.value,
                        },
                      },
                    })
                  }
                  className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                  placeholder="10000"
                  data-testid="rule-condition-budget-min-input"
                />
              </div>
            </div>
          </div>

          {/* Active Toggle */}
          <div className="flex items-center gap-3 rounded-xl border border-[#E4E4E7] bg-white px-4 py-3">
            <button
              type="button"
              onClick={() => setForm({ ...form, isActive: !form.isActive })}
              className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                form.isActive ? 'bg-[#059669]' : 'bg-[#E4E4E7]'
              }`}
              aria-pressed={form.isActive}
              data-testid="rule-active-toggle"
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  form.isActive ? 'translate-x-5' : ''
                }`}
              />
            </button>
            <span className="text-sm font-medium text-[#18181B]">{t('ruleActive')}</span>
          </div>
          </div>
        </form>

        {/* Sticky footer */}
        <div className="sticky bottom-0 z-10 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 border-t border-[#E4E4E7] rounded-b-2xl">
          <div className="px-5 sm:px-6 py-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={onClose}
                className="h-11 w-full rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] font-medium hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                data-testid="routing-rule-cancel-button"
              >
                {t('cancelAction')}
              </button>
              <button
                type="submit"
                form="routing-rule-form"
                className="h-11 w-full rounded-xl bg-[#18181B] text-white font-medium hover:bg-[#27272A] transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                data-testid="save-rule-btn"
              >
                {rule ? t('adm2_79d9f1b64d') : t('adm2_f0476ee470')}
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default RoutingRulesPage;
