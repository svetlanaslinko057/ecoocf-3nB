import React from 'react';
import { FileText, CheckCircle, Clock, Download } from '@phosphor-icons/react';

const contractIcon = (status) => {
  const v = (status || '').toLowerCase();
  if (['signed','active','executed','completed'].includes(v)) return CheckCircle;
  return Clock;
};

const statusCls = (status) => {
  const v = (status || '').toLowerCase();
  if (['signed','active','executed','completed'].includes(v)) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (['draft','pending','sent'].includes(v)) return 'bg-amber-50 text-amber-800 border-amber-200';
  if (['cancelled','rejected','expired'].includes(v)) return 'bg-red-50 text-red-700 border-red-200';
  return 'bg-zinc-100 text-zinc-700 border-zinc-200';
};

const DealContractsTab = ({ contracts = [] }) => {
  if (!contracts.length) {
    return (
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-8 text-center" data-testid="deal-contracts-empty">
        <FileText size={32} className="mx-auto text-[#A1A1AA] mb-2" />
        <div className="text-[#71717A]">No contracts yet</div>
      </div>
    );
  }
  return (
    <div className="space-y-2" data-testid="deal-contracts-tab">
      {contracts.map((c, i) => {
        const Icon = contractIcon(c.status);
        const url = c.signed_file_url || c.uploaded_file_url || c.file_url;
        return (
          <div key={c.id || i} className="bg-white border border-[#E4E4E7] rounded-2xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#F4F4F5] flex items-center justify-center text-[#52525B]">
                <Icon size={18} weight="bold" />
              </div>
              <div>
                <div className="font-semibold text-[#18181B]">{c.title || c.type || c.template_code || 'Contract'}</div>
                <div className="text-[12px] text-[#71717A]">
                  {c.signed_at ? `Signed ${new Date(c.signed_at).toLocaleString()}` : (c.created_at ? `Created ${new Date(c.created_at).toLocaleString()}` : '')}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 border text-[10px] uppercase tracking-wider font-bold ${statusCls(c.status)}`}>
                {c.status || 'draft'}
              </span>
              {url ? (
                <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#4F46E5] hover:underline">
                  <Download size={12} /> Open
                </a>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default DealContractsTab;
