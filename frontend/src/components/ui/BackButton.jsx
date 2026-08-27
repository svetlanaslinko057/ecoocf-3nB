/**
 * BackButton — компактная кнопка возврата на родительскую страницу.
 *
 * <BackButton to="/team" label="Team Dashboard" />
 *   → "← Team Dashboard" — клик: navigate(to)
 *
 * <BackButton label="Back" />
 *   → "← Back" — клик: history.back()
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CaretLeft } from '@phosphor-icons/react';

const BackButton = ({ to, label, className = '', testId, ...rest }) => {
  const navigate = useNavigate();
  const handleClick = () => {
    if (to) navigate(to);
    else navigate(-1);
  };
  return (
    <button
      type="button"
      onClick={handleClick}
      data-testid={testId || 'back-button'}
      className={`inline-flex items-center gap-1.5 text-sm font-medium text-[#52525B] hover:text-[#18181B] hover:bg-[#F4F4F5] px-2.5 py-1.5 -ml-2 rounded-lg transition-colors ${className}`}
      {...rest}
    >
      <CaretLeft size={16} weight="bold" />
      <span className="truncate">{label}</span>
    </button>
  );
};

export default BackButton;
