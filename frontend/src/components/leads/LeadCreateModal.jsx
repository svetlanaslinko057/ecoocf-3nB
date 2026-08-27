import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import PhoneInput from '../ui/PhoneInput';
import { LEAD_SOURCES, sourceLabel } from './leadConstants';
import { useLang } from '../../i18n/LanguageContext';

const LeadCreateModal = ({
  open, onOpenChange, formData, setFormData, formErrors,
  editingLead, onSubmit, lang,
}) => {
  const { t } = useLang();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[calc(100%-2rem)] sm:max-w-lg bg-white rounded-2xl border border-[#E4E4E7] max-h-[90vh] overflow-y-auto" data-testid="lead-modal">
        <DialogHeader>
          <DialogTitle className="text-lg sm:text-xl font-bold text-[#18181B]">
            {editingLead ? t('editLead') : t('newLead')}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4 mt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('firstName')} <span className="text-[#DC2626]">*</span></label>
              <input type="text" value={formData.firstName} onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                     required className={`input w-full ${formErrors.firstName ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`} data-testid="lead-firstname-input" />
              {formErrors.firstName ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.firstName}</p> : null}
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('lastName')} <span className="text-[#DC2626]">*</span></label>
              <input type="text" value={formData.lastName} onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                     required className={`input w-full ${formErrors.lastName ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`} data-testid="lead-lastname-input" />
              {formErrors.lastName ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.lastName}</p> : null}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('email')} <span className="text-[#DC2626]">*</span></label>
            <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                   required className={`input w-full ${formErrors.email ? 'border-[#DC2626] focus:ring-[#DC2626]/30' : ''}`} data-testid="lead-email-input" placeholder="name@example.com" />
            {formErrors.email ? <p className="mt-1.5 text-[11px] text-[#DC2626]">{formErrors.email}</p> : null}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('phone')}</label>
              <PhoneInput value={formData.phone} country={formData.phoneCountry}
                          onChange={({ phone, country }) => setFormData({ ...formData, phone, phoneCountry: country })}
                          error={formErrors.phone} testId="lead-phone" />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('vehicleInterest')}</label>
              <input type="text" value={formData.vehicleInterest} onChange={(e) => setFormData({ ...formData, vehicleInterest: e.target.value })}
                     className="input w-full" placeholder="BMW X5, Audi Q7…" data-testid="lead-vehicle-interest-input" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('source')}</label>
              <Select value={formData.source} onValueChange={(v) => setFormData({ ...formData, source: v })}>
                <SelectTrigger className="input w-full" data-testid="lead-source-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LEAD_SOURCES.map((s) => (<SelectItem key={s} value={s}>{sourceLabel(lang, s)}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('leadsWs_fieldBudget')}</label>
              <input type="number" min="0" step="500" value={formData.budgetEur}
                     onChange={(e) => setFormData({ ...formData, budgetEur: e.target.value === '' ? '' : (parseInt(e.target.value, 10) || 0) })}
                     className="input w-full" placeholder="25000" data-testid="lead-budget-input" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('leadNotes')}</label>
            <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      rows={3} className="input w-full resize-none" placeholder={t('additionalInfo')} data-testid="lead-description-input" />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={() => onOpenChange(false)} className="btn-secondary flex-1" data-testid="lead-cancel-btn">{t('cancel')}</button>
            <button type="submit" className="btn-primary flex-1" data-testid="lead-submit-btn">{editingLead ? t('save') : t('create')}</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default LeadCreateModal;
