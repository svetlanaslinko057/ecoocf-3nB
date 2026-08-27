/**
 * History Page (Customer Cabinet)
 * 
 * /cabinet/:customerId/history
 */

import React, { useState } from 'react';
import { FileText, MagnifyingGlass, Info } from '@phosphor-icons/react';
import { useNavigate, useParams } from 'react-router-dom';
import { useHistoryQuota } from '../../hooks/useHistoryQuota';
import { useLang } from '../../i18n';
import HistoryButton from '../../components/engagement/HistoryButton';
import HistoryReportCard from '../../components/engagement/HistoryReportCard';

export default function HistoryPage() {
  const { t } = useLang();
  const navigate = useNavigate();
  const { customerId } = useParams();
  const { quota, loading: quotaLoading, reload: reloadQuota } = useHistoryQuota();
  const [vin, setVin] = useState('');
  const [report, setReport] = useState(null);

  const handleVinChange = (e) => {
    setVin(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''));
  };

  const isValidVin = vin.length === 17;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-3 rounded-xl bg-[#F4F4F5]">
          <FileText size={24} weight="fill" className="text-[#71717A]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[#18181B]">{t('adm3_vin_1e9157951c')}</h1>
          <p className="text-[#71717A]">{t('adm3_4b1cca81e2')}</p>
        </div>
      </div>

      {/* Quota Info */}
      {!quotaLoading && quota && (
        <div className="rounded-xl bg-[#F4F4F5] p-4 flex items-center justify-between" data-testid="quota-info">
          <div className="text-[#71717A]">
            {t('adm3_c722fc049a')} <strong className="text-[#18181B]">{quota.freeRemaining}</strong> {t('r9_of')} {quota.freeReportsLimit}
          </div>
          {quota.isRestricted && (
            <span className="px-3 py-1 rounded-lg bg-red-100 text-red-600 text-sm">
              {t('adm3_5187848a68')}
            </span>
          )}
        </div>
      )}

      {/* VIN Input */}
      <div className="rounded-2xl border border-[#E4E4E7] bg-white p-6 space-y-4">
        <div className="relative">
          <MagnifyingGlass 
            size={20} 
            className="absolute left-4 top-1/2 -translate-y-1/2 text-[#A1A1AA]" 
          />
          <input
            type="text"
            value={vin}
            onChange={handleVinChange}
            placeholder={t('adm3_d68051a16d')}
            maxLength={17}
            className="w-full pl-12 pr-20 py-4 rounded-xl border border-[#E4E4E7] 
                       focus:border-[#18181B] focus:ring-2 focus:ring-[#F4F4F5] 
                       outline-none transition-all text-lg font-mono"
            data-testid="vin-input"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[#A1A1AA] text-sm">
            {vin.length}/17
          </span>
        </div>

        {isValidVin && (
          <HistoryButton 
            vin={vin}
            quota={quota}
            onLoaded={setReport}
            onQuotaChange={reloadQuota}
            size="lg"
          />
        )}

        {!isValidVin && vin.length > 0 && (
          <p className="text-amber-600 text-sm">
            {t('adm3_d5689c8de6')}
          </p>
        )}
      </div>

      {/* Report */}
      {report && <HistoryReportCard report={report} />}

      {/* Info */}
      {!report && (
        <div className="rounded-2xl bg-blue-50 border border-blue-100 p-6">
          <div className="flex items-start gap-3">
            <Info size={24} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-900 mb-2">
                {t('adm3_159f4ead03')}
              </h3>
              <ul className="space-y-2 text-blue-800 text-sm">
                <li>{t('adm3_45d8cf9c9b')}</li>
                <li>{t('adm3_43f83ae69e')}</li>
                <li>{t('adm3_9f04d01825')}</li>
                <li>{t('adm3_c710cb1905')}</li>
                <li>{t('adm3_704f9c63ac')}</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
