/**
 * UI State Components
 * 
 * Loading, Error, Empty states для всього сайту
 */

import React from 'react';
import { Warning, SmileySad, SpinnerGap } from '@phosphor-icons/react';
import { useLang } from '../../i18n';

// Loading State
export const Loading = ({ text = 'Loading...' }) => {
  return (
    <div className="flex flex-col items-center justify-center py-16" data-testid="loading-state">
      <SpinnerGap size={48} className="text-zinc-400 animate-spin mb-4" />
      <p className="text-zinc-500 text-sm">{text}</p>
    </div>
  );
};

// Error State
export const ErrorState = ({ 
  text = 'Something went wrong', 
  onRetry 
}) => {
  const { t } = useLang();
  return (
    <div className="flex flex-col items-center justify-center py-16" data-testid="error-state">
      <Warning size={48} className="text-red-400 mb-4" />
      <p className="text-red-500 font-medium mb-2">{text}</p>
      <p className="text-zinc-400 text-sm mb-4">{t('i18n_try_again_later_d1c1b2')}</p>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800"
        >
          {t('i18n_try_again_3f2709')}
        </button>
      )}
    </div>
  );
};

// Empty State
export const Empty = ({ 
  text = 'Nothing found',
  subtext,
  icon: Icon = SmileySad,
  action,
  actionText = 'Show All'
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 bg-zinc-100 rounded-xl" data-testid="empty-state">
      <Icon size={48} className="text-zinc-300 mb-4" />
      <p className="text-zinc-500 font-medium mb-1">{text}</p>
      {subtext && <p className="text-zinc-400 text-sm">{subtext}</p>}
      {action && (
        <button 
          onClick={action}
          className="mt-4 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm hover:bg-zinc-800"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

// Page Loading (full page)
export const PageLoading = () => {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <Loading />
    </div>
  );
};

export default { Loading, ErrorState, Empty, PageLoading };
