/**
 * BIBI Cars - Admin Score Rules Management
 * Control Layer: Manage scoring rules for leads, deals, managers, shipments
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChartLineUp,
  Plus,
  Pencil,
  Trash,
  Fire,
  Heart,
  User,
  Truck,
  ToggleLeft,
  ToggleRight,
  X,
  Tag,
  Info,
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import ControlSubNav from '../../components/admin/ControlSubNav';
import ControlPageHeader from '../../components/admin/ControlPageHeader';

const ScoreRulesPage = () => {
  const { t } = useLang();
  // eslint-disable-next-line no-unused-vars
  const { user } = useAuth();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('lead_score');
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/scoring/rules`);
      const rulesData = Array.isArray(res.data)
        ? res.data
        : res.data?.data || res.data?.rules || [];
      setRules(rulesData);
    } catch (err) {
      console.error('Error fetching score rules:', err);
      toast.error(t('rulesLoadError'));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRule = async (rule) => {
    try {
      await axios.patch(
        `${API_URL}/api/scoring/rules/${rule.code}/toggle`,
        { isActive: !rule.isActive }
      );
      toast.success(
        rule.isActive ? t('adm2_f75de2fbc9') : t('adm2_032de0678c')
      );
      fetchRules();
    } catch (err) {
      toast.error(t('errorGeneric'));
    }
  };

  const handleDeleteRule = async (code) => {
    if (!window.confirm(t('adm2_4e3e8cac4a'))) return;
    try {
      await axios.delete(`${API_URL}/api/scoring/rules/${code}`);
      toast.success(t('ruleDeleted'));
      fetchRules();
    } catch (err) {
      toast.error(t('deleteError'));
    }
  };

  const handleSaveRule = async (ruleData) => {
    try {
      if (editingRule?.code) {
        await axios.patch(
          `${API_URL}/api/scoring/rules/${editingRule.code}`,
          ruleData
        );
        toast.success(t('ruleUpdated'));
      } else {
        await axios.post(`${API_URL}/api/scoring/rules`, ruleData);
        toast.success(t('ruleCreated'));
      }
      setShowForm(false);
      setEditingRule(null);
      fetchRules();
    } catch (err) {
      toast.error(t('saveError'));
    }
  };

  const scoreTypes = [
    {
      id: 'lead_score',
      label: t('adm_lead_score'),
      icon: Fire,
      color: '#DC2626',
      bgColor: '#FEF2F2',
      description: t('adm2_cold_warm_hot_db4ae67702'),
    },
    {
      id: 'deal_health',
      label: t('adm_deal_health'),
      icon: Heart,
      color: '#059669',
      bgColor: '#ECFDF5',
      description: t('adm2_low_medium_high_0ed2ece3a9'),
    },
    {
      id: 'manager_performance',
      label: t('adm_manager_performance'),
      icon: User,
      color: '#4F46E5',
      bgColor: '#EEF2FF',
      description: t('adm_manager_performance_2'),
    },
    {
      id: 'shipment_risk',
      label: t('adm_shipment_risk'),
      icon: Truck,
      color: '#D97706',
      bgColor: '#FEF3C7',
      description: t('adm_delivery_risk'),
    },
  ];

  const filteredRules = rules.filter((r) => r.scoreType === activeTab);
  const activeType = scoreTypes.find((tt) => tt.id === activeTab);

  if (loading) {
    return (
      <div data-testid="score-rules-page">
        <ControlSubNav />
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      data-testid="score-rules-page"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <ControlSubNav />

      <div className="space-y-5 sm:space-y-6">
        <ControlPageHeader
          icon={ChartLineUp}
          title={t('scoreRulesTitle')}
          subtitle={t('scoreRulesSubtitle')}
          action={
            <button
              onClick={() => {
                setEditingRule(null);
                setShowForm(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 sm:px-4 h-10 bg-[#18181B] text-white rounded-lg hover:bg-[#27272A] transition-colors text-xs sm:text-sm font-medium whitespace-nowrap shadow-sm"
              data-testid="create-score-rule-btn"
            >
              <Plus size={16} weight="bold" />
              <span className="hidden sm:inline">{t('addScoreRule')}</span>
            </button>
          }
        />

        {/* Score Type Cards — comfortable padding, 2-col mobile / 4-col desktop */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {scoreTypes.map((type) => {
            const count = rules.filter((r) => r.scoreType === type.id).length;
            const activeCount = rules.filter(
              (r) => r.scoreType === type.id && r.isActive
            ).length;
            const active = activeTab === type.id;
            return (
              <motion.button
                key={type.id}
                type="button"
                whileTap={{ scale: 0.97 }}
                onClick={() => setActiveTab(type.id)}
                className={`text-left cursor-pointer rounded-xl p-4 border transition-all min-w-0 ${
                  active
                    ? 'border-[#18181B] shadow-md'
                    : 'border-[#E4E4E7] hover:border-[#A1A1AA]'
                }`}
                style={{ backgroundColor: active ? type.bgColor : 'white' }}
              >
                <div className="flex items-start justify-between mb-2.5">
                  <div
                    className="p-2 rounded-lg"
                    style={{ backgroundColor: type.bgColor }}
                  >
                    <type.icon
                      size={18}
                      weight="duotone"
                      style={{ color: type.color }}
                    />
                  </div>
                  <span
                    className="text-xl sm:text-2xl font-bold leading-none"
                    style={{ color: type.color }}
                  >
                    {count}
                  </span>
                </div>
                <h4 className="font-semibold text-sm text-[#18181B] mb-1 truncate">
                  {type.label}
                </h4>
                <p className="text-[11px] text-[#71717A] line-clamp-2 leading-snug">
                  {type.description}
                </p>
                <div className="mt-2 text-[11px] text-[#A1A1AA]">
                  {activeCount} {t('adm3_783ab41d11')}
                </div>
              </motion.button>
            );
          })}
        </div>

        {/* Rules List */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              {activeType && (
                <>
                  <activeType.icon
                    size={18}
                    style={{ color: activeType.color }}
                    weight="duotone"
                  />
                  <h3 className="font-semibold text-sm text-[#18181B] truncate">
                    {activeType.label} Rules ({filteredRules.length})
                  </h3>
                </>
              )}
            </div>
          </div>

          {filteredRules.length === 0 ? (
            <div className="p-8 text-center text-sm text-[#71717A]">
              {t('adm_no_rules_for_this_category')}
            </div>
          ) : (
            <div className="divide-y divide-[#E4E4E7]">
              {filteredRules.map((rule, idx) => (
                <motion.div
                  key={rule.code}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.03 }}
                  className={`px-4 sm:px-5 py-4 hover:bg-[#FAFAFA] transition-colors ${
                    !rule.isActive ? 'opacity-60' : ''
                  }`}
                  data-testid={`rule-${rule.code}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1 flex-wrap">
                      <h4 className="font-semibold text-sm text-[#18181B] truncate">
                        {rule.name}
                      </h4>
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold rounded-md whitespace-nowrap flex-shrink-0 ${
                          rule.points > 0
                            ? 'bg-[#ECFDF5] text-[#059669]'
                            : 'bg-[#FEF2F2] text-[#DC2626]'
                        }`}
                      >
                        {rule.points > 0 ? '+' : ''}
                        {rule.points} pts
                      </span>
                      <span
                        className={`px-2 py-0.5 text-[10px] rounded-md whitespace-nowrap flex-shrink-0 ${
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
                        onClick={() => handleToggleRule(rule)}
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
                        onClick={() => handleDeleteRule(rule.code)}
                        className="p-2 text-[#71717A] hover:text-[#DC2626] hover:bg-[#FEF2F2] rounded-md transition-colors"
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </div>

                  {rule.description && (
                    <p className="text-xs text-[#71717A] mb-2 line-clamp-2 leading-relaxed">
                      {rule.description}
                    </p>
                  )}

                  <div className="flex items-center gap-1.5 text-[11px] text-[#A1A1AA]">
                    <Tag size={11} />
                    <span className="font-mono truncate">{rule.code}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Info Block — comfortable padding */}
        <div className="bg-[#EEF2FF] rounded-xl p-4 sm:p-5 flex items-start gap-3.5">
          <Info
            size={20}
            className="text-[#4F46E5] flex-shrink-0 mt-0.5"
            weight="duotone"
          />
          <div className="min-w-0">
            <h4 className="font-semibold text-sm text-[#18181B] mb-1">
              {t('adm_how_scoring_works')}
            </h4>
            <p className="text-xs text-[#71717A] leading-relaxed">
              {t('adm_score_explanation')}
            </p>
          </div>
        </div>
      </div>

      {/* Score Rule Form Modal */}
      <AnimatePresence>
        {showForm && (
          <ScoreRuleFormModal
            rule={editingRule}
            scoreType={activeTab}
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

const ScoreRuleFormModal = ({ rule, scoreType, onSave, onClose }) => {
  const { t } = useLang();
  const [form, setForm] = useState({
    code: rule?.code || '',
    name: rule?.name || '',
    description: rule?.description || '',
    scoreType: rule?.scoreType || scoreType,
    points: rule?.points || 10,
    isActive: rule?.isActive !== false,
    condition: {
      field: rule?.condition?.field || '',
      operator: rule?.condition?.operator || 'exists',
      value: rule?.condition?.value || '',
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const data = {
      ...form,
      condition: form.condition.field ? form.condition : undefined,
    };
    onSave(data);
  };

  const operators = [
    { value: 'exists', label: t('adm_exists') },
    { value: 'equals', label: t('adm_equals') },
    { value: 'gt', label: t('adm_greater_than') },
    { value: 'lt', label: t('adm_less_than') },
    { value: 'gte', label: t('adm_greater_than_or_equal_to') },
    { value: 'lte', label: t('adm_less_than_or_equal_to') },
    { value: 'contains', label: t('adm_contains') },
    { value: 'in', label: t('adm_one_of') },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-3 sm:p-6"
      onClick={onClose}
      data-testid="score-rule-modal-overlay"
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0, y: 8 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0, y: 8 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="bg-white rounded-2xl border border-[#E4E4E7] shadow-[0_24px_80px_rgba(0,0,0,0.22)] w-[calc(100vw-24px)] sm:w-full max-w-2xl max-h-[90vh] grid grid-rows-[auto_minmax(0,1fr)_auto]"
        onClick={(e) => e.stopPropagation()}
        data-testid="score-rule-modal-panel"
      >
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 border-b border-[#E4E4E7] rounded-t-2xl">
          <div className="px-5 sm:px-6 py-4 flex items-start gap-3">
            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-semibold text-[#18181B] leading-6" data-testid="score-rule-modal-title">
                {rule ? t('adm2_c73609acb0') : t('adm2_8b51d5b11c')}
              </h2>
              <p className="mt-0.5 text-sm text-zinc-500 leading-5">
                {t('adm_score_type')} · {t('adm_points')}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto shrink-0 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
              data-testid="score-rule-modal-close-button"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Scroll body */}
        <form
          id="score-rule-form"
          onSubmit={handleSubmit}
          className="min-h-0 overflow-y-auto px-5 sm:px-6 py-5"
          data-testid="score-rule-modal-form"
        >
          <div className="space-y-6">
            {/* Code */}
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B]">
                {t('adm2_acede68c53')}
              </label>
              <input
                type="text"
                value={form.code}
                onChange={(e) =>
                  setForm({
                    ...form,
                    code: e.target.value.toLowerCase().replace(/\s+/g, '_'),
                  })
                }
                required
                disabled={!!rule}
                className="mt-2 w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none disabled:bg-[#F4F4F5] font-mono text-sm"
                placeholder="lead_hot_source"
                data-testid="score-rule-code-input"
              />
            </div>

            {/* Name */}
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B]">
                {t('adm_name_3')}
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                className="mt-2 w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                placeholder={t('hotLeadFromPremium')}
                data-testid="score-rule-name-input"
              />
            </div>

            {/* Description */}
            <div className="min-w-0">
              <label className="block text-sm font-medium text-[#18181B]">
                {t('descUk')}
              </label>
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={3}
                className="mt-2 w-full px-3.5 py-2.5 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none resize-y text-sm leading-relaxed"
                placeholder={t('adm_rule_description')}
                data-testid="score-rule-description-input"
              />
            </div>

            {/* Score Type & Points — auto-fit, never truncates Score Type label */}
            <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
              <div className="min-w-0">
                <label className="block text-sm font-medium text-[#18181B] mb-2">
                  {t('adm_score_type')}
                </label>
                <WhiteSelect
                  value={form.scoreType}
                  onChange={(e) =>
                    setForm({ ...form, scoreType: e.target.value })
                  }
                  data-testid="score-rule-type-select"
                >
                  <option value="lead_score">{t('leadScore')}</option>
                  <option value="deal_health">{t('dealHealth')}</option>
                  <option value="manager_performance">
                    {t('managerPerformance')}
                  </option>
                  <option value="shipment_risk">{t('shipmentRisk')}</option>
                </WhiteSelect>
              </div>
              <div className="min-w-0">
                <label className="block text-sm font-medium text-[#18181B] mb-2">
                  {t('adm_points')}
                </label>
                <input
                  type="number"
                  value={form.points}
                  onChange={(e) =>
                    setForm({ ...form, points: Number(e.target.value) })
                  }
                  className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                  placeholder="10"
                  data-testid="score-rule-points-input"
                />
                <p className="mt-1.5 text-xs text-zinc-500 leading-5">
                  {t('adm_use_negative_for_penalties')}
                </p>
              </div>
            </div>

            {/* Condition (optional) — section with divider */}
            <div className="pt-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-[#18181B]">
                  {t('adm2_3b21ce3ba6')}
                </h3>
                <span className="text-xs text-zinc-500">{t('adm_field')} · {t('adm_operator')} · {t('adm_value')}</span>
              </div>
              <div className="mt-3 border-t border-[#E4E4E7]" />
              <div className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
                <div className="min-w-0">
                  <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                    {t('adm_field')}
                  </label>
                  <input
                    type="text"
                    value={form.condition.field}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        condition: { ...form.condition, field: e.target.value },
                      })
                    }
                    className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                    placeholder="source"
                    data-testid="score-rule-condition-field-input"
                  />
                </div>
                <div className="min-w-0">
                  <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                    {t('adm_operator')}
                  </label>
                  <WhiteSelect
                    value={form.condition.operator}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        condition: {
                          ...form.condition,
                          operator: e.target.value,
                        },
                      })
                    }
                    data-testid="score-rule-operator-select"
                  >
                    {operators.map((op) => (
                      <option key={op.value} value={op.value}>
                        {op.label}
                      </option>
                    ))}
                  </WhiteSelect>
                </div>
                <div className="min-w-0">
                  <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                    {t('adm_value')}
                  </label>
                  <input
                    type="text"
                    value={form.condition.value}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        condition: { ...form.condition, value: e.target.value },
                      })
                    }
                    className="w-full px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5]/30 focus:border-[#4F46E5] focus:outline-none text-sm"
                    placeholder="facebook"
                    data-testid="score-rule-condition-value-input"
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
                data-testid="score-rule-active-toggle"
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
                data-testid="score-rule-cancel-button"
              >
                {t('cancelAction')}
              </button>
              <button
                type="submit"
                form="score-rule-form"
                className="h-11 w-full rounded-xl bg-[#18181B] text-white font-medium hover:bg-[#27272A] transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                data-testid="save-score-rule-btn"
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

export default ScoreRulesPage;
