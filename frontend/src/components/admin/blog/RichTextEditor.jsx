/**
 * RichTextEditor — full-featured TipTap-based WYSIWYG editor used inside
 * the BlogArticlesEditor (and re-usable anywhere else in the admin).
 *
 * Toolbar coverage (every action wired):
 *   • Headings  H1 / H2 / H3 / H4 / paragraph
 *   • Font size (12 / 14 / 16 / 18 / 24 / 32 / 48)
 *   • Text color + Highlight color
 *   • Bold / Italic / Underline / Strikethrough
 *   • Subscript / Superscript
 *   • Bullet / Ordered / Task lists
 *   • Blockquote / Code block / Horizontal rule
 *   • Text align (left / center / right / justify)
 *   • Link (prompt) / Image (upload to /api/admin/blog/upload-image)
 *   • YouTube embed (paste any youtube.com or youtu.be URL)
 *   • Table (insert 3×3, add/remove rows / cols, toggle header)
 *   • Emoji picker (emoji-picker-react)
 *   • Undo / Redo / Clear formatting / View HTML source
 *
 * Output: HTML string (sanitized on the public side with isomorphic-dompurify).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useEditor, EditorContent } from '@tiptap/react';
import { StarterKit } from '@tiptap/starter-kit';
import { Link } from '@tiptap/extension-link';
import { Image as ImageExt } from '@tiptap/extension-image';
import { TextAlign } from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { Highlight } from '@tiptap/extension-highlight';
import { Underline } from '@tiptap/extension-underline';
import { Subscript } from '@tiptap/extension-subscript';
import { Superscript } from '@tiptap/extension-superscript';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableHeader } from '@tiptap/extension-table-header';
import { TableCell } from '@tiptap/extension-table-cell';
import { Placeholder } from '@tiptap/extension-placeholder';
import { Youtube } from '@tiptap/extension-youtube';
import { FontFamily } from '@tiptap/extension-font-family';
import { Typography } from '@tiptap/extension-typography';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';
import EmojiPicker from 'emoji-picker-react';
import {
  TextB, TextItalic, TextUnderline, TextStrikethrough,
  TextAlignLeft, TextAlignCenter, TextAlignRight, TextAlignJustify,
  ListBullets, ListNumbers, ListChecks, Quotes, Code,
  Link as LinkIcon, Image as ImageIcon, YoutubeLogo, Table as TableIcon,
  Smiley, ArrowCounterClockwise, ArrowClockwise, Eraser, MinusSquare,
  PaintBrushHousehold, Highlighter, CodeBlock,
  Plus, Minus, ArrowsHorizontal,
} from '@phosphor-icons/react';
import styles from './RichTextEditor.module.css';
import { useLang } from '../../../i18n';
import WhiteSelect from '../../../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FONT_SIZES = [12, 14, 16, 18, 24, 32, 48];
const TEXT_COLORS = [
  '#FFFFFF', '#D6D6D6', '#949494', '#FEAE00', '#FFC83F',
  '#1D1D1B', '#000000', '#FF5252', '#00B279', '#4F8EF7',
];
const HIGHLIGHT_COLORS = [
  '#FEAE00', '#FFEB99', '#FFC83F', '#FF5252', '#00B279', '#4F8EF7', '#D6D6D6', '#555452',
];

function authHeaders() {
  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function RichTextEditor({ value, onChange, placeholder, testId }) {
  const { t } = useLang();
  const fileInputRef = useRef(null);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [sourceMode, setSourceMode] = useState(false);
  const [sourceHtml, setSourceHtml] = useState(value || '');

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
        codeBlock: { HTMLAttributes: { class: 'rte-code' } },
      }),
      Underline,
      Subscript,
      Superscript,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer', class: 'rte-link' },
      }),
      ImageExt.configure({ inline: false, HTMLAttributes: { class: 'rte-image' } }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      FontFamily,
      Typography,
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: false, HTMLAttributes: { class: 'rte-table' } }),
      TableRow,
      TableHeader,
      TableCell,
      Youtube.configure({ width: 720, height: 405, nocookie: true, modestBranding: true }),
      Placeholder.configure({ placeholder: placeholder || 'Start writing your article…' }),
    ],
    content: value || '',
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange && onChange(html);
      setSourceHtml(html);
    },
  });

  // Sync external value changes (language tab switch, load)
  useEffect(() => {
    if (!editor) return;
    if ((value || '') === editor.getHTML()) return;
    editor.commands.setContent(value || '', false);
    setSourceHtml(value || '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, editor]);

  const setFontSize = useCallback((px) => {
    if (!editor) return;
    editor.chain().focus().setMark('textStyle', { fontSize: `${px}px` }).run();
  }, [editor]);

  const setColor = useCallback((c) => {
    if (!editor) return;
    editor.chain().focus().setColor(c).run();
  }, [editor]);

  const setHighlight = useCallback((c) => {
    if (!editor) return;
    editor.chain().focus().toggleHighlight({ color: c }).run();
  }, [editor]);

  const setLink = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes('link').href || '';
    // eslint-disable-next-line no-alert
    const url = window.prompt('Enter URL', prev);
    if (url === null) return;
    if (url === '') { editor.chain().focus().extendMarkRange('link').unsetLink().run(); return; }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  }, [editor]);

  const insertYoutube = useCallback(() => {
    if (!editor) return;
    // eslint-disable-next-line no-alert
    const url = window.prompt('YouTube URL (e.g. https://youtu.be/xyz)');
    if (!url) return;
    editor.chain().focus().setYoutubeVideo({ src: url }).run();
  }, [editor]);

  const insertImageFromFile = useCallback(async (file) => {
    if (!file || !editor) return;
    try {
      const fd = new FormData();
      fd.append('image', file);
      const { data } = await axios.post(`${API_URL}/api/admin/blog/upload-image`, fd, {
        headers: { ...authHeaders(), 'Content-Type': 'multipart/form-data' },
      });
      const fullUrl = data.url.startsWith('http') ? data.url : `${API_URL}${data.url}`;
      editor.chain().focus().setImage({ src: fullUrl }).run();
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert('Image upload failed: ' + (err?.response?.data?.detail || err.message));
    }
  }, [editor]);

  const insertEmoji = useCallback((emojiData) => {
    if (!editor) return;
    editor.chain().focus().insertContent(emojiData.emoji).run();
    setEmojiOpen(false);
  }, [editor]);

  const insertTable = useCallback(() => {
    if (!editor) return;
    editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
  }, [editor]);

  const toggleSourceMode = useCallback(() => {
    if (!editor) return;
    if (!sourceMode) {
      setSourceHtml(editor.getHTML());
    } else {
      editor.commands.setContent(sourceHtml || '', true);
      onChange && onChange(sourceHtml || '');
    }
    setSourceMode((v) => !v);
  }, [editor, sourceMode, sourceHtml, onChange]);

  if (!editor) return null;

  const Btn = ({ active, onClick, title, children, testId: tid, disabled }) => (
    <button
      type="button"
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      title={title}
      disabled={disabled}
      data-testid={tid}
      className={`${styles.btn} ${active ? styles.btnActive : ''}`}
    >
      {children}
    </button>
  );

  return (
    <div className={styles.wrap} data-testid={testId}>
      <div className={styles.toolbar}>
        {/* Headings */}
        <WhiteSelect
          className={styles.select}
          value={
            editor.isActive('heading', { level: 1 }) ? 'h1' :
            editor.isActive('heading', { level: 2 }) ? 'h2' :
            editor.isActive('heading', { level: 3 }) ? 'h3' :
            editor.isActive('heading', { level: 4 }) ? 'h4' :
            editor.isActive('codeBlock') ? 'code' :
            'p'
          }
          onChange={(e) => {
            const v = e.target.value;
            if (v === 'p') editor.chain().focus().setParagraph().run();
            else if (v === 'code') editor.chain().focus().setCodeBlock().run();
            else editor.chain().focus().toggleHeading({ level: parseInt(v[1], 10) }).run();
          }}
          data-testid="rte-block"
        >
          <option value="p">{t('paragraphLabel')}</option>
          <option value="h1">{t('cmp_heading_1')}</option>
          <option value="h2">{t('cmp_heading_2')}</option>
          <option value="h3">{t('cmp_heading_3')}</option>
          <option value="h4">{t('cmp_heading_4')}</option>
          <option value="code">{t('codeBlock')}</option>
        </WhiteSelect>

        {/* Font size */}
        <WhiteSelect
          className={styles.select}
          defaultValue=""
          onChange={(e) => { if (e.target.value) setFontSize(e.target.value); }}
          data-testid="rte-fontsize"
        >
          <option value="">{t('sizeLabel')}</option>
          {FONT_SIZES.map((s) => <option key={s} value={s}>{s} px</option>)}
        </WhiteSelect>

        <span className={styles.divider} />

        <Btn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold (⌘B)" testId="rte-bold"><TextB size={16} weight="bold" /></Btn>
        <Btn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic (⌘I)" testId="rte-italic"><TextItalic size={16} /></Btn>
        <Btn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Underline (⌘U)" testId="rte-underline"><TextUnderline size={16} /></Btn>
        <Btn active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title={t('strikethrough')} testId="rte-strike"><TextStrikethrough size={16} /></Btn>
        <Btn active={editor.isActive('subscript')} onClick={() => editor.chain().focus().toggleSubscript().run()} title={t('subscriptLabel')} testId="rte-sub"><span style={{ fontSize: 11, fontWeight: 600 }}>{t('cmp_x_2')}</span></Btn>
        <Btn active={editor.isActive('superscript')} onClick={() => editor.chain().focus().toggleSuperscript().run()} title={t('superscriptLabel')} testId="rte-sup"><span style={{ fontSize: 11, fontWeight: 600 }}>{t('cmp_x')}</span></Btn>
        <Btn active={editor.isActive('code')} onClick={() => editor.chain().focus().toggleCode().run()} title={t('inlineCode')}><Code size={16} /></Btn>

        <span className={styles.divider} />

        {/* Color */}
        <div className={styles.colorWrap}>
          <Btn title={t('textColor')}><PaintBrushHousehold size={16} /></Btn>
          <div className={styles.colorPop}>
            {TEXT_COLORS.map((c) => (
              <button key={c} type="button" onMouseDown={(e) => e.preventDefault()}
                onClick={() => setColor(c)} className={styles.colorSwatch}
                style={{ background: c }} title={c} />
            ))}
            <button type="button" onMouseDown={(e) => e.preventDefault()}
              onClick={() => editor.chain().focus().unsetColor().run()}
              className={`${styles.colorSwatch} ${styles.colorClear}`} title={t('resetColor')}>×</button>
          </div>
        </div>

        {/* Highlight */}
        <div className={styles.colorWrap}>
          <Btn title={t('highlightLabel')} active={editor.isActive('highlight')}><Highlighter size={16} /></Btn>
          <div className={styles.colorPop}>
            {HIGHLIGHT_COLORS.map((c) => (
              <button key={c} type="button" onMouseDown={(e) => e.preventDefault()}
                onClick={() => setHighlight(c)} className={styles.colorSwatch}
                style={{ background: c }} title={c} />
            ))}
            <button type="button" onMouseDown={(e) => e.preventDefault()}
              onClick={() => editor.chain().focus().unsetHighlight().run()}
              className={`${styles.colorSwatch} ${styles.colorClear}`} title={t('removeHighlight')}>×</button>
          </div>
        </div>

        <span className={styles.divider} />

        <Btn active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title={t('alignLeft')}><TextAlignLeft size={16} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title={t('alignCenter')}><TextAlignCenter size={16} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title={t('alignRight')}><TextAlignRight size={16} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()} title={t('justifyLabel')}><TextAlignJustify size={16} /></Btn>

        <span className={styles.divider} />

        <Btn active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} title={t('bulletList')}><ListBullets size={16} /></Btn>
        <Btn active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} title={t('numberedList')}><ListNumbers size={16} /></Btn>
        <Btn active={editor.isActive('taskList')} onClick={() => editor.chain().focus().toggleTaskList().run()} title={t('taskListLabel')}><ListChecks size={16} /></Btn>
        <Btn active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()} title={t('blockquote')}><Quotes size={16} /></Btn>
        <Btn active={editor.isActive('codeBlock')} onClick={() => editor.chain().focus().toggleCodeBlock().run()} title={t('codeBlock')}><CodeBlock size={16} /></Btn>
        <Btn onClick={() => editor.chain().focus().setHorizontalRule().run()} title={t('horizontalRule')}><MinusSquare size={16} /></Btn>

        <span className={styles.divider} />

        <Btn active={editor.isActive('link')} onClick={setLink} title={t('cmp_insert_edit_link')} testId="rte-link"><LinkIcon size={16} /></Btn>
        <Btn onClick={() => fileInputRef.current?.click()} title={t('insertImage')} testId="rte-image"><ImageIcon size={16} /></Btn>
        <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }}
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; insertImageFromFile(f); }} />
        <Btn onClick={insertYoutube} title={t('embedYoutube')} testId="rte-yt"><YoutubeLogo size={16} /></Btn>

        <span className={styles.divider} />

        {/* Table actions */}
        <Btn onClick={insertTable} title={t('cmp_insert_33_table')} testId="rte-table"><TableIcon size={16} /></Btn>
        {editor.isActive('table') && (
          <>
            <Btn onClick={() => editor.chain().focus().addColumnAfter().run()} title={t('addColumn')}><Plus size={14} /><ArrowsHorizontal size={12} /></Btn>
            <Btn onClick={() => editor.chain().focus().deleteColumn().run()} title={t('deleteColumn')}><Minus size={14} /><ArrowsHorizontal size={12} /></Btn>
            <Btn onClick={() => editor.chain().focus().addRowAfter().run()} title={t('addRow')}><Plus size={14} />R</Btn>
            <Btn onClick={() => editor.chain().focus().deleteRow().run()} title={t('deleteRow')}><Minus size={14} />R</Btn>
            <Btn onClick={() => editor.chain().focus().deleteTable().run()} title={t('deleteTable')}>⌫</Btn>
          </>
        )}

        <span className={styles.divider} />

        {/* Emoji */}
        <div className={styles.emojiWrap}>
          <Btn active={emojiOpen} onClick={() => setEmojiOpen((v) => !v)} title={t('emojiLabel')} testId="rte-emoji"><Smiley size={16} /></Btn>
          {emojiOpen && (
            <div className={styles.emojiPop}>
              <EmojiPicker
                width={320}
                height={360}
                theme="light"
                searchPlaceHolder="Search emoji…"
                onEmojiClick={insertEmoji}
                lazyLoadEmojis
              />
            </div>
          )}
        </div>

        <span className={styles.divider} />

        <Btn onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title={t('undoAction')}><ArrowCounterClockwise size={16} /></Btn>
        <Btn onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title={t('redoAction')}><ArrowClockwise size={16} /></Btn>
        <Btn onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()} title={t('clearFormatting')}><Eraser size={16} /></Btn>
        <Btn active={sourceMode} onClick={toggleSourceMode} title={t('cmp_view_edit_html')} testId="rte-html"><Code size={16} /></Btn>
      </div>

      {sourceMode ? (
        <textarea
          className={styles.sourceArea}
          value={sourceHtml}
          onChange={(e) => { setSourceHtml(e.target.value); onChange && onChange(e.target.value); }}
          spellCheck="false"
          data-testid="rte-source"
        />
      ) : (
        <EditorContent editor={editor} className={styles.editor} data-testid="rte-editor" />
      )}
      <div className={styles.statusBar}>
        <span>{editor.storage.characterCount?.characters?.() ?? editor.getText().length} chars</span>
        <span>•</span>
        <span>{editor.getText().trim().split(/\s+/).filter(Boolean).length} words</span>
      </div>
    </div>
  );
}
