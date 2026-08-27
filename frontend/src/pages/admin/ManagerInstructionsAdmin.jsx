/* eslint-disable */
/**
 * BIBI Cars — Block 7.3 — Manager Instructions admin editor
 * ============================================================
 *
 * Rich text editor (TipTap) where admins/master_admin maintain a single
 * canonical document of operating instructions for the sales team.
 *
 * Save semantics: PUT /api/manager-instructions stores HTML + version + actor.
 * Read endpoint: GET /api/manager-instructions returns the latest.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import Placeholder from '@tiptap/extension-placeholder';
import {
  FloppyDisk, ArrowsClockwise, ListBullets, ListNumbers, LinkSimple, Code, ArrowUUpLeft, ArrowUUpRight,
  Quotes, ClockCounterClockwise, TextB, TextItalic, TextUnderline,
} from '@phosphor-icons/react';
import { API_URL } from '../../App';

const ToolbarBtn = ({ active, onClick, title, children, disabled }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    disabled={disabled}
    className={`p-2 rounded-lg transition-colors flex items-center justify-center
      ${active ? 'bg-[#18181B] text-white' : 'bg-white text-[#3F3F46] hover:bg-[#F4F4F5]'}
      ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    data-testid={`mi-btn-${title.toLowerCase().replace(/\s+/g, '-')}`}
  >
    {children}
  </button>
);

const ManagerInstructionsAdmin = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [meta, setMeta] = useState({ updated_at: null, updated_by_name: null, version: 0 });

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Link.configure({ openOnClick: false, autolink: true }),
      Placeholder.configure({ placeholder: 'Write the manager instructions here…' }),
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'prose max-w-none min-h-[400px] focus:outline-none px-4 py-3',
      },
    },
  });

  // Initial load
  useEffect(() => {
    if (!editor) return;
    let cancelled = false;
    setLoading(true);
    axios.get(`${API_URL}/api/manager-instructions`)
      .then((res) => {
        if (cancelled) return;
        const d = res?.data?.data || {};
        editor.commands.setContent(d.content_html || '', false);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setMeta({
          updated_at: d.updated_at,
          updated_by_name: d.updated_by_name,
          version: d.version || 0,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err?.response?.data?.detail || err?.message || 'Failed to load';
        toast.error(msg);
      })
      .finally(() => {
        if (cancelled) return;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [editor]);

  const handleSave = useCallback(async () => {
    if (!editor) return;
    setSaving(true);
    try {
      const html = editor.getHTML();
      const text = editor.getText();
      const res = await axios.put(`${API_URL}/api/manager-instructions`, {
        content_html: html,
        content_text: text,
      });
      const d = res?.data?.data || {};
      setMeta({
        updated_at: d.updated_at,
        updated_by_name: d.updated_by_name,
        version: d.version || 0,
      });
      toast.success(`Saved (v${d.version || '?'})`);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Save failed';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }, [editor]);

  const setLink = () => {
    if (!editor) return;
    const previous = editor.getAttributes('link').href;
    const url = window.prompt('URL', previous || 'https://');
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url, target: '_blank' }).run();
  };

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-6" data-testid="manager-instructions-admin">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-[#18181B]">Manager Instructions</h1>
          <p className="text-sm text-[#71717A] mt-1">
            Single source of truth for the sales / support team. Edit, save — visible to every staff member.
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !editor || loading}
          className="px-4 py-2 rounded-xl bg-[#18181B] text-white text-sm font-semibold hover:bg-[#27272A] disabled:bg-[#A1A1AA] disabled:cursor-not-allowed flex items-center gap-2"
          data-testid="mi-save"
        >
          {saving ? (
            <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving…</>
          ) : (
            <><FloppyDisk size={16} weight="bold" /> Save</>
          )}
        </button>
      </div>

      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
        {/* Toolbar */}
        <div className="border-b border-[#F4F4F5] px-3 py-2 flex flex-wrap gap-1 items-center bg-[#FAFAFA]">
          <ToolbarBtn title="Bold"      onClick={() => editor?.chain().focus().toggleBold().run()}      active={editor?.isActive('bold')}><TextB size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Italic"    onClick={() => editor?.chain().focus().toggleItalic().run()}    active={editor?.isActive('italic')}><TextItalic size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Underline" onClick={() => editor?.chain().focus().toggleUnderline().run()} active={editor?.isActive('underline')}><TextUnderline size={16} weight="bold" /></ToolbarBtn>
          <div className="w-px h-5 bg-[#E4E4E7] mx-1" />
          <ToolbarBtn title="Bulleted" onClick={() => editor?.chain().focus().toggleBulletList().run()}  active={editor?.isActive('bulletList')}><ListBullets size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Numbered" onClick={() => editor?.chain().focus().toggleOrderedList().run()} active={editor?.isActive('orderedList')}><ListNumbers size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Quote"    onClick={() => editor?.chain().focus().toggleBlockquote().run()}  active={editor?.isActive('blockquote')}><Quotes size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Code"     onClick={() => editor?.chain().focus().toggleCode().run()}        active={editor?.isActive('code')}><Code size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Link"     onClick={setLink}                                                  active={editor?.isActive('link')}><LinkSimple size={16} weight="bold" /></ToolbarBtn>
          <div className="w-px h-5 bg-[#E4E4E7] mx-1" />
          <ToolbarBtn title="H1" onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} active={editor?.isActive('heading', { level: 1 })}><span className="text-xs font-bold">H1</span></ToolbarBtn>
          <ToolbarBtn title="H2" onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} active={editor?.isActive('heading', { level: 2 })}><span className="text-xs font-bold">H2</span></ToolbarBtn>
          <ToolbarBtn title="H3" onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()} active={editor?.isActive('heading', { level: 3 })}><span className="text-xs font-bold">H3</span></ToolbarBtn>
          <div className="w-px h-5 bg-[#E4E4E7] mx-1" />
          <ToolbarBtn title="Undo" onClick={() => editor?.chain().focus().undo().run()} disabled={!editor?.can().undo()}><ArrowUUpLeft size={16} weight="bold" /></ToolbarBtn>
          <ToolbarBtn title="Redo" onClick={() => editor?.chain().focus().redo().run()} disabled={!editor?.can().redo()}><ArrowUUpRight size={16} weight="bold" /></ToolbarBtn>
        </div>

        {/* Editor */}
        {loading ? (
          <div className="px-4 py-16 text-center text-[#71717A]">
            <div className="inline-flex items-center gap-2"><ArrowsClockwise size={16} className="animate-spin" /> Loading…</div>
          </div>
        ) : (
          <EditorContent editor={editor} data-testid="mi-editor-content" />
        )}
      </div>

      <div className="mt-3 text-xs text-[#71717A] flex items-center gap-2">
        <ClockCounterClockwise size={14} />
        {meta.updated_at
          ? (<>Last updated <b>{new Date(meta.updated_at).toLocaleString()}</b> by <b>{meta.updated_by_name || 'unknown'}</b> · v{meta.version}</>)
          : <>No saves yet — this will be the first version.</>}
      </div>
    </div>
  );
};

export default ManagerInstructionsAdmin;
