import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { CheckCircle, XCircle, Eye, CaretDown, MagnifyingGlass, Funnel, ArrowsClockwise, Car, Upload } from '@phosphor-icons/react';
import { useAuth } from '../App';
import { useLang } from '../i18n';
import WhiteSelect from '../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const ModerationPage = () => {
  const { t } = useLang();
  const { token, user } = useAuth();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending_review');
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);

  const statusConfig = {
    parsed: { label: t('parsed'), color: 'text-gray-500', bg: 'bg-gray-100' },
    normalized: { label: t('normalized'), color: 'text-blue-500', bg: 'bg-blue-100' },
    pending_review: { label: t('pendingReview'), color: 'text-yellow-600', bg: 'bg-yellow-100' },
    approved: { label: t('approved'), color: 'text-green-500', bg: 'bg-green-100' },
    rejected: { label: t('docRejected'), color: 'text-red-500', bg: 'bg-red-100' },
    published: { label: t('publishedStatus'), color: 'text-emerald-600', bg: 'bg-emerald-100' },
    unpublished: { label: t('unpublishedStatus'), color: 'text-orange-500', bg: 'bg-orange-100' },
    archived: { label: t('docArchived'), color: 'text-gray-400', bg: 'bg-gray-50' },
  };

  useEffect(() => { fetchListings(); }, [filter]);

  const fetchListings = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter && filter !== 'all') params.set('status', filter);
      params.set('limit', '50');
      const res = await axios.get(`${API_URL}/api/publishing/queue?${params.toString()}`, { headers: { Authorization: `Bearer ${token}` } });
      setListings(res.data?.data || res.data?.listings || []);
    } catch (err) {
      try { const res = await axios.get(`${API_URL}/api/vehicles?limit=50`, { headers: { Authorization: `Bearer ${token}` } }); setListings(res.data?.data || []); }
      catch { toast.error(t('error')); }
    } finally { setLoading(false); }
  };

  const handleAction = async (id, action, extraData = {}) => {
    try {
      await axios.post(`${API_URL}/api/publishing/${id}/${action}`, { userId: user?.id || 'admin', ...extraData }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(t('actionSuccess'));
      fetchListings();
    } catch (err) { toast.error(t('actionError')); }
  };

  const handleBulkAction = async (action) => {
    if (selectedIds.length === 0) { toast.warning(t('selectListings')); return; }
    try {
      await axios.post(`${API_URL}/api/publishing/bulk/${action}`, { ids: selectedIds, userId: user?.id || 'admin' }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`${t('bulkActionSuccess')} (${selectedIds.length})`);
      setSelectedIds([]);
      fetchListings();
    } catch (err) { toast.error(t('actionError')); }
  };

  const filteredListings = listings.filter(l => {
    if (!search) return true;
    const s = search.toLowerCase();
    return l.vin?.toLowerCase().includes(s) || l.make?.toLowerCase().includes(s) || l.model?.toLowerCase().includes(s) || l.title?.toLowerCase().includes(s);
  });

  const toggleSelect = (id) => { setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]); };
  const toggleSelectAll = () => { if (selectedIds.length === filteredListings.length) setSelectedIds([]); else setSelectedIds(filteredListings.map(l => l.id || l._id)); };

  return (
    <div className="space-y-6" data-testid="moderation-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">{t('moderationTitle')}</h1>
          <p className="text-zinc-500 text-sm mt-1">{t('moderationSubtitle')}</p>
        </div>
        <button onClick={fetchListings} className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-700 rounded-lg hover:bg-zinc-200"><ArrowsClockwise size={18} />{t('refresh')}</button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Funnel size={18} className="text-zinc-400" />
          <WhiteSelect value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="status-filter">
            <option value="all">{t('allStatuses')}</option>
            {Object.entries(statusConfig).map(([key, cfg]) => <option key={key} value={key}>{cfg.label}</option>)}
          </WhiteSelect>
        </div>
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('searchByVinMake')} className="w-full pl-10 pr-4 py-2 border border-zinc-200 rounded-lg text-sm" />
        </div>
        {selectedIds.length > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-sm text-zinc-500">{t('selected')}: {selectedIds.length}</span>
            <button onClick={() => handleBulkAction('approve')} className="px-3 py-1.5 bg-green-500 text-white rounded-lg text-sm hover:bg-green-600">{t('approveAll')}</button>
            <button onClick={() => handleBulkAction('publish')} className="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600">{t('publishAll')}</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-4">
        {Object.entries(statusConfig).slice(0, 4).map(([status, config]) => (
          <div key={status} onClick={() => setFilter(status)} className={`p-4 rounded-xl border cursor-pointer transition-colors ${filter === status ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-200 hover:border-zinc-300'}`}>
            <p className="text-2xl font-bold text-zinc-900">{listings.filter(l => l.status === status).length || '-'}</p>
            <p className={`text-sm ${config.color}`}>{config.label}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center"><div className="w-8 h-8 border-2 border-zinc-200 border-t-zinc-900 rounded-full animate-spin mx-auto mb-4" /><p className="text-zinc-500">{t('loading')}</p></div>
        ) : filteredListings.length === 0 ? (
          <div className="p-12 text-center"><Car size={48} className="mx-auto text-zinc-300 mb-4" /><p className="text-zinc-500">{t('noListings')}</p></div>
        ) : (
          <table className="w-full">
            <thead className="bg-zinc-50 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left"><input type="checkbox" checked={selectedIds.length === filteredListings.length && filteredListings.length > 0} onChange={toggleSelectAll} className="rounded border-zinc-300" /></th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">{t('vehicle')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">VIN</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">{t('price')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">{t('status')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">{t('source')}</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">{t('actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {filteredListings.map((listing) => (
                <ListingRow key={listing.id || listing._id} listing={listing} selected={selectedIds.includes(listing.id || listing._id)} onSelect={() => toggleSelect(listing.id || listing._id)} onAction={handleAction} statusConfig={statusConfig} t={t} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

const ListingRow = ({ listing, selected, onSelect, onAction, statusConfig  }) => {
  const { t } = useLang();
  const status = statusConfig[listing.status] || statusConfig.parsed;
  const title = listing.title || `${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`.trim() || t('unknownCar');
  return (
    <tr className={`hover:bg-zinc-50 ${selected ? 'bg-blue-50' : ''}`}>
      <td className="px-4 py-3"><input type="checkbox" checked={selected} onChange={onSelect} className="rounded border-zinc-300" /></td>
      <td className="px-4 py-3"><div className="flex items-center gap-3">{listing.primaryImage ? <img src={listing.primaryImage} alt={title} className="w-12 h-12 rounded-lg object-cover" /> : <div className="w-12 h-12 bg-zinc-100 rounded-lg flex items-center justify-center"><Car size={20} className="text-zinc-400" /></div>}<div><p className="font-medium text-zinc-900 text-sm">{title}</p><p className="text-xs text-zinc-500">{listing.mileage ? `${listing.mileage.toLocaleString()} mi` : ''}{listing.damageType ? ` • ${listing.damageType}` : ''}</p></div></div></td>
      <td className="px-4 py-3"><span className="font-mono text-xs text-zinc-600">{listing.vin || '-'}</span></td>
      <td className="px-4 py-3"><span className="font-semibold text-zinc-900">{listing.currentBid || listing.buyNowPrice ? `$${(listing.currentBid || listing.buyNowPrice).toLocaleString()}` : '-'}</span></td>
      <td className="px-4 py-3"><span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>{status.label}</span></td>
      <td className="px-4 py-3"><span className="text-xs text-zinc-500 uppercase">{listing.source || '-'}</span></td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          {listing.status === 'pending_review' && (<>
            <button onClick={() => onAction(listing.id || listing._id, 'approve')} className="p-2 text-green-600 hover:bg-green-50 rounded-lg" title={t('approveAction')}><CheckCircle size={18} /></button>
            <button onClick={() => onAction(listing.id || listing._id, 'reject', { reason: t('doesNotMeetRequirements') })} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" title={t('reject')}><XCircle size={18} /></button>
          </>)}
          {listing.status === 'approved' && <button onClick={() => onAction(listing.id || listing._id, 'publish')} className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg" title={t('publishAction')}><Upload size={18} /></button>}
          {listing.status === 'published' && <button onClick={() => onAction(listing.id || listing._id, 'unpublish')} className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg" title={t('unpublishAction')}><Eye size={18} /></button>}
        </div>
      </td>
    </tr>
  );
};

export default ModerationPage;
