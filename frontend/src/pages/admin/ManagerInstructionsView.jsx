/**
 * BIBI Cars — Block 7.3 — Manager Instructions viewer (read-only)
 * ===================================================================
 *
 * Read-only render of the latest instructions for any staff member.
 * Safe HTML render via DOMPurify (already in deps).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import DOMPurify from 'isomorphic-dompurify';
import { ArrowsClockwise, ClockCounterClockwise, BookOpen } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const ManagerInstructionsView = () => {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API_URL}/api/manager-instructions`)
      .then((res) => setDoc(res?.data?.data || null))
      .catch((err) => setError(err?.response?.data?.detail || err?.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  const safeHtml = doc?.content_html ? DOMPurify.sanitize(doc.content_html) : '';

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6" data-testid="manager-instructions-view">
      <div className="mb-4 flex items-center gap-2">
        <BookOpen size={24} weight="duotone" className="text-[#4F46E5]" />
        <h1 className="text-xl md:text-2xl font-bold text-[#18181B]">Manager Instructions</h1>
      </div>

      {loading && (
        <div className="py-12 text-center text-[#71717A]">
          <div className="inline-flex items-center gap-2">
            <ArrowsClockwise size={16} className="animate-spin" /> Loading…
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="py-6 text-center text-sm text-[#B91C1C]">{error}</div>
      )}

      {!loading && !error && !safeHtml && (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl px-6 py-12 text-center text-[#71717A]">
          <BookOpen size={32} weight="duotone" className="mx-auto text-[#A1A1AA] mb-3" />
          No instructions have been published yet. Ask an admin to set them in <code>/admin/manager-instructions</code>.
        </div>
      )}

      {!loading && !error && safeHtml && (
        <>
          <article
            className="prose max-w-none bg-white border border-[#E4E4E7] rounded-2xl px-5 py-6"
            dangerouslySetInnerHTML={{ __html: safeHtml }}
          />
          <div className="mt-3 text-xs text-[#71717A] flex items-center gap-2">
            <ClockCounterClockwise size={14} />
            {doc?.updated_at
              ? <>Updated <b>{new Date(doc.updated_at).toLocaleString()}</b> by <b>{doc.updated_by_name || 'unknown'}</b> · v{doc.version}</>
              : null}
          </div>
        </>
      )}
    </div>
  );
};

export default ManagerInstructionsView;
