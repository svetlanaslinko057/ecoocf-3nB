import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang, getLocale } from '../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { FileText, Upload, CheckCircle, XCircle, Clock, Eye, Download, Archive, MagnifyingGlass, FunnelSimple } from '@phosphor-icons/react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

const DOCUMENT_TYPES = ['contract', 'invoice', 'deposit_proof', 'client_document', 'delivery_document', 'custom'];
const DOCUMENT_STATUSES = ['draft', 'uploaded', 'pending_verification', 'verified', 'rejected', 'archived'];

const Documents = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [pendingDocs, setPendingDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const isAdminOrFinance = ['master_admin', 'team_lead', 'admin', 'finance'].includes(user?.role);

  useEffect(() => { fetchDocuments(); if (isAdminOrFinance) fetchPendingDocs(); }, [statusFilter, typeFilter]);

  const fetchDocuments = async () => { try { const params = new URLSearchParams(); if (statusFilter) params.append('status', statusFilter); if (typeFilter) params.append('type', typeFilter); const res = await axios.get(`${API_URL}/api/documents?${params}`); setDocuments(res.data.data || res.data || []); } catch (err) { toast.error(t('error')); } finally { setLoading(false); } };
  const fetchPendingDocs = async () => { try { const res = await axios.get(`${API_URL}/api/documents/queue/pending-verification`); setPendingDocs(Array.isArray(res.data) ? res.data : (res.data?.data || res.data?.items || [])); } catch (err) { console.error('Pending docs error:', err); setPendingDocs([]); } };
  const handleVerify = async (docId) => { try { await axios.post(`${API_URL}/api/documents/${docId}/verify`, { note: 'Verified' }); toast.success(t('documentVerified')); fetchDocuments(); fetchPendingDocs(); } catch (err) { toast.error(t('error')); } };
  const handleReject = async () => { if (!selectedDoc || !rejectReason) return; try { await axios.post(`${API_URL}/api/documents/${selectedDoc.id}/reject`, { reason: rejectReason }); toast.success(t('documentRejected')); setShowRejectModal(false); setRejectReason(''); setSelectedDoc(null); fetchDocuments(); fetchPendingDocs(); } catch (err) { toast.error(t('error')); } };
  const handleArchive = async (docId) => { try { await axios.post(`${API_URL}/api/documents/${docId}/archive`); toast.success(t('documentArchived')); fetchDocuments(); } catch (err) { toast.error(t('error')); } };
  const openRejectModal = (doc) => { setSelectedDoc(doc); setShowRejectModal(true); };

  const typeLabels = { contract: t('docContract'), invoice: t('docInvoice'), deposit_proof: t('docDepositProof'), client_document: t('docClientDocument'), delivery_document: t('docDeliveryDocument'), custom: t('docOther') };
  const statusLabels = { draft: t('docDraft'), uploaded: t('docUploaded'), pending_verification: t('docPendingVerification'), verified: t('docVerified'), rejected: t('docRejected'), archived: t('docArchived') };
  const statusColors = { draft: { bg: '#F4F4F5', text: '#71717A' }, uploaded: { bg: '#DBEAFE', text: '#2563EB' }, pending_verification: { bg: '#FEF3C7', text: '#D97706' }, verified: { bg: '#D1FAE5', text: '#059669' }, rejected: { bg: '#FEE2E2', text: '#DC2626' }, archived: { bg: '#F4F4F5', text: '#71717A' } };
  const filteredDocs = documents.filter(doc => { if (search) { const s = search.toLowerCase(); return doc.title?.toLowerCase().includes(s) || doc.description?.toLowerCase().includes(s); } return true; });

  return (
    <motion.div data-testid="documents-page" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('documentsTitle')}</h1>
          <p className="text-sm text-[#71717A] mt-1">{t('documentManagement')}</p>
        </div>
        {isAdminOrFinance && pendingDocs.length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-[#FEF3C7] border border-[#FCD34D] rounded-xl">
            <Clock size={18} className="text-[#D97706]" />
            <span className="text-sm font-medium text-[#92400E]">{pendingDocs.length} {t('pendingVerification')}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-5 mb-8">
        <div className="kpi-card" data-testid="docs-stat-total"><div className="mb-4"><FileText size={28} weight="duotone" className="text-[#4F46E5]" /></div><div className="kpi-value">{documents.length}</div><div className="kpi-label">{t('total')}</div></div>
        <div className="kpi-card" data-testid="docs-stat-pending"><div className="mb-4"><Clock size={28} weight="duotone" className="text-[#D97706]" /></div><div className="kpi-value">{documents.filter(d => d.status === 'pending_verification').length}</div><div className="kpi-label">{t('pendingVerification')}</div></div>
        <div className="kpi-card" data-testid="docs-stat-verified"><div className="mb-4"><CheckCircle size={28} weight="duotone" className="text-[#059669]" /></div><div className="kpi-value">{documents.filter(d => d.status === 'verified').length}</div><div className="kpi-label">{t('docVerified')}</div></div>
        <div className="kpi-card" data-testid="docs-stat-rejected"><div className="mb-4"><XCircle size={28} weight="duotone" className="text-[#DC2626]" /></div><div className="kpi-value">{documents.filter(d => d.status === 'rejected').length}</div><div className="kpi-label">{t('docRejected')}</div></div>
        <div className="kpi-card" data-testid="docs-stat-archived"><div className="mb-4"><Archive size={28} weight="duotone" className="text-[#71717A]" /></div><div className="kpi-value">{documents.filter(d => d.status === 'archived').length}</div><div className="kpi-label">{t('docArchived')}</div></div>
      </div>

      {isAdminOrFinance ? (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-[#F4F4F5] p-1 rounded-xl inline-flex">
            <TabsTrigger value="all" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium">{t('allDocuments')}</TabsTrigger>
            <TabsTrigger value="verification" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
              {t('verification')}{pendingDocs.length > 0 && <span className="w-5 h-5 rounded-full bg-[#D97706] text-white text-xs flex items-center justify-center">{pendingDocs.length}</span>}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <DocumentsTable documents={filteredDocs} loading={loading} typeLabels={typeLabels} statusLabels={statusLabels} statusColors={statusColors} statusFilter={statusFilter} setStatusFilter={setStatusFilter} typeFilter={typeFilter} setTypeFilter={setTypeFilter} search={search} setSearch={setSearch} isAdminOrFinance={isAdminOrFinance} onVerify={handleVerify} onReject={openRejectModal} onArchive={handleArchive} t={t} />
          </TabsContent>

          <TabsContent value="verification">
            <div className="section-card mb-6">
              <h3 className="font-semibold text-[#18181B] mb-4" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('verificationQueue')}</h3>
              {pendingDocs.length === 0 ? (
                <div className="text-center py-12 text-[#71717A]"><CheckCircle size={48} className="mx-auto mb-3 opacity-50" /><p>{t('noPendingDocs')}</p></div>
              ) : (
                <div className="space-y-4">
                  {pendingDocs.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between p-4 bg-[#FAFAFA] rounded-xl border border-[#E4E4E7]" data-testid={`pending-doc-${doc.id}`}>
                      <div className="flex items-center gap-4"><FileText size={28} weight="duotone" className="text-[#D97706]" /><div><p className="font-medium text-[#18181B]">{doc.title}</p><p className="text-sm text-[#71717A]">{typeLabels[doc.type] || doc.type} • {new Date(doc.createdAt).toLocaleDateString(getLocale())}</p></div></div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleVerify(doc.id)} className="flex items-center gap-2 px-4 py-2 bg-[#059669] text-white rounded-xl hover:bg-[#047857] transition-colors" data-testid={`verify-doc-${doc.id}`}><CheckCircle size={18} />{t('verify')}</button>
                        <button onClick={() => openRejectModal(doc)} className="flex items-center gap-2 px-4 py-2 bg-[#DC2626] text-white rounded-xl hover:bg-[#B91C1C] transition-colors" data-testid={`reject-doc-${doc.id}`}><XCircle size={18} />{t('reject')}</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      ) : (
        <DocumentsTable documents={filteredDocs} loading={loading} typeLabels={typeLabels} statusLabels={statusLabels} statusColors={statusColors} statusFilter={statusFilter} setStatusFilter={setStatusFilter} typeFilter={typeFilter} setTypeFilter={setTypeFilter} search={search} setSearch={setSearch} isAdminOrFinance={false} t={t} />
      )}

      <Dialog open={showRejectModal} onOpenChange={setShowRejectModal}>
        <DialogContent className="max-w-md bg-white rounded-2xl border border-[#E4E4E7]" data-testid="reject-modal">
          <DialogHeader><DialogTitle className="text-xl font-bold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('rejectDocument')}</DialogTitle></DialogHeader>
          <div className="space-y-5 mt-4">
            <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('rejectReason')}</label><textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder={t('rejectReasonPlaceholder')} rows={4} className="input w-full resize-none" data-testid="reject-reason-input" /></div>
            <div className="flex gap-3"><button onClick={() => setShowRejectModal(false)} className="btn-secondary flex-1">{t('cancel')}</button><button onClick={handleReject} disabled={!rejectReason} className="btn-primary flex-1 bg-[#DC2626] hover:bg-[#B91C1C] disabled:opacity-50" data-testid="confirm-reject-btn">{t('reject')}</button></div>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
};

const DocumentsTable = ({ documents, loading, typeLabels, statusLabels, statusColors, statusFilter, setStatusFilter, typeFilter, setTypeFilter, search, setSearch, isAdminOrFinance, onVerify, onReject, onArchive, t }) => (
  <>
    <div className="card p-5 mb-5">
      <div className="flex flex-wrap gap-4">
        <div className="relative flex-1 min-w-[200px]"><input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('searchDocuments')} className="input w-full" data-testid="docs-search-input" /></div>
        <Select value={statusFilter || "all"} onValueChange={(v) => setStatusFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-[160px] input" data-testid="docs-status-filter"><SelectValue placeholder={t('allStatuses')} /></SelectTrigger>
          <SelectContent><SelectItem value="all">{t('allStatuses')}</SelectItem>{DOCUMENT_STATUSES.map(s => <SelectItem key={s} value={s}>{statusLabels[s]}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={typeFilter || "all"} onValueChange={(v) => setTypeFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-[180px] input" data-testid="docs-type-filter"><SelectValue placeholder={t('allTypes')} /></SelectTrigger>
          <SelectContent><SelectItem value="all">{t('allTypes')}</SelectItem>{DOCUMENT_TYPES.map(dt => <SelectItem key={dt} value={dt}>{typeLabels[dt]}</SelectItem>)}</SelectContent>
        </Select>
      </div>
    </div>
    <div className="card overflow-hidden">
      {/* When there is no data, replace the whole table body with a centered
          empty state so the message never looks "stuck to a column". The
          headers stay (so users still see the column model), then we render
          an absolutely centered message under them. */}
      <div className="overflow-x-auto">
        <table className="table-premium w-full min-w-[560px]" data-testid="documents-table">
          <thead><tr><th>{t('document')}</th><th>{t('type')}</th><th>{t('status')}</th><th>{t('date')}</th>{isAdminOrFinance && <th className="text-right">{t('actions')}</th>}</tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={isAdminOrFinance ? 5 : 4} className="text-center !text-center align-middle py-12 text-[#71717A]"><div className="w-full text-center">{t('loading')}</div></td></tr>
            : documents.length === 0 ? <tr><td colSpan={isAdminOrFinance ? 5 : 4} className="!text-center align-middle py-12 text-[#71717A]"><div className="w-full flex items-center justify-center text-center">{t('noDocuments')}</div></td></tr>
            : documents.map(doc => (
              <tr key={doc.id} data-testid={`doc-row-${doc.id}`}>
                <td><div className="flex items-center gap-3"><FileText size={24} weight="duotone" className="text-[#52525B]" /><div><p className="font-medium text-[#18181B]">{doc.title || t('untitled')}</p><p className="text-xs text-[#71717A]">{doc.description || '—'}</p></div></div></td>
                <td><span className="text-sm text-[#3F3F46]">{typeLabels[doc.type] || doc.type}</span></td>
                <td><span className="badge" style={{ backgroundColor: statusColors[doc.status]?.bg || '#F4F4F5', color: statusColors[doc.status]?.text || '#71717A' }}>{statusLabels[doc.status] || doc.status}</span></td>
                <td className="text-sm text-[#71717A]">{doc.createdAt ? new Date(doc.createdAt).toLocaleDateString(getLocale()) : '—'}</td>
                {isAdminOrFinance && (
                  <td><div className="flex items-center justify-end gap-1">
                    {doc.status === 'pending_verification' && (<><button onClick={() => onVerify(doc.id)} className="p-2 hover:bg-[#F4F4F5] rounded-lg transition-colors" title={t('verify')}><CheckCircle size={18} className="text-emerald-600" /></button><button onClick={() => onReject(doc)} className="p-2 hover:bg-[#F4F4F5] rounded-lg transition-colors" title={t('reject')}><XCircle size={18} className="text-rose-600" /></button></>)}
                    {doc.status === 'verified' && <button onClick={() => onArchive(doc.id)} className="p-2 hover:bg-[#F4F4F5] rounded-lg transition-colors" title={t('archive')}><Archive size={18} className="text-[#71717A]" /></button>}
                  </div></td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </>
);

export default Documents;
