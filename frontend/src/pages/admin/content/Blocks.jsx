/**
 * Block editors — Phase D1.
 *
 * One React component per block type. Each takes `{ value, onChange }` and
 * renders a compact editing form. The blocks are not "live-previewed"
 * in D1 (see BlockPreview.jsx for the preview lane); the admin edits
 * fields and Save persists the normalised block array to the backend.
 */
import React from 'react';
import { Trash, Plus, X } from '@phosphor-icons/react';
import { Field, Input, Textarea, Select, Button } from '../seo/_shared';
import MediaPickerDialog from '@/components/unified/MediaPickerDialog';
import RelationPicker from '@/components/unified/RelationPicker';

// --- inline list-of-strings helper -----------------------------------
const TagList = ({ value = [], onChange, placeholder = 'додати…' }) => {
  const [txt, setTxt] = React.useState('');
  const add = () => {
    const v = txt.trim();
    if (!v) return;
    onChange([...(value || []), v]);
    setTxt('');
  };
  return (
    <div className="flex flex-wrap gap-1.5">
      {(value || []).map((t, i) => (
        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#F4F4F5] border border-[#E4E4E7] text-[12px] text-[#3F3F46]">
          {t}
          <button onClick={() => onChange(value.filter((_, idx) => idx !== i))} className="text-[#71717A] hover:text-rose-600">
            <X size={11} weight="bold" />
          </button>
        </span>
      ))}
      <div className="inline-flex items-center gap-1">
        <Input
          value={txt}
          onChange={(e) => setTxt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder={placeholder}
          className="h-7 text-[12px] w-40"
        />
        <button onClick={add} className="h-7 w-7 rounded-md border border-[#E4E4E7] hover:bg-[#F4F4F5] inline-flex items-center justify-center text-[#3F3F46]">
          <Plus size={12} weight="bold" />
        </button>
      </div>
    </div>
  );
};

// --- Repeatable-item helper -----------------------------------------
const RepeatList = ({ items = [], onChange, renderItem, addLabel = 'Додати', newItem = {} }) => (
  <div className="space-y-3">
    {(items || []).map((it, i) => (
      <div key={i} className="relative rounded-lg border border-[#E4E4E7] p-3 pr-9">
        {renderItem(it, (upd) => {
          const next = [...items];
          next[i] = { ...next[i], ...upd };
          onChange(next);
        }, i)}
        <button
          onClick={() => onChange(items.filter((_, idx) => idx !== i))}
          className="absolute top-2 right-2 h-6 w-6 rounded-md text-[#71717A] hover:text-rose-600 hover:bg-rose-50 inline-flex items-center justify-center"
        >
          <Trash size={12} weight="bold" />
        </button>
      </div>
    ))}
    <Button variant="secondary" size="sm" onClick={() => onChange([...(items || []), { ...newItem }])}>
      <Plus size={12} weight="bold" /> {addLabel}
    </Button>
  </div>
);

// ---------------------------------------------------------------------
// Individual block editors
// ---------------------------------------------------------------------

export const HeroEditor = ({ value, onChange }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    <Field label="Eyebrow"><Input value={value.eyebrow || ''} onChange={(e) => onChange({ eyebrow: e.target.value })} /></Field>
    <Field label="Variant"><Select value={value.variant || 'default'} onChange={(e) => onChange({ variant: e.target.value })}>
      <option value="default">Default</option>
      <option value="split">Split (image right)</option>
      <option value="centered">Centered</option>
    </Select></Field>
    <Field className="md:col-span-2" label="Title" required><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
    <Field className="md:col-span-2" label="Subtitle"><Textarea rows={2} value={value.subtitle || ''} onChange={(e) => onChange({ subtitle: e.target.value })} /></Field>
    <Field label="CTA label"><Input value={value.cta_label || ''} onChange={(e) => onChange({ cta_label: e.target.value })} /></Field>
    <Field label="CTA URL"><Input value={value.cta_href || ''} onChange={(e) => onChange({ cta_href: e.target.value })} placeholder="/contacts" /></Field>
    <Field label="Secondary CTA label"><Input value={value.secondary_cta_label || ''} onChange={(e) => onChange({ secondary_cta_label: e.target.value })} /></Field>
    <Field label="Secondary CTA URL"><Input value={value.secondary_cta_href || ''} onChange={(e) => onChange({ secondary_cta_href: e.target.value })} /></Field>
    <Field className="md:col-span-2" label="Image URL"><Input value={value.image_url || ''} onChange={(e) => onChange({ image_url: e.target.value })} placeholder="/api/media/…" /></Field>
    <Field className="md:col-span-2" label="Image alt"><Input value={value.image_alt || ''} onChange={(e) => onChange({ image_alt: e.target.value })} /></Field>
  </div>
);

export const RichTextEditor = ({ value, onChange }) => (
  <div className="space-y-2">
    <Field label="HTML content" hint="Підтримується обмежений HTML: p, strong, em, ul/ol/li, a, h2–h4, br">
      <Textarea rows={6} value={value.html || ''} onChange={(e) => onChange({ html: e.target.value })} />
    </Field>
    <Field label="Align"><Select value={value.align || 'left'} onChange={(e) => onChange({ align: e.target.value })}>
      <option value="left">Left</option>
      <option value="center">Center</option>
      <option value="right">Right</option>
    </Select></Field>
  </div>
);

export const ImageEditor = ({ value, onChange }) => {
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const handlePick = (asset) => {
    onChange({
      url: asset.url,
      ...(value.alt ? {} : { alt: asset.alt || asset.filename || '' }),
      ...(asset.width ? { width: asset.width } : {}),
      ...(asset.height ? { height: asset.height } : {}),
    });
  };
  return (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    <div className="md:col-span-2">
      <Field label="URL" required>
        <div className="flex items-center gap-2">
          <Input value={value.url || ''} onChange={(e) => onChange({ url: e.target.value })} placeholder="/api/media/…" />
          <Button type="button" variant="secondary" size="sm" onClick={() => setPickerOpen(true)} data-testid="image-block-pick-media">
            Медіа-бібліотека
          </Button>
        </div>
      </Field>
    </div>
    <Field label="Alt" required><Input value={value.alt || ''} onChange={(e) => onChange({ alt: e.target.value })} /></Field>
    <Field label="Caption"><Input value={value.caption || ''} onChange={(e) => onChange({ caption: e.target.value })} /></Field>
    <Field label="Width"><Input type="number" value={value.width || ''} onChange={(e) => onChange({ width: +e.target.value || 0 })} /></Field>
    <Field label="Height"><Input type="number" value={value.height || ''} onChange={(e) => onChange({ height: +e.target.value || 0 })} /></Field>
    <Field label="Link URL (optional)"><Input value={value.link_href || ''} onChange={(e) => onChange({ link_href: e.target.value })} /></Field>
    <Field label="Focus X (%)"><Input type="number" min={0} max={100} value={value.focus_x ?? 50} onChange={(e) => onChange({ focus_x: +e.target.value })} /></Field>
    <Field label="Focus Y (%)"><Input type="number" min={0} max={100} value={value.focus_y ?? 50} onChange={(e) => onChange({ focus_y: +e.target.value })} /></Field>
    <MediaPickerDialog open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={handlePick} />
  </div>
  );
};

export const GalleryEditor = ({ value, onChange }) => (
  <div className="space-y-3">
    <Field label="Layout"><Select value={value.layout || 'grid'} onChange={(e) => onChange({ layout: e.target.value })}>
      <option value="grid">Grid</option>
      <option value="carousel">Carousel</option>
      <option value="masonry">Masonry</option>
    </Select></Field>
    <div>
      <div className="text-[12px] font-medium text-[#3F3F46] mb-2">Items ({(value.items || []).length})</div>
      <RepeatList
        items={value.items || []}
        onChange={(items) => onChange({ items })}
        addLabel="Додати зображення"
        newItem={{ url: '', alt: '', caption: '' }}
        renderItem={(it, patch) => (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <Field label="URL"><Input value={it.url || ''} onChange={(e) => patch({ url: e.target.value })} /></Field>
            <Field label="Alt"><Input value={it.alt || ''} onChange={(e) => patch({ alt: e.target.value })} /></Field>
            <Field label="Caption"><Input value={it.caption || ''} onChange={(e) => patch({ caption: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
  </div>
);

export const QuoteEditor = ({ value, onChange }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    <Field className="md:col-span-2" label="Text" required><Textarea rows={3} value={value.text || ''} onChange={(e) => onChange({ text: e.target.value })} /></Field>
    <Field label="Author"><Input value={value.author || ''} onChange={(e) => onChange({ author: e.target.value })} /></Field>
    <Field label="Role"><Input value={value.role || ''} onChange={(e) => onChange({ role: e.target.value })} placeholder="CEO, Company" /></Field>
    <Field className="md:col-span-2" label="Avatar URL"><Input value={value.avatar_url || ''} onChange={(e) => onChange({ avatar_url: e.target.value })} /></Field>
  </div>
);

export const CTAEditor = ({ value, onChange }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    <Field className="md:col-span-2" label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
    <Field className="md:col-span-2" label="Description"><Textarea rows={2} value={value.description || ''} onChange={(e) => onChange({ description: e.target.value })} /></Field>
    <Field label="Button label"><Input value={value.button_label || ''} onChange={(e) => onChange({ button_label: e.target.value })} /></Field>
    <Field label="Button URL"><Input value={value.button_href || ''} onChange={(e) => onChange({ button_href: e.target.value })} /></Field>
    <Field label="Variant"><Select value={value.variant || 'primary'} onChange={(e) => onChange({ variant: e.target.value })}>
      <option value="primary">Primary</option>
      <option value="secondary">Secondary</option>
      <option value="dark">Dark</option>
    </Select></Field>
    <Field label="Align"><Select value={value.align || 'center'} onChange={(e) => onChange({ align: e.target.value })}>
      <option value="left">Left</option>
      <option value="center">Center</option>
      <option value="right">Right</option>
    </Select></Field>
  </div>
);

export const FAQEditor = ({ value, onChange }) => (
  <div className="space-y-3">
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
      <Field label="FAQ group (опційно)" hint="Береться з FAQ Engine за цією групою">
        <Input value={value.faq_group || ''} onChange={(e) => onChange({ faq_group: e.target.value })} placeholder="battery-utilization" />
      </Field>
    </div>
    <div>
      <div className="text-[12px] font-medium text-[#3F3F46] mb-2">Або введіть FAQ inline ({(value.items || []).length})</div>
      <RepeatList
        items={value.items || []}
        onChange={(items) => onChange({ items })}
        addLabel="Додати питання"
        newItem={{ question: '', answer: '' }}
        renderItem={(it, patch) => (
          <div className="space-y-2">
            <Field label="Question"><Input value={it.question || ''} onChange={(e) => patch({ question: e.target.value })} /></Field>
            <Field label="Answer (HTML)"><Textarea rows={3} value={it.answer || ''} onChange={(e) => patch({ answer: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
  </div>
);

export const ProcessEditor = ({ value, onChange }) => (
  <div className="space-y-3">
    <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
    <Field label="Description"><Textarea rows={2} value={value.description || ''} onChange={(e) => onChange({ description: e.target.value })} /></Field>
    <div>
      <div className="text-[12px] font-medium text-[#3F3F46] mb-2">Steps ({(value.steps || []).length})</div>
      <RepeatList
        items={value.steps || []}
        onChange={(steps) => onChange({ steps })}
        addLabel="Додати крок"
        newItem={{ title: '', description: '' }}
        renderItem={(it, patch) => (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Field label="Title"><Input value={it.title || ''} onChange={(e) => patch({ title: e.target.value })} /></Field>
            <Field label="Icon (optional)"><Input value={it.icon || ''} onChange={(e) => patch({ icon: e.target.value })} placeholder="phosphor-icon-name" /></Field>
            <Field className="md:col-span-2" label="Description"><Textarea rows={2} value={it.description || ''} onChange={(e) => patch({ description: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
  </div>
);

export const CardsEditor = ({ value, onChange }) => (
  <div className="space-y-3">
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
      <Field label="Description"><Input value={value.description || ''} onChange={(e) => onChange({ description: e.target.value })} /></Field>
      <Field label="Columns"><Select value={value.columns || 3} onChange={(e) => onChange({ columns: +e.target.value })}>
        <option value={1}>1</option><option value={2}>2</option><option value={3}>3</option><option value={4}>4</option>
      </Select></Field>
    </div>
    <div>
      <div className="text-[12px] font-medium text-[#3F3F46] mb-2">Cards ({(value.cards || []).length})</div>
      <RepeatList
        items={value.cards || []}
        onChange={(cards) => onChange({ cards })}
        addLabel="Додати картку"
        newItem={{ title: '', description: '' }}
        renderItem={(it, patch) => (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Field label="Title"><Input value={it.title || ''} onChange={(e) => patch({ title: e.target.value })} /></Field>
            <Field label="Href (optional)"><Input value={it.href || ''} onChange={(e) => patch({ href: e.target.value })} /></Field>
            <Field className="md:col-span-2" label="Description"><Textarea rows={2} value={it.description || ''} onChange={(e) => patch({ description: e.target.value })} /></Field>
            <Field label="Image URL"><Input value={it.image_url || ''} onChange={(e) => patch({ image_url: e.target.value })} /></Field>
            <Field label="Icon"><Input value={it.icon || ''} onChange={(e) => patch({ icon: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
  </div>
);

export const StatsEditor = ({ value, onChange }) => (
  <div className="space-y-3">
    <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
    <div>
      <div className="text-[12px] font-medium text-[#3F3F46] mb-2">Items ({(value.items || []).length})</div>
      <RepeatList
        items={value.items || []}
        onChange={(items) => onChange({ items })}
        addLabel="Додати показник"
        newItem={{ value: '', label: '' }}
        renderItem={(it, patch) => (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <Field label="Value"><Input value={it.value || ''} onChange={(e) => patch({ value: e.target.value })} /></Field>
            <Field label="Suffix"><Input value={it.suffix || ''} onChange={(e) => patch({ suffix: e.target.value })} placeholder="%, т, +" /></Field>
            <Field label="Label"><Input value={it.label || ''} onChange={(e) => patch({ label: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
  </div>
);

export const TableEditor = ({ value, onChange }) => {
  const headers = value.headers || [];
  const rows = value.rows || [];
  return (
    <div className="space-y-3">
      <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
      <Field label="Headers (Enter to add)">
        <TagList value={headers} onChange={(v) => onChange({ headers: v })} placeholder="е.g. Колонка" />
      </Field>
      <Field label={`Rows JSON (масив масивів) · ${rows.length} рядків`} hint='наприклад: [["A","B","C"],["1","2","3"]]'>
        <Textarea
          rows={6}
          value={JSON.stringify(rows, null, 2)}
          onChange={(e) => {
            try {
              const v = JSON.parse(e.target.value);
              if (Array.isArray(v)) onChange({ rows: v });
            } catch { /* ignore parse errors while typing */ }
          }}
        />
      </Field>
    </div>
  );
};

export const RelatedLinksEditor = ({ value, onChange }) => {
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const addRelation = (item) => {
    const next = [...(value.items || []), { href: item.url || '', label: item.title || '', description: item.subtitle || '' }];
    onChange({ items: next });
  };
  return (
  <div className="space-y-3">
    <div className="flex items-center justify-between">
      <Field label="Title"><Input value={value.title || ''} onChange={(e) => onChange({ title: e.target.value })} /></Field>
    </div>
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[12px] font-medium text-[#3F3F46]">Links ({(value.items || []).length})</div>
        <Button type="button" variant="secondary" size="sm" onClick={() => setPickerOpen(true)} data-testid="related-links-pick-relation">
          Обрати зв'язок
        </Button>
      </div>
      <RepeatList
        items={value.items || []}
        onChange={(items) => onChange({ items })}
        addLabel="Додати посилання"
        newItem={{ href: '', label: '' }}
        renderItem={(it, patch) => (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Field label="Label"><Input value={it.label || ''} onChange={(e) => patch({ label: e.target.value })} /></Field>
            <Field label="Href"><Input value={it.href || ''} onChange={(e) => patch({ href: e.target.value })} placeholder="/services/..." /></Field>
            <Field className="md:col-span-2" label="Description"><Input value={it.description || ''} onChange={(e) => patch({ description: e.target.value })} /></Field>
          </div>
        )}
      />
    </div>
    <RelationPicker open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={addRelation}
                    allowedTypes={["content_page", "waste_code", "blog", "faq", "seo_page"]} title="Прив'язати сторінку / код / статтю" />
  </div>
  );
};

export const BLOCK_META = {
  hero:          { label: 'Hero',          hint: 'Головний банер сторінки', Editor: HeroEditor },
  rich_text:     { label: 'Rich text',     hint: 'Текстовий блок (HTML)',       Editor: RichTextEditor },
  image:         { label: 'Image',         hint: 'Solo зображення',           Editor: ImageEditor },
  gallery:       { label: 'Gallery',       hint: 'Grid / carousel',              Editor: GalleryEditor },
  quote:         { label: 'Quote',         hint: 'Цитата / testimonial',        Editor: QuoteEditor },
  cta:           { label: 'CTA',           hint: 'Call-to-action блок',        Editor: CTAEditor },
  faq:           { label: 'FAQ',           hint: 'Група FAQ або inline',        Editor: FAQEditor },
  process:       { label: 'Process',       hint: 'Нумеровані кроки',           Editor: ProcessEditor },
  cards:         { label: 'Cards',         hint: 'Сітка карток',                Editor: CardsEditor },
  stats:         { label: 'Stats',         hint: 'Показники / metrics',         Editor: StatsEditor },
  table:         { label: 'Table',         hint: 'Таблиця',                     Editor: TableEditor },
  related_links: { label: 'Related links', hint: 'Список пов’язаних сторінок', Editor: RelatedLinksEditor },
};

export { TagList, RepeatList };
