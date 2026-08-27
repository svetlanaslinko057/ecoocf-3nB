/**
 * Shared UI primitives for the Admin SEO Center — matches the visual
 * language of the existing admin pages (rounded cards, muted borders,
 * tight typography).
 */
import React from 'react';
import { FloppyDisk, Warning, CheckCircle, Copy } from '@phosphor-icons/react';
import { toast } from 'sonner';

export const Card = ({ children, className = '' }) => (
  <section className={`rounded-2xl border border-[#E4E4E7] bg-white ${className}`}>
    {children}
  </section>
);

export const CardHeader = ({ title, subtitle, icon: Icon, right }) => (
  <header className="px-5 py-4 border-b border-[#E4E4E7] flex items-start gap-3">
    {Icon ? (
      <div className="w-9 h-9 rounded-lg bg-[#F4F4F5] text-[#18181B] flex items-center justify-center shrink-0">
        <Icon size={16} weight="bold" />
      </div>
    ) : null}
    <div className="flex-1 min-w-0">
      <h2 className="text-[14px] font-semibold text-[#18181B] leading-snug">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-[12px] text-[#71717A] leading-snug">{subtitle}</p> : null}
    </div>
    {right}
  </header>
);

export const CardBody = ({ children, className = '' }) => (
  <div className={`px-5 py-4 ${className}`}>{children}</div>
);

export const Field = ({ label, hint, required, error, children, className = '' }) => (
  <label className={`block ${className}`}>
    <div className="flex items-center gap-1.5 text-[12px] font-medium text-[#3F3F46] mb-1">
      <span>{label}</span>
      {required ? <span className="text-rose-500">*</span> : null}
    </div>
    {children}
    {hint ? <div className="mt-1 text-[11px] text-[#71717A] leading-snug">{hint}</div> : null}
    {error ? <div className="mt-1 text-[11px] text-rose-600">{error}</div> : null}
  </label>
);

export const Input = React.forwardRef((props, ref) => (
  <input
    ref={ref}
    {...props}
    className={`w-full h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 ${props.className || ''}`}
  />
));
Input.displayName = 'Input';

export const Textarea = React.forwardRef((props, ref) => (
  <textarea
    ref={ref}
    {...props}
    className={`w-full min-h-[80px] px-3 py-2 rounded-lg border border-[#E4E4E7] bg-white text-[13px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 ${props.className || ''}`}
  />
));
Textarea.displayName = 'Textarea';

export const Select = React.forwardRef((props, ref) => (
  <select
    ref={ref}
    {...props}
    className={`w-full h-9 px-3 pr-8 rounded-lg border border-[#E4E4E7] bg-white text-[13px] text-[#18181B] focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 ${props.className || ''}`}
  />
));
Select.displayName = 'Select';

export const Toggle = ({ checked, onChange, label, hint, dataTestid }) => (
  <div className="flex items-start gap-3">
    <button
      type="button"
      role="switch"
      aria-checked={!!checked}
      onClick={() => onChange(!checked)}
      data-testid={dataTestid}
      className={`shrink-0 relative inline-flex h-5 w-9 rounded-full transition ${checked ? 'bg-emerald-500' : 'bg-[#E4E4E7]'}`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition ${checked ? 'left-[18px]' : 'left-0.5'}`}
      />
    </button>
    <div className="min-w-0">
      {label ? <div className="text-[13px] font-medium text-[#18181B] leading-snug">{label}</div> : null}
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5 leading-snug">{hint}</div> : null}
    </div>
  </div>
);

export const Button = ({ variant = 'primary', size = 'md', children, className = '', ...props }) => {
  const base = 'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed';
  const sizes = { sm: 'h-8 px-3 text-[12px]', md: 'h-9 px-3.5 text-[13px]', lg: 'h-10 px-4 text-[13.5px]' };
  const variants = {
    primary:   'bg-emerald-600 text-white hover:bg-emerald-700',
    secondary: 'bg-white border border-[#E4E4E7] text-[#18181B] hover:bg-[#F4F4F5]',
    ghost:     'text-[#3F3F46] hover:bg-[#F4F4F5]',
    danger:    'bg-white border border-rose-200 text-rose-700 hover:bg-rose-50',
  };
  return (
    <button {...props} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </button>
  );
};

export const DirtyBar = ({ dirty, saving, onSave, onDiscard, savedAt, updatedBy }) => (
  <div className="sticky top-0 z-30 -mx-5 sm:mx-0 mb-4 py-2.5 px-4 rounded-none sm:rounded-xl bg-white/95 backdrop-blur border-b sm:border sm:border-[#E4E4E7] flex flex-wrap items-center gap-3">
    <div className="flex-1 min-w-[160px]">
      {dirty ? (
        <span className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
          <Warning size={11} weight="fill" /> Незбережені зміни
        </span>
      ) : savedAt ? (
        <span className="inline-flex items-center gap-1.5 text-[11.5px] text-[#71717A]">
          <CheckCircle size={11} weight="fill" className="text-emerald-500" />
          Оновлено: {new Date(savedAt).toLocaleString()}
          {updatedBy ? ` · ${updatedBy}` : ''}
        </span>
      ) : null}
    </div>
    <div className="flex items-center gap-2">
      {dirty ? (
        <Button variant="secondary" onClick={onDiscard} disabled={saving} data-testid="seo-discard">
          Скасувати
        </Button>
      ) : null}
      <Button variant="primary" onClick={onSave} disabled={!dirty || saving} data-testid="seo-save">
        <FloppyDisk size={13} weight="bold" />
        {saving ? 'Зберігаю…' : 'Зберегти'}
      </Button>
    </div>
  </div>
);

export const CopyBtn = ({ value, children }) => (
  <button
    type="button"
    onClick={() => {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(value).then(
        () => toast.success('Скопійовано'),
        () => toast.error('Не вдалося скопіювати')
      );
    }}
    className="inline-flex items-center gap-1 text-[11.5px] text-emerald-700 hover:text-emerald-800"
  >
    <Copy size={11} weight="bold" /> {children || 'Копіювати'}
  </button>
);

export const Skeleton = () => (
  <div className="space-y-4">
    <div className="h-9 rounded-lg bg-[#F4F4F5] animate-pulse" />
    <div className="h-32 rounded-lg bg-[#F4F4F5] animate-pulse" />
    <div className="h-32 rounded-lg bg-[#F4F4F5] animate-pulse" />
  </div>
);
