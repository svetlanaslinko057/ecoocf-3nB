/**
 * Payment Success Page
 * 
 * /cabinet/payment-success?session_id=xxx
 * 
 * Polls payment status and shows confirmation
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { useLang } from '../../i18n';
import { 
  CheckCircle, 
  XCircle, 
  Spinner, 
  Receipt,
  ArrowLeft,
  Confetti
} from '@phosphor-icons/react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const PaymentSuccessPage = () => {
  const { t } = useLang();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');
  
  const [status, setStatus] = useState('loading'); // loading, success, failed, expired
  const [paymentData, setPaymentData] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 10;

  const pollPaymentStatus = useCallback(async () => {
    if (!sessionId) {
      setStatus('failed');
      return;
    }

    try {
      const token = localStorage.getItem('customerToken') || localStorage.getItem('token');
      const response = await axios.get(
        `${API_URL}/api/invoices/checkout/${sessionId}/status`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );

      const data = response.data;
      setPaymentData(data);

      if (data.paymentStatus === 'paid') {
        setStatus('success');
        toast.success(t('adm3_00e948ae7c'));
        return;
      }

      if (data.status === 'expired') {
        setStatus('expired');
        return;
      }

      // Keep polling if not final state
      if (attempts < maxAttempts) {
        setAttempts(prev => prev + 1);
        setTimeout(pollPaymentStatus, 2000);
      } else {
        // Timeout - but payment might still be processing
        setStatus('pending');
      }
    } catch (error) {
      console.error('Error checking payment status:', error);
      if (attempts < maxAttempts) {
        setAttempts(prev => prev + 1);
        setTimeout(pollPaymentStatus, 2000);
      } else {
        setStatus('failed');
      }
    }
  }, [sessionId, attempts]);

  useEffect(() => {
    pollPaymentStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Success State
  if (status === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-6">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center" data-testid="payment-success">
            {/* Confetti animation */}
            <div className="relative">
              <Confetti size={64} className="text-emerald-500 mx-auto mb-4 animate-bounce" weight="fill" />
            </div>
            
            <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle size={48} className="text-emerald-600" weight="fill" />
            </div>
            
            <h1 className="text-2xl font-bold text-zinc-900 mb-2">{t('adm3_00e948ae7c')}</h1>
            <p className="text-zinc-600 mb-6">{t('adm3_633c0d6130')}</p>
            
            {paymentData && (
              <div className="bg-zinc-50 rounded-xl p-4 mb-6 text-left">
                <div className="flex justify-between py-2 border-b border-zinc-200">
                  <span className="text-zinc-500">{t('adm3_3bed8fba01')}</span>
                  <span className="font-bold text-zinc-900">
                    ${(paymentData.amountTotal / 100).toLocaleString()} {paymentData.currency?.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-zinc-500">{t('adm3_7203f7a4ff')}</span>
                  <span className="text-emerald-600 font-medium">{t('adm3_6d8c085082')}</span>
                </div>
              </div>
            )}
            
            <Link
              to="/cabinet/invoices"
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 transition-colors font-medium"
              data-testid="back-to-invoices"
            >
              <Receipt size={20} />
              {t('adm3_712890eac8')}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Loading State
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center p-6">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center" data-testid="payment-processing">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Spinner size={48} className="text-blue-600 animate-spin" />
            </div>
            
            <h1 className="text-2xl font-bold text-zinc-900 mb-2">{t('adm3_66f881f42a')}</h1>
            <p className="text-zinc-600 mb-4">{t('adm3_5bef061461')}</p>
            
            <div className="flex justify-center gap-1">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                  style={{ animationDelay: `${i * 0.1}s` }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Pending State (timeout but might still succeed)
  if (status === 'pending') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 to-orange-50 flex items-center justify-center p-6">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center" data-testid="payment-pending">
            <div className="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Spinner size={48} className="text-amber-600 animate-spin" />
            </div>
            
            <h1 className="text-2xl font-bold text-zinc-900 mb-2">{t('adm3_565a35a124')}</h1>
            <p className="text-zinc-600 mb-6">
              {t('adm3_c8a249139e')}
            </p>
            
            <Link
              to="/cabinet/invoices"
              className="inline-flex items-center gap-2 px-6 py-3 bg-amber-600 text-white rounded-xl hover:bg-amber-700 transition-colors font-medium"
            >
              <ArrowLeft size={20} />
              {t('adm3_53078b2d12')}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Failed/Expired State
  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 to-rose-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center" data-testid="payment-failed">
          <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <XCircle size={48} className="text-red-600" weight="fill" />
          </div>
          
          <h1 className="text-2xl font-bold text-zinc-900 mb-2">
            {status === 'expired' ? t('adm3_826dd589dd') : t('adm3_def4f42bfc')}
          </h1>
          <p className="text-zinc-600 mb-6">
            {status === 'expired' 
              ? t('adm3_67635c5276')
              : t('adm3_d128d00ed9')
            }
          </p>
          
          <Link
            to="/cabinet/invoices"
            className="inline-flex items-center gap-2 px-6 py-3 bg-zinc-800 text-white rounded-xl hover:bg-zinc-900 transition-colors font-medium"
          >
            <ArrowLeft size={20} />
            {t('adm3_53078b2d12')}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default PaymentSuccessPage;
