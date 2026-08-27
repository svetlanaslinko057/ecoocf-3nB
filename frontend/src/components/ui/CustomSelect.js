/**
 * CustomSelect — legacy API wrapper around WhiteSelect.
 *
 * Совместимость с существующими вызовами (legacy callers):
 *   <CustomSelect
 *     label="Port"
 *     value={port}
 *     onChange={(val) => …}            // legacy: вызывается с value, НЕ event
 *     options={[{ value, label }]}
 *     placeholder="Select…"
 *     testId="…"
 *     dropUp                           // игнорируется — auto-flip встроен
 *   />
 *
 * Под капотом всё рендерится через WhiteSelect (portal + auto-flip + min-width),
 * чтобы поведение dropdown было единообразным во всём админ-кабинете.
 */
import React from 'react';
import WhiteSelect from './WhiteSelect';

const CustomSelect = ({
  value,
  onChange,
  options = [],
  placeholder = 'Select...',
  label,
  className = '',
  testId,
  dropUp, // legacy prop — ignored, auto-flip handled by WhiteSelect
}) => {
  // Legacy onChange contract: caller expects raw value, not event.
  // WhiteSelect passes a synthetic event {target:{value}}. Unwrap it.
  const handleChange = (e) => {
    const v = e && e.target ? e.target.value : e;
    if (typeof onChange === 'function') onChange(v);
  };

  return (
    <div className={className}>
      {label && (
        <label className="block text-xs font-medium text-[#71717A] uppercase tracking-wider mb-2">
          {label}
        </label>
      )}
      <WhiteSelect
        value={value ?? ''}
        onChange={handleChange}
        options={options}
        placeholder={placeholder}
        data-testid={testId}
      />
    </div>
  );
};

export default CustomSelect;
