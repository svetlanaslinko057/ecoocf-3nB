/**
 * Select — единый белый dropdown в нашем дизайне.
 *
 * Заменяет нативный <select>, чтобы:
 *   1. Убрать серую macOS-стилизацию (`appearance: none`)
 *   2. Соответствовать дизайн-системе (белый фон, rounded-xl,
 *      border #E4E4E7, размер 12px, hover/focus тонкие)
 *   3. Работать с теми же props что и `<select>` — drop-in замена.
 *
 * Под капотом — нативный `<select>` (а значит работает без JS-popper'ов,
 * корректно на мобильном, доступно для скринридеров), но стилизованный
 * через Tailwind + кастомная стрелка.
 *
 * Использование:
 *   <Select value={x} onChange={...} testId="filter-status">
 *     <option value="">{t('all_statuses')}</option>
 *     {STATUSES.map(s => <option key={s} value={s}>{t(`contract_status_${s}`)}</option>)}
 *   </Select>
 */
import * as React from "react";
import { CaretDown } from "@phosphor-icons/react";

const Select = React.forwardRef(function Select(
  {
    value,
    onChange,
    children,
    className = "",
    size = "md",
    disabled = false,
    testId,
    placeholder,
    ...rest
  },
  ref
) {
  const sizeCls =
    size === "sm"
      ? "h-8 text-[12px] pl-3 pr-8"
      : size === "lg"
      ? "h-11 text-[14px] pl-4 pr-10"
      : "h-9 text-[12px] pl-3 pr-8";

  return (
    <div className={`relative inline-block ${className}`}>
      <select
        ref={ref}
        value={value ?? ""}
        onChange={onChange}
        disabled={disabled}
        data-testid={testId}
        className={
          `w-full appearance-none bg-white border border-[#E4E4E7] rounded-xl ` +
          `font-medium text-[#18181B] ` +
          `hover:border-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-[#18181B]/10 focus:border-[#18181B] ` +
          `disabled:bg-[#FAFAFA] disabled:text-[#A1A1AA] disabled:cursor-not-allowed ` +
          `transition-colors cursor-pointer ${sizeCls}`
        }
        {...rest}
      >
        {placeholder !== undefined ? (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        ) : null}
        {children}
      </select>
      <CaretDown
        size={12}
        weight="bold"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A]"
      />
    </div>
  );
});

export default Select;
export { Select };
