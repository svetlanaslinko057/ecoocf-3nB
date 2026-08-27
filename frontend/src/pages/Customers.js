import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang } from '../i18n';
import { toast } from 'sonner';
import { Plus, Pencil, Trash, Eye, Users, ArrowsClockwise } from '@phosphor-icons/react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { motion } from 'framer-motion';
import RefreshButton from '../components/ui/RefreshButton';
import PhoneInput, { detectCountry, isValidForCountry } from '../components/ui/PhoneInput';
import SharedZoneBadge from '../components/ui/SharedZoneBadge';
import ReassignDialog from '../components/ui/ReassignDialog';
import useManagersMap from '../hooks/useManagersMap';
import HealthChip from '../components/health/HealthChip';

const CUSTOMER_TYPES = ['individual', 'company'];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const Customers = () => {
  const { t } = useLang();
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canReassign = ['admin', 'owner', 'master_admin', 'team_lead'].includes(role);
  const { managers: managersMap, invalidate: invalidateManagers } = useManagersMap();
  const [customers, setCustomers] = useState([]);
  const [healthMap, setHealthMap] = useState({}); // { customerId: {score, segment} }
  const [healthFilter, setHealthFilter] = useState(''); // '', 'hot', 'warm', 'cold', 'lost'
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  // Customer-Card spec (2026-06-10): TL filters
  const [countryFilter, setCountryFilter]    = useState('');
  const [managerFilter, setManagerFilter]    = useState('');
  const [statusFilter, setStatusFilter]      = useState('');
  const [utmSource, setUtmSource]            = useState('');
  const [utmMedium, setUtmMedium]            = useState('');
  const [utmCampaign, setUtmCampaign]        = useState('');
  const [filtersOpen, setFiltersOpen]        = useState(false);  // mobile collapse
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [reassignTarget, setReassignTarget] = useState(null);
  const [formData, setFormData] = useState({
    firstName: '', lastName: '', email: '', phone: '', phoneCountry: 'BG',
    company: '', type: 'individual', vehicleInterest: '', notes: '',
    country: '',
    wishes: { budget_min: '', budget_max: '', currency: 'EUR', timeline_months: '', note: '' },
  });
  const [formErrors, setFormErrors] = useState({});

  useEffect(() => { fetchCustomers(); }, [search, countryFilter, managerFilter, statusFilter, utmSource, utmMedium, utmCampaign]);

  const fetchCustomers = async () => {
    try {
      const params = new URLSearchParams();
      if (search)         params.append('q', search);
      if (countryFilter)  params.append('country', countryFilter);
      if (managerFilter)  params.append('managerId', managerFilter);
      if (statusFilter)   params.append('status', statusFilter);
      if (utmSource)      params.append('utm_source', utmSource);
      if (utmMedium)      params.append('utm_medium', utmMedium);
      if (utmCampaign)    params.append('utm_campaign', utmCampaign);
      // Legacy "search" alias kept for backend back-compat
      if (search)         params.append('search', search);
      const res = await axios.get(`${API_URL}/api/customers?${params}`);
      const list = res.data.data || [];
      setCustomers(list);
      // Pull lightweight health for the visible page (single round-trip, no N+1).
      if (list.length) {
        try {
          const ids = list.map((c) => c.id).filter(Boolean).join(',');
          const { data: hb } = await axios.get(`${API_URL}/api/customer-health-bulk?ids=${ids}`);
          setHealthMap(hb.items || {});
        } catch {
          setHealthMap({});
        }
      } else {
        setHealthMap({});
      }
    } catch (err) { toast.error(t('error')); } finally { setLoading(false); }
  };

  const validate = () => {
    const errors = {};
    if (!(formData.firstName || '').trim()) errors.firstName = t('field_required');
    if (!(formData.lastName || '').trim()) errors.lastName = t('field_required');
    if (!(formData.email || '').trim()) {
      errors.email = t('field_required');
    } else if (!EMAIL_RE.test(formData.email.trim())) {
      errors.email = t('field_invalid_email');
    }
    if (!(formData.phone || '').trim()) {
      errors.phone = t('field_required');
    } else if (!isValidForCountry(formData.phone, formData.phoneCountry)) {
      errors.phone = t('field_invalid_phone');
    }
    if (formData.type === 'company' && !(formData.company || '').trim()) {
      errors.company = t('field_required');
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) {
      toast.error(t('field_form_invalid'));
      return;
    }
    try {
      const payload = {
        firstName: formData.firstName.trim(),
        lastName:  formData.lastName.trim(),
        email:     formData.email.trim(),
        phone:     formData.phone,
        phoneCountry: formData.phoneCountry,
        company:   formData.type === 'company' ? formData.company.trim() : null,
        type:      formData.type,
        vehicleInterest: formData.vehicleInterest || null,
        notes:     formData.notes || null,
        country:   formData.country || null,
        wishes:    {
          budget_min:      Number(formData.wishes?.budget_min) || 0,
          budget_max:      Number(formData.wishes?.budget_max) || 0,
          currency:        (formData.wishes?.currency || 'EUR').toUpperCase(),
          timeline_months: Number(formData.wishes?.timeline_months) || 0,
          note:            (formData.wishes?.note || '').trim() || null,
        },
      };
      if (editingCustomer) {
        await axios.put(`${API_URL}/api/customers/${editingCustomer.id}`, payload);
        toast.success(t('customerUpdated'));
      } else {
        await axios.post(`${API_URL}/api/customers`, payload);
        toast.success(t('customerCreated'));
      }
      setShowModal(false);
      resetForm();
      fetchCustomers();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.response?.data?.message || t('error'));
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(t('deleteCustomerConfirm'))) return;
    try {
      await axios.delete(`${API_URL}/api/customers/${id}`);
      toast.success(t('customerDeleted'));
      fetchCustomers();
    } catch (err) { toast.error(t('error')); }
  };

  const openEditModal = (customer) => {
    setEditingCustomer(customer);
    const detected = detectCountry(customer.phone);
    setFormData({
      firstName: customer.firstName || '',
      lastName:  customer.lastName || '',
      email:     customer.email || '',
      phone:     customer.phone || '',
      phoneCountry: customer.phoneCountry || (detected && detected.code) || 'BG',
      company:   customer.company || '',
      type:      customer.type || 'individual',
      vehicleInterest: customer.vehicleInterest || '',
      notes:     customer.notes || '',
      country:   customer.country || '',
      wishes: {
        budget_min:      customer.wishes?.budget_min ?? '',
        budget_max:      customer.wishes?.budget_max ?? '',
        currency:        customer.wishes?.currency || 'EUR',
        timeline_months: customer.wishes?.timeline_months ?? '',
        note:            customer.wishes?.note || '',
      },
    });
    setFormErrors({});
    setShowModal(true);
  };

  const resetForm = () => {
    setEditingCustomer(null);
    setFormData({
      firstName: '', lastName: '', email: '', phone: '', phoneCountry: 'BG',
      company: '', type: 'individual', vehicleInterest: '', notes: '',
      country: '',
      wishes: { budget_min: '', budget_max: '', currency: 'EUR', timeline_months: '', note: '' },
    });
    setFormErrors({});
  };

  const typeLabels = { individual: t('typeIndividual'), company: t('typeCompany') };

  return (
    <motion.div data-testid="customers-page" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4 mb-6 lg:mb-8">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Users size={20} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('customersTitle')}</h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">{t('customerDatabase')}</p>
            <div className="mt-2">
              <SharedZoneBadge />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <RefreshButton onClick={fetchCustomers} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="customers-refresh-btn" />
          <button onClick={() => { resetForm(); setShowModal(true); }} className="btn-primary shrink-0 whitespace-nowrap" data-testid="create-customer-btn">
            <Plus size={18} weight="bold" /><span className="hidden sm:inline">{t('newCustomer')}</span>
          </button>
        </div>
      </div>

      <div className="card p-4 sm:p-5 mb-4 sm:mb-5">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('searchCustomers')} className="input w-full sm:max-w-md" data-testid="customers-search-input" />
          <div className="flex items-center gap-1.5 flex-wrap" data-testid="customers-health-filter">
            {[
              { id: '',     label: t('health_seg_all') },
              { id: 'hot',  label: t('health_seg_hot'),  cls: 'data-[active=true]:bg-emerald-50 data-[active=true]:text-emerald-700 data-[active=true]:border-emerald-300' },
              { id: 'warm', label: t('health_seg_warm'), cls: 'data-[active=true]:bg-amber-50   data-[active=true]:text-amber-700   data-[active=true]:border-amber-300' },
              { id: 'cold', label: t('health_seg_cold'), cls: 'data-[active=true]:bg-sky-50     data-[active=true]:text-sky-700     data-[active=true]:border-sky-300' },
              { id: 'lost', label: t('health_seg_lost'), cls: 'data-[active=true]:bg-zinc-100   data-[active=true]:text-zinc-700   data-[active=true]:border-zinc-300' },
            ].map((opt) => (
              <button
                key={opt.id || 'all'}
                data-active={healthFilter === opt.id}
                onClick={() => setHealthFilter(opt.id)}
                className={`px-2.5 py-1 text-xs font-medium rounded-full border border-zinc-200 bg-white hover:bg-zinc-50 transition-colors ${opt.cls || ''}`}
                data-testid={`customers-health-filter-${opt.id || 'all'}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Advanced filters — collapsible on mobile, always visible from sm+ */}
        <div className="mt-3 sm:mt-4">
          <button
            type="button"
            onClick={() => setFiltersOpen((v) => !v)}
            className="sm:hidden w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[#52525B] bg-[#F4F4F5] rounded-lg"
            data-testid="customers-filters-toggle"
          >
            <span>{t('adm_filters')}{(countryFilter || managerFilter || statusFilter || utmSource || utmMedium || utmCampaign) ? ' •' : ''}</span>
            <span className="text-[10px]">{filtersOpen ? '▲' : '▼'}</span>
          </button>
          <div className={`${filtersOpen ? 'block' : 'hidden'} sm:block mt-2 sm:mt-0`} data-testid="customers-filters-panel">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-2 sm:gap-3">
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_country_direction')}</label>
                <select
                  value={countryFilter}
                  onChange={(e) => setCountryFilter(e.target.value)}
                  className="input w-full text-[12.5px]"
                  data-testid="customers-filter-country"
                >
                  <option value="">{t('adm_all')}</option>
                  <option value="USA">USA</option>
                  <option value="Korea">Korea</option>
                  <option value="Bulgaria">Bulgaria</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              {canReassign && (
                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('leadsWs_fieldManager') || 'Manager'}</label>
                  <select
                    value={managerFilter}
                    onChange={(e) => setManagerFilter(e.target.value)}
                    className="input w-full text-[12.5px]"
                    data-testid="customers-filter-manager"
                  >
                    <option value="">{t('adm_all')}</option>
                    {Object.entries(managersMap || {}).map(([mid, m]) => (
                      <option key={mid} value={mid}>{m?.name || m?.email || mid}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_status')}</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="input w-full text-[12.5px]"
                  data-testid="customers-filter-status"
                >
                  <option value="">{t('adm_all')}</option>
                  <option value="active">{t('adm_active')}</option>
                  <option value="lost">{t('adm_lost')}</option>
                  <option value="completed">{t('adm_completed')}</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Source</label>
                <input
                  type="text"
                  value={utmSource}
                  onChange={(e) => setUtmSource(e.target.value)}
                  placeholder="google, fb…"
                  className="input w-full text-[12.5px]"
                  data-testid="customers-filter-utm-source"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Medium</label>
                <input
                  type="text"
                  value={utmMedium}
                  onChange={(e) => setUtmMedium(e.target.value)}
                  placeholder="cpc, social…"
                  className="input w-full text-[12.5px]"
                  data-testid="customers-filter-utm-medium"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Campaign</label>
                <input
                  type="text"
                  value={utmCampaign}
                  onChange={(e) => setUtmCampaign(e.target.value)}
                  placeholder="spring_sale_2026…"
                  className="input w-full text-[12.5px]"
                  data-testid="customers-filter-utm-campaign"
                />
              </div>
            </div>
            {(countryFilter || managerFilter || statusFilter || utmSource || utmMedium || utmCampaign) && (
              <button
                type="button"
                onClick={() => { setCountryFilter(''); setManagerFilter(''); setStatusFilter(''); setUtmSource(''); setUtmMedium(''); setUtmCampaign(''); }}
                className="mt-2 text-[11px] text-[#4F46E5] hover:underline"
                data-testid="customers-filters-clear"
              >
                {t('adm_clear_filters')}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        {/* Bulk reassign bar */}
        {canReassign && selectedIds.size > 0 && (
          <div className="bg-[#EEF2FF] border-b border-[#C7D2FE] px-4 py-2.5 flex items-center justify-between gap-3" data-testid="customers-bulk-bar">
            <div className="text-sm text-[#3730A3] font-medium">
              {selectedIds.size} {selectedIds.size === 1 ? 'customer' : 'customers'} selected
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setReassignTarget({ ids: Array.from(selectedIds), currentManagerId: null })}
                className="px-3 py-1.5 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors"
                data-testid="customers-bulk-reassign"
              >
                <ArrowsClockwise size={14} weight="bold" /> Reassign selected
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="px-3 py-1.5 text-[#52525B] hover:bg-white text-xs font-medium rounded-lg transition-colors"
              >
                Clear
              </button>
            </div>
          </div>
        )}
        {/* Desktop / tablet — table view */}
        <div className="hidden md:block overflow-x-auto">
          <table className="table-premium min-w-[700px] w-full" data-testid="customers-table">
          <thead>
            <tr>
              {canReassign && (
                <th className="w-10 text-center">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={customers.length > 0 && selectedIds.size === customers.length}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedIds(new Set(customers.map(c => c.id)));
                      else setSelectedIds(new Set());
                    }}
                    className="rounded border-[#A1A1AA] text-[#4F46E5] focus:ring-[#4F46E5]"
                    data-testid="customers-select-all"
                  />
                </th>
              )}
              <th>{t('name')}</th>
              <th>{t('email')}</th>
              <th>{t('phone')}</th>
              <th>{t('type')}</th>
              <th>{t('health_col_header')}</th>
              <th>Owner</th>
              <th>{t('dealsCount')}</th>
              <th className="text-right">{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (<tr><td colSpan={canReassign ? 9 : 8} className="text-center py-12 text-[#71717A]">{t('loading')}</td></tr>
            ) : customers.length === 0 ? (<tr><td colSpan={canReassign ? 9 : 8} className="text-center py-12 text-[#71717A]">{t('noCustomers')}</td></tr>
            ) : customers
              .filter((customer) => {
                if (!healthFilter) return true;
                const h = healthMap[customer.id];
                return h && h.segment === healthFilter;
              })
              .map(customer => {
              const mgr = customer.managerId ? managersMap[customer.managerId] : null;
              const isSelected = selectedIds.has(customer.id);
              return (
              <tr key={customer.id} data-testid={`customer-row-${customer.id}`} className={isSelected ? 'bg-[#F5F3FF]' : ''}>
                {canReassign && (
                  <td className="w-10 text-center">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        const next = new Set(selectedIds);
                        if (e.target.checked) next.add(customer.id);
                        else next.delete(customer.id);
                        setSelectedIds(next);
                      }}
                      className="rounded border-[#A1A1AA] text-[#4F46E5] focus:ring-[#4F46E5]"
                      data-testid={`customer-select-${customer.id}`}
                    />
                  </td>
                )}
                <td className="font-medium text-[#18181B]">
                  <button 
                    onClick={() => navigate(`/admin/customers/${customer.id}/360`)}
                    className="hover:text-[#4F46E5] transition-colors"
                  >
                    {customer.firstName} {customer.lastName}
                  </button>
                </td>
                <td>{customer.email}</td>
                <td>{customer.phone || '—'}</td>
                <td><span className="text-xs text-[#71717A]">{typeLabels[customer.type]}</span></td>
                <td data-testid={`customer-health-cell-${customer.id}`}>
                  {healthMap[customer.id] ? (
                    <HealthChip
                      size="sm"
                      score={healthMap[customer.id].score}
                      segment={healthMap[customer.id].segment}
                    />
                  ) : (
                    <span className="text-xs text-[#A1A1AA]">—</span>
                  )}
                </td>
                <td>
                  {mgr ? (
                    <div className="flex items-center gap-1.5 text-xs">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-semibold text-[10px]">
                        {(mgr.name || mgr.email || '?').slice(0,1).toUpperCase()}
                      </div>
                      <span className="text-[#18181B] truncate max-w-[110px]" title={mgr.email}>{mgr.name || mgr.email}</span>
                    </div>
                  ) : (
                    <span className="text-xs text-[#A1A1AA] italic">unassigned</span>
                  )}
                </td>
                <td>
                  <span className="font-semibold text-[#18181B]">{customer.totalDeals || 0}</span>
                  <span className="text-xs text-[#71717A] ml-1">(${(customer.totalRevenue || customer.totalValue || 0).toLocaleString()})</span>
                </td>
                <td>
                  <div className="flex items-center justify-end gap-1">
                    {canReassign && (
                      <button
                        onClick={() => setReassignTarget({ ids: [customer.id], currentManagerId: customer.managerId })}
                        className="p-2.5 hover:bg-[#EEF2FF] rounded-lg transition-colors"
                        data-testid={`reassign-customer-${customer.id}`}
                        title="Change owner"
                      >
                        <ArrowsClockwise size={16} className="text-[#4F46E5]" />
                      </button>
                    )}
                    <button onClick={() => navigate(`/admin/customers/${customer.id}/360`)} className="p-2.5 hover:bg-[#E0E7FF] rounded-lg" data-testid={`view-customer-${customer.id}`}><Eye size={16} className="text-[#4F46E5]" /></button>
                    <button onClick={() => openEditModal(customer)} className="p-2.5 hover:bg-[#F4F4F5] rounded-lg" data-testid={`edit-customer-${customer.id}`}><Pencil size={16} className="text-[#71717A]" /></button>
                    <button onClick={() => handleDelete(customer.id)} className="p-2.5 hover:bg-[#FEE2E2] rounded-lg" data-testid={`delete-customer-${customer.id}`}><Trash size={16} className="text-[#DC2626]" /></button>
                  </div>
                </td>
              </tr>
            )})}
          </tbody>
        </table>
        </div>

        {/* Mobile — stacked card view */}
        <div className="md:hidden divide-y divide-[#F4F4F5]" data-testid="customers-mobile-list">
          {loading ? (
            <div className="text-center py-12 text-[#71717A]">{t('loading')}</div>
          ) : customers.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">{t('noCustomers')}</div>
          ) : customers
              .filter((customer) => {
                if (!healthFilter) return true;
                const h = healthMap[customer.id];
                return h && h.segment === healthFilter;
              })
              .map(customer => (
            <div
              key={customer.id}
              className="p-4 hover:bg-[#FAFAFA] transition-colors"
              data-testid={`customer-card-${customer.id}`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <button
                  onClick={() => navigate(`/admin/customers/${customer.id}/360`)}
                  className="text-left flex-1 min-w-0"
                >
                  <div className="font-semibold text-[#18181B] text-base truncate">
                    {customer.firstName} {customer.lastName}
                  </div>
                  {customer.email && (
                    <div className="text-xs text-[#71717A] truncate mt-0.5">{customer.email}</div>
                  )}
                  {healthMap[customer.id] && (
                    <div className="mt-1.5">
                      <HealthChip
                        size="xs"
                        score={healthMap[customer.id].score}
                        segment={healthMap[customer.id].segment}
                      />
                    </div>
                  )}
                </button>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => navigate(`/admin/customers/${customer.id}/360`)} className="p-2 hover:bg-[#E0E7FF] rounded-lg" data-testid={`view-customer-mob-${customer.id}`}><Eye size={16} className="text-[#4F46E5]" /></button>
                  <button onClick={() => openEditModal(customer)} className="p-2 hover:bg-[#F4F4F5] rounded-lg" data-testid={`edit-customer-mob-${customer.id}`}><Pencil size={16} className="text-[#71717A]" /></button>
                  <button onClick={() => handleDelete(customer.id)} className="p-2 hover:bg-[#FEE2E2] rounded-lg" data-testid={`delete-customer-mob-${customer.id}`}><Trash size={16} className="text-[#DC2626]" /></button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
                {customer.phone && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('phone')}</div>
                    <div className="text-[#3F3F46] truncate">{customer.phone}</div>
                  </div>
                )}
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('type')}</div>
                  <div className="text-[#3F3F46] truncate">{typeLabels[customer.type] || '—'}</div>
                </div>
                {customer.company && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('company')}</div>
                    <div className="text-[#3F3F46] truncate">{customer.company}</div>
                  </div>
                )}
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('dealsCount')}</div>
                  <div className="text-[#3F3F46]">
                    <span className="font-semibold text-[#18181B]">{customer.totalDeals || 0}</span>
                    <span className="text-xs text-[#71717A] ml-1">(${(customer.totalRevenue || customer.totalValue || 0).toLocaleString()})</span>
                  </div>
                </div>
                <div className="col-span-2 flex items-center justify-between pt-2 mt-1 border-t border-[#F4F4F5]">
                  <span className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">Owner</span>
                  {customer.managerId && managersMap[customer.managerId] ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#18181B] truncate max-w-[140px]">{managersMap[customer.managerId].name || managersMap[customer.managerId].email}</span>
                      {canReassign && (
                        <button
                          onClick={() => setReassignTarget({ ids: [customer.id], currentManagerId: customer.managerId })}
                          className="p-1.5 hover:bg-[#EEF2FF] rounded-lg"
                          data-testid={`reassign-customer-mob-${customer.id}`}
                        >
                          <ArrowsClockwise size={14} className="text-[#4F46E5]" />
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#A1A1AA] italic">unassigned</span>
                      {canReassign && (
                        <button
                          onClick={() => setReassignTarget({ ids: [customer.id], currentManagerId: null })}
                          className="px-2 py-1 bg-[#4F46E5] text-white text-[10px] font-semibold rounded-md"
                          data-testid={`reassign-customer-mob-${customer.id}`}
                        >
                          Assign
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-[calc(100%-2rem)] sm:max-w-md bg-white rounded-2xl border border-[#E4E4E7] max-h-[90vh] overflow-y-auto" data-testid="customer-modal">
          <DialogHeader><DialogTitle className="text-lg sm:text-xl font-bold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{editingCustomer ? t('editCustomer') : t('newCustomer')}</DialogTitle></DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5 mt-4">
            {/* Helper banner — what a "customer" means here */}
            <div className="rounded-xl bg-[#ECFDF5] border border-[#10B981]/30 px-3 py-2 text-[12px] text-[#065F46] leading-relaxed">
              {t('customer_helper_banner')}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('firstName')} <span className="text-[#DC2626]">*</span></label>
                <input
                  type="text"
                  value={formData.firstName}
                  onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                  required
                  className={`input w-full ${formErrors.firstName ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`}
                  data-testid="customer-firstname-input"
                />
                {formErrors.firstName ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.firstName}</p> : null}
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('lastName')} <span className="text-[#DC2626]">*</span></label>
                <input
                  type="text"
                  value={formData.lastName}
                  onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                  required
                  className={`input w-full ${formErrors.lastName ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`}
                  data-testid="customer-lastname-input"
                />
                {formErrors.lastName ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.lastName}</p> : null}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('email')} <span className="text-[#DC2626]">*</span></label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                className={`input w-full ${formErrors.email ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`}
                placeholder="name@example.com"
                data-testid="customer-email-input"
              />
              {formErrors.email ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.email}</p> : null}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('phone')} <span className="text-[#DC2626]">*</span></label>
                <PhoneInput
                  value={formData.phone}
                  country={formData.phoneCountry}
                  onChange={({ phone, country }) => setFormData({ ...formData, phone, phoneCountry: country })}
                  error={formErrors.phone}
                  required
                  testId="customer-phone"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('type')}</label>
                <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                  <SelectTrigger className="input" data-testid="customer-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CUSTOMER_TYPES.map((ct) => (
                      <SelectItem key={ct} value={ct}>{typeLabels[ct]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {formData.type === 'company' ? (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('company')} <span className="text-[#DC2626]">*</span></label>
                <input
                  type="text"
                  value={formData.company}
                  onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                  className={`input w-full ${formErrors.company ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`}
                  placeholder={t('customer_company_ph')}
                  data-testid="customer-company-input"
                />
                {formErrors.company ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.company}</p> : null}
              </div>
            ) : null}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('lead_vehicle_interest')}</label>
              <input
                type="text"
                value={formData.vehicleInterest}
                onChange={(e) => setFormData({ ...formData, vehicleInterest: e.target.value })}
                className="input w-full"
                placeholder={t('lead_vehicle_interest_ph')}
                data-testid="customer-vehicle-interest-input"
              />
            </div>

            {/* Country direction (USA / Korea / Bulgaria / Other) */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('adm_country_direction')}</label>
              <select
                value={formData.country || ''}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                className="input w-full"
                data-testid="customer-country-direction"
              >
                <option value="">—</option>
                <option value="USA">USA</option>
                <option value="Korea">Korea</option>
                <option value="Bulgaria">Bulgaria</option>
                <option value="Other">Other</option>
              </select>
            </div>

            {/* Wishes — budget + timeline + note */}
            <div className="border border-[#E4E4E7] rounded-xl p-3 space-y-3 bg-[#FAFAFA]" data-testid="customer-wishes-block">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">{t('adm_customer_wishes')}</p>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10.5px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_budget_min')}</label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={formData.wishes?.budget_min ?? ''}
                    onChange={(e) => setFormData({ ...formData, wishes: { ...formData.wishes, budget_min: e.target.value } })}
                    className="input w-full"
                    data-testid="customer-budget-min"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-[10.5px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_budget_max')}</label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={formData.wishes?.budget_max ?? ''}
                    onChange={(e) => setFormData({ ...formData, wishes: { ...formData.wishes, budget_max: e.target.value } })}
                    className="input w-full"
                    data-testid="customer-budget-max"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-[10.5px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_currency')}</label>
                  <select
                    value={formData.wishes?.currency || 'EUR'}
                    onChange={(e) => setFormData({ ...formData, wishes: { ...formData.wishes, currency: e.target.value } })}
                    className="input w-full"
                    data-testid="customer-currency"
                  >
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                    <option value="BGN">BGN</option>
                    <option value="UAH">UAH</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-[10.5px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_timeline_months')}</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={formData.wishes?.timeline_months ?? ''}
                  onChange={(e) => setFormData({ ...formData, wishes: { ...formData.wishes, timeline_months: e.target.value } })}
                  className="input w-full"
                  data-testid="customer-timeline-months"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-[10.5px] uppercase tracking-wider text-[#71717A] mb-1">{t('adm_wish_note')}</label>
                <textarea
                  value={formData.wishes?.note || ''}
                  onChange={(e) => setFormData({ ...formData, wishes: { ...formData.wishes, note: e.target.value } })}
                  rows={2}
                  className="input w-full resize-none"
                  placeholder={t('adm_wish_note_ph')}
                  data-testid="customer-wish-note"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('notes')}</label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={2}
                className="input w-full resize-none"
                placeholder={t('customer_notes_ph')}
                data-testid="customer-notes-input"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary flex-1" data-testid="customer-cancel-btn">{t('cancel')}</button>
              <button type="submit" className="btn-primary flex-1" data-testid="customer-submit-btn">{editingCustomer ? t('save') : t('create')}</button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Wave 7 — Reassign dialog */}
      {canReassign && reassignTarget && (
        <ReassignDialog
          open={!!reassignTarget}
          onClose={() => setReassignTarget(null)}
          entity="customer"
          ids={reassignTarget.ids}
          currentManagerId={reassignTarget.currentManagerId}
          onSuccess={() => {
            setSelectedIds(new Set());
            invalidateManagers();
            fetchCustomers();
          }}
        />
      )}
    </motion.div>
  );
};

export default Customers;
