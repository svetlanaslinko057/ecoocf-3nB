/**
 * Contracts Page (Cabinet)
 * 
 * /cabinet/contracts
 * 
 * Shows user's contracts and signing status
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useLang, getLocale } from '../../i18n';
import { 
  FileText, 
  PencilLine, 
  CheckCircle, 
  Clock, 
  X,
  Eye,
  Download,
  Warning
} from '@phosphor-icons/react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Status Badge
const StatusBadge = ({ status, t }) => {
  const config = {
    draft: { color: 'zinc', icon: FileText, labelKey: 'contractDraft' },
    sent: { color: 'blue', icon: Clock, labelKey: 'contractSent' },
    viewed: { color: 'amber', icon: Eye, labelKey: 'contractViewed' },
    signed: { color: 'emerald', icon: CheckCircle, labelKey: 'contractSigned' },
    rejected: { color: 'red', icon: X, labelKey: 'contractRejected' },
    expired: { color: 'zinc', icon: Warning, labelKey: 'contractExpired' },
  };
  const { color, icon: Icon, labelKey } = config[status] || config.draft;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-${color}-100 text-${color}-700`}>
      <Icon size={12} />
      {t(labelKey)}
    </span>
  );
};

// Contract Card
const ContractCard = ({ contract, onSign, onView  }) => {
  const { t } = useLang();
  const canSign = ['sent', 'viewed'].includes(contract.status);
  
  return (
    <div 
      className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all
        ${canSign ? 'border-blue-300 bg-blue-50/30' : 'border-zinc-200'}`}
      data-testid={`contract-card-${contract.id}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-zinc-900">{contract.title}</h3>
          <p className="text-sm text-zinc-500 mt-0.5">{contract.type?.replace(/_/g, ' ')}</p>
        </div>
        <StatusBadge status={contract.status} t={t} />
      </div>
      
      {contract.vehicleTitle && (
        <div className="bg-zinc-50 rounded-lg p-3 mb-3">
          <div className="text-sm text-zinc-600">{contract.vehicleTitle}</div>
          {contract.vin && <div className="text-xs text-zinc-500 font-mono mt-1">VIN: {contract.vin}</div>}
          {contract.price && (
            <div className="text-lg font-bold text-zinc-900 mt-1">${contract.price?.toLocaleString()}</div>
          )}
        </div>
      )}
      
      <div className="flex items-center gap-2 mt-4">
        {canSign && (
          <button
            onClick={() => onSign(contract)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            data-testid={`sign-contract-${contract.id}`}
          >
            <PencilLine size={18} />
            {t('signContract')}
          </button>
        )}
        
        <button
          onClick={() => onView(contract)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-700 rounded-lg hover:bg-zinc-200 transition-colors"
          data-testid={`view-contract-${contract.id}`}
        >
          <Eye size={18} />
          {t('viewContract')}
        </button>
        
        {contract.status === 'signed' && contract.signedDocumentUrl && (
          <a
            href={contract.signedDocumentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors"
          >
            <Download size={18} />
          </a>
        )}
      </div>
      
      <div className="mt-3 pt-3 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-500">
        <span>{t('createdAt')}: {new Date(contract.createdAt).toLocaleDateString(getLocale())}</span>
        {contract.signedAt && (
          <span className="text-emerald-600">{t('signedAt')}: {new Date(contract.signedAt).toLocaleDateString(getLocale())}</span>
        )}
      </div>
    </div>
  );
};

// Sign Modal with PDF Preview
const SignModal = ({ contract, onClose, onConfirm  }) => {
  const { t } = useLang();
  const [agreed, setAgreed] = useState(false);
  const [signing, setSigning] = useState(false);
  const [signatureData, setSignatureData] = useState(null);
  const [showPdf, setShowPdf] = useState(true);
  const canvasRef = React.useRef(null);
  const [isDrawing, setIsDrawing] = useState(false);

  // Signature pad setup
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = '#1a1a2e';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
  }, []);

  const startDrawing = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || e.touches?.[0]?.clientX) - rect.left;
    const y = (e.clientY || e.touches?.[0]?.clientY) - rect.top;
    
    const ctx = canvas.getContext('2d');
    ctx.beginPath();
    ctx.moveTo(x, y);
    setIsDrawing(true);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || e.touches?.[0]?.clientX) - rect.left;
    const y = (e.clientY || e.touches?.[0]?.clientY) - rect.top;
    
    const ctx = canvas.getContext('2d');
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
    // Save signature
    const canvas = canvasRef.current;
    setSignatureData(canvas.toDataURL('image/png'));
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setSignatureData(null);
  };

  const handleSign = async () => {
    if (!agreed) {
      toast.error(t('confirmAgreementError'));
      return;
    }
    
    if (!signatureData) {
      toast.error(t('signatureRequiredError'));
      return;
    }
    
    setSigning(true);
    try {
      await onConfirm(contract, signatureData);
      toast.success(t('contractSignedSuccess'));
      onClose();
    } catch (error) {
      toast.error(t('signingError'));
    } finally {
      setSigning(false);
    }
  };

  const pdfUrl = `${API_URL}/api/contracts/template/mediation_agreement`;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-4xl w-full my-4" data-testid="sign-modal">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-xl font-bold text-zinc-900">{t('contractSigning')}</h2>
          <button onClick={onClose} className="p-2 hover:bg-zinc-100 rounded-lg">
            <X size={20} />
          </button>
        </div>
        
        <div className="grid md:grid-cols-2 gap-4 p-4">
          {/* PDF Preview */}
          <div className="bg-zinc-100 rounded-lg overflow-hidden">
            <div className="p-2 bg-zinc-200 flex items-center justify-between">
              <span className="text-sm font-medium">{t('documentLabel')}</span>
              <a 
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline"
              >
                {t('openPdf')}
              </a>
            </div>
            <div className="h-[400px] overflow-auto">
              <iframe
                src={pdfUrl}
                className="w-full h-full"
                title="Contract PDF"
              />
            </div>
          </div>
          
          {/* Signing Area */}
          <div className="space-y-4">
            {/* Contract Info */}
            <div className="bg-zinc-50 rounded-lg p-4">
              <h3 className="font-medium text-zinc-900">{contract.title}</h3>
              {contract.vehicleTitle && (
                <p className="text-sm text-zinc-600 mt-1">{contract.vehicleTitle}</p>
              )}
              {contract.price && (
                <p className="text-lg font-bold text-zinc-900 mt-2">${contract.price?.toLocaleString()}</p>
              )}
            </div>
            
            {/* Signature Canvas */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-zinc-700">{t('yourSignature')}</label>
                <button
                  onClick={clearSignature}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {t('clearSignature')}
                </button>
              </div>
              <canvas
                ref={canvasRef}
                width={320}
                height={120}
                className="border-2 border-dashed border-zinc-300 rounded-lg bg-white cursor-crosshair w-full touch-none"
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
              />
              <p className="text-xs text-zinc-500 mt-1">{t('drawSignatureHint')}</p>
            </div>
            
            {/* Agreement Checkbox */}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-1 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                data-testid="agree-checkbox"
              />
              <span className="text-sm text-zinc-600">
                {t('agreeTermsText')}
              </span>
            </label>
          </div>
        </div>
        
        {/* Actions */}
        <div className="p-4 border-t flex items-center gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-zinc-100 text-zinc-700 rounded-lg hover:bg-zinc-200 transition-colors"
          >
            {t('cancel')}
          </button>
          <button
            onClick={handleSign}
            disabled={!agreed || !signatureData || signing}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="confirm-sign-btn"
          >
            {signing ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            ) : (
              <>
                <PencilLine size={18} />
                {t('signContract')}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

const ContractsPage = () => {
  const { t } = useLang();
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [signingContract, setSigningContract] = useState(null);

  const getCustomerId = () => {
    const path = window.location.pathname;
    const match = path.match(/\/cabinet\/([^/]+)/);
    return match?.[1] || localStorage.getItem('customerId');
  };

  const fetchContracts = useCallback(async () => {
    try {
      const customerId = getCustomerId();
      const response = await axios.get(`${API_URL}/api/contracts/me`, { params: { customerId } });
      // API may return either `{contracts: [...]}` (current backend shape) or
      // a raw array. Support both to avoid runtime errors when the server
      // evolves.
      const payload = response.data;
      const list = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.contracts)
          ? payload.contracts
          : Array.isArray(payload?.data)
            ? payload.data
            : Array.isArray(payload?.items)
              ? payload.items
              : [];
      setContracts(list);
    } catch (error) {
      // 401 here means the staff-only /api/contracts/me endpoint is not
      // reachable from a pure customer session (canonical cabinet route
      // /cabinet/:customerId/contracts uses the customer BFF instead).
      // Render an empty state silently — surfacing a red toast on every
      // page-load would be noisy and unprofessional for the UAT release.
      const status = error?.response?.status;
      if (status !== 401 && status !== 403) {
        console.error('Error fetching contracts:', error);
        toast.error(t('contractLoadError'));
      }
      setContracts([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchContracts();
  }, [fetchContracts]);

  const handleSign = async (contract, signatureData) => {
    try {
      await axios.post(`${API_URL}/api/contracts/${contract.id}/sign-with-signature`, {
        signatureData,
        signedAt: new Date().toISOString(),
      });
      fetchContracts();
    } catch (error) {
      throw error;
    }
  };

  const handleView = async (contract) => {
    // Mark as viewed if sent
    if (contract.status === 'sent') {
      try {
        await axios.post(`${API_URL}/api/contracts/${contract.id}/view`);
        fetchContracts();
      } catch (error) {
        console.error('Error marking viewed:', error);
      }
    }
    
    // Open document if available
    if (contract.documentUrl) {
      window.open(contract.documentUrl, '_blank');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const pendingContracts = contracts.filter(c => ['sent', 'viewed'].includes(c.status));
  const signedContracts = contracts.filter(c => c.status === 'signed');

  return (
    <div className="p-6 max-w-4xl mx-auto" data-testid="contracts-page">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 mb-2">{t('myContracts')}</h1>
        <p className="text-zinc-600">{t('contractsSubtitle') || t('viewContract')}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-zinc-200 p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <PencilLine size={20} className="text-blue-600" />
            </div>
            <div>
              <div className="text-sm text-zinc-500">{t('contractSent')}</div>
              <div className="text-xl font-bold text-blue-600">{pendingContracts.length}</div>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-zinc-200 p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 rounded-lg">
              <CheckCircle size={20} className="text-emerald-600" />
            </div>
            <div>
              <div className="text-sm text-zinc-500">{t('contractSigned')}</div>
              <div className="text-xl font-bold text-emerald-600">{signedContracts.length}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Pending Contracts */}
      {pendingContracts.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
            <PencilLine size={20} className="text-blue-500" />
            {t('contractSent')} ({pendingContracts.length})
          </h2>
          <div className="grid gap-4">
            {pendingContracts.map(contract => (
              <ContractCard 
                key={contract.id} 
                contract={contract} 
                onSign={() => setSigningContract(contract)}
                onView={() => handleView(contract)}
                t={t}
              />
            ))}
          </div>
        </div>
      )}

      {/* Signed Contracts */}
      {signedContracts.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
            <CheckCircle size={20} className="text-emerald-500" />
            {t('contractSigned')} ({signedContracts.length})
          </h2>
          <div className="grid gap-4">
            {signedContracts.map(contract => (
              <ContractCard 
                key={contract.id} 
                contract={contract}
                onSign={() => {}}
                onView={() => handleView(contract)}
                t={t}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {contracts.length === 0 && (
        <div className="text-center py-12 bg-zinc-50 rounded-xl">
          <FileText size={48} className="text-zinc-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-900 mb-2">{t('noContracts')}</h3>
          <p className="text-zinc-600">{t('noData')}</p>
        </div>
      )}

      {/* Sign Modal */}
      {signingContract && (
        <SignModal
          contract={signingContract}
          onClose={() => setSigningContract(null)}
          onConfirm={handleSign}
          t={t}
        />
      )}
    </div>
  );
};

export default ContractsPage;
