/**
 * Manager AI Widget Component
 * 
 * Displays AI-powered sales recommendations for managers
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../../App';
import { useLang } from '../../i18n';
import { 
  Lightning, 
  Phone, 
  Clock, 
  ChartLine, 
  ArrowRight,
  Sparkle,
  Warning,
  CheckCircle
} from '@phosphor-icons/react';

const urgencyColors = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

const actionIcons = {
  close_now: Lightning,
  follow_up: Clock,
  educate: ChartLine,
  nurture: CheckCircle,
};

const ManagerAIWidget = ({ leadId, userId, onAction }) => {
  const { t } = useLang();
  const [advice, setAdvice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAdvice();
  }, [leadId, userId]);

  const fetchAdvice = async () => {
    setLoading(true);
    setError(null);
    try {
      let url;
      if (leadId) {
        url = `${API_URL}/api/manager-ai/lead/${leadId}`;
      } else if (userId) {
        url = `${API_URL}/api/manager-ai/user/${userId}`;
      } else {
        throw new Error('leadId or userId required');
      }

      const res = await axios.get(url);
      setAdvice(res.data.advice);
    } catch (err) {
      setError(err.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 animate-pulse" data-testid="manager-ai-loading">
        <div className="flex items-center gap-2 mb-4">
          <Sparkle className="w-5 h-5 text-purple-500" weight="fill" />
          <span className="font-medium text-gray-700">{t('cmp_ai_recommendation')}</span>
        </div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5" data-testid="manager-ai-error">
        <div className="flex items-center gap-2 text-red-600">
          <Warning className="w-5 h-5" weight="bold" />
          <span className="font-medium">{t('cmp_ai_error')}</span>
        </div>
        <p className="mt-2 text-sm text-red-500">{error}</p>
        <button 
          onClick={fetchAdvice}
          className="mt-3 text-sm text-red-600 underline hover:no-underline"
        >
          {t('cmp_try_again')}
        </button>
      </div>
    );
  }

  if (!advice) return null;

  const ActionIcon = actionIcons[advice.action] || Lightning;

  return (
    <div className="rounded-xl border border-purple-200 bg-gradient-to-br from-purple-50 to-white p-5 shadow-sm" data-testid="manager-ai-widget">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkle className="w-5 h-5 text-purple-500" weight="fill" />
          <span className="font-semibold text-gray-800">{t('cmp_ai_recommendation')}</span>
        </div>
        <div className={`px-2 py-1 rounded-full text-xs font-medium text-white ${urgencyColors[advice.urgency]}`}>
          {advice.urgency === 'critical' ? t('adm3_7eafba1484') : 
           advice.urgency === 'high' ? t('adm3_8df17276ca') :
           advice.urgency === 'medium' ? t('adm3_a30bcda28f') : t('adm3_d4b9823769')}
        </div>
      </div>

      {/* Action Badge */}
      <div className="flex items-center gap-3 mb-4 p-3 bg-white rounded-lg border border-gray-100">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
          advice.action === 'close_now' ? 'bg-green-100 text-green-600' :
          advice.action === 'follow_up' ? 'bg-blue-100 text-blue-600' :
          advice.action === 'educate' ? 'bg-yellow-100 text-yellow-600' :
          'bg-gray-100 text-gray-600'
        }`}>
          <ActionIcon className="w-5 h-5" weight="bold" />
        </div>
        <div>
          <div className="font-medium text-gray-800">
            {advice.action === 'close_now' ? t('adm3_0f22bc9fa8') :
             advice.action === 'follow_up' ? 'Follow-up' :
             advice.action === 'educate' ? t('adm3_2a20d5f1e9') : t('adm3_1256b02375')}
          </div>
          <div className="text-xs text-gray-500">
            {t('r9_confidence_label')}: {Math.round(advice.confidence * 100)}%
          </div>
        </div>
      </div>

      {/* Message */}
      <div className="mb-4">
        <div className="text-sm text-gray-600 mb-1">{t('cmp_what_to_tell_the_customer')}</div>
        <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-800 italic">
          "{advice.messageUk || advice.message}"
        </div>
      </div>

      {/* Strategy */}
      <div className="mb-4">
        <div className="text-sm text-gray-600 mb-1">{t('cmp_strategy')}</div>
        <div className="text-sm text-gray-700">
          {advice.strategyUk || advice.strategy}
        </div>
      </div>

      {/* Price Offer */}
      {advice.offer && (advice.offer.priceSuggestion || advice.offer.discount) && (
        <div className="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
          <div className="text-sm font-medium text-green-800 mb-1">{t('cmp_price_offer')}</div>
          {advice.offer.priceSuggestion && (
            <div className="text-lg font-bold text-green-700">${advice.offer.priceSuggestion.toLocaleString()}</div>
          )}
          {advice.offer.discount && (
            <div className="text-sm text-green-600">{t('adm3_34939b62b3')}{advice.offer.discount.toLocaleString()}</div>
          )}
          {advice.offer.urgencyReason && (
            <div className="text-xs text-green-600 mt-1">{advice.offer.urgencyReason}</div>
          )}
        </div>
      )}

      {/* Next Steps */}
      {advice.nextSteps && advice.nextSteps.length > 0 && (
        <div>
          <div className="text-sm text-gray-600 mb-2">{t('cmp_next_steps')}</div>
          <ul className="space-y-1">
            {advice.nextSteps.map((step, idx) => (
              <li key={idx} className="flex items-center gap-2 text-sm text-gray-700">
                <ArrowRight className="w-3 h-3 text-purple-500" weight="bold" />
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Button */}
      {advice.action === 'close_now' && onAction && (
        <button
          onClick={() => onAction('call')}
          className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          data-testid="ai-action-call"
        >
          <Phone className="w-4 h-4" weight="bold" />
          {t('cmp_call_now')}
        </button>
      )}
    </div>
  );
};

export default ManagerAIWidget;
