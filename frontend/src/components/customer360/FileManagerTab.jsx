/**
 * Customer360 — File Manager Tab (Sprint 2 + UAT v1)
 * --------------------------------------------------
 * Adds (Launch-Candidate v1):
 *   - Per-folder metadata: size · last upload · file count
 *   - Folder descriptions (inline editable, including system folders)
 *   - Custom-folder rename (hover action)
 *   - Vehicle-photos sub-folder chips (Auction → Post-delivery)
 *   - Sub-folder navigation with breadcrumb
 *   - Image gallery with ←/→ arrows + “{i} of {n}” counter
 *   - Full i18n (UK / EN / BG) + mobile-adaptive layout
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../App';
import {
  Folder,
  FolderPlus,
  FolderOpen,
  UploadSimple,
  CloudArrowUp,
  FileText,
  FilePdf,
  Image,
  Trash,
  PencilSimple,
  Download as DownloadIcon,
  Eye,
  ArrowRight,
  X,
  CaretRight,
  CaretLeft,
  CaretLeft as CaretLeftIcon,
  FileDoc,
  FileXls,
  Plus,
  FloppyDisk,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';
import { folderDisplayName } from '../../utils/folderI18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SYSTEM_FOLDER_ICON = {
  // canonical slugs (Block 7.2)
  customer_docs:  FileText,
  vehicle_docs:   FileText,
  contracts:      FileText,
  vehicle_photos: Image,
  other:          Folder,
  // legacy English names — kept for back-compat
  Contracts:    FileText,
  Invoices:     FileText,
  Registration: FileText,
  Adaptation:   FileText,
  Photos:       Image,
  Delivery:     FileText,
  Other:        Folder,
};

const VEHICLE_PHOTO_STAGES = [
  { key: 'auction',            tk: 'fm_subfolder_auction' },
  { key: 'port_of_departure',  tk: 'fm_subfolder_port_of_departure' },
  { key: 'in_transit',         tk: 'fm_subfolder_in_transit' },
  { key: 'port_of_arrival',    tk: 'fm_subfolder_port_of_arrival' },
  { key: 'customs',            tk: 'fm_subfolder_customs' },
  { key: 'delivery',           tk: 'fm_subfolder_delivery' },
  { key: 'post_delivery',      tk: 'fm_subfolder_post_delivery' },
];

const fileIcon = (mime = '') => {
  if (mime.startsWith('image/')) return Image;
  if (mime === 'application/pdf') return FilePdf;
  if (mime.includes('word') || mime.includes('document')) return FileDoc;
  if (mime.includes('excel') || mime.includes('sheet')) return FileXls;
  return FileText;
};

const humanSize = (n) => {
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0; let v = Number(n);
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
};

const formatDate = (iso, lang) => {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    const localeMap = { uk: 'uk-UA', en: 'en-GB', bg: 'bg-BG' };
    return d.toLocaleDateString(localeMap[lang] || 'en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return iso; }
};

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const FileManagerTab = ({ customerId }) => {
  const { t, lang } = useLang();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canWrite = ['manager', 'team_lead', 'admin', 'master_admin', 'owner'].includes(role);
  const isManager = role === 'manager';
  const myId = user?.id;

  const [folders, setFolders] = useState([]);
  const [activeFolderId, setActiveFolderId] = useState(null);
  const [files, setFiles] = useState([]);
  const [loadingFolders, setLoadingFolders] = useState(true);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderDesc, setNewFolderDesc] = useState('');
  const [movingFile, setMovingFile] = useState(null);
  const [editingFile, setEditingFile] = useState(null);
  const [editFileName, setEditFileName] = useState('');
  const [editFileComment, setEditFileComment] = useState('');
  const [renamingFolderId, setRenamingFolderId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [descEditFolderId, setDescEditFolderId] = useState(null);
  const [descValue, setDescValue] = useState('');
  const [totals, setTotals] = useState({ total_files: 0, total_size_bytes: 0, folders_count: 0 });
  const fileInputRef = useRef(null);

  // Hierarchical helpers ------------------------------------------------
  const rootFolders = useMemo(
    () => folders.filter((f) => !f.parent_id),
    [folders]
  );
  const activeFolder = useMemo(
    () => folders.find((f) => f.id === activeFolderId) || null,
    [folders, activeFolderId]
  );
  const parentFolder = useMemo(
    () => (activeFolder?.parent_id ? folders.find((f) => f.id === activeFolder.parent_id) : null),
    [folders, activeFolder]
  );
  const currentSubfolders = useMemo(
    () => (activeFolder ? folders.filter((f) => f.parent_id === activeFolder.id) : []),
    [folders, activeFolder]
  );
  const isVehiclePhotosFolder = activeFolder?.slug === 'vehicle_photos' && !activeFolder?.parent_id;

  // Files restricted to images, for gallery navigation -----------------
  const imageFiles = useMemo(
    () => files.filter((f) => (f.mime_type || '').startsWith('image/')),
    [files]
  );
  const previewIndex = useMemo(
    () => (previewFile ? imageFiles.findIndex((f) => f.id === previewFile.id) : -1),
    [imageFiles, previewFile]
  );

  // Data fetches -------------------------------------------------------
  const fetchTotals = useCallback(async () => {
    try {
      const res = await axios.get(
        `${API_URL}/api/customers/${customerId}/files/totals`,
        { headers: authHeaders() }
      );
      setTotals({
        total_files:      Number(res.data?.total_files || 0),
        total_size_bytes: Number(res.data?.total_size_bytes || 0),
        folders_count:    Number(res.data?.folders_count || 0),
      });
    } catch { /* RBAC / network — leave existing values */ }
  }, [customerId]);

  const fetchFolders = useCallback(async () => {
    try {
      setLoadingFolders(true);
      const res = await axios.get(`${API_URL}/api/customers/${customerId}/folders`, { headers: authHeaders() });
      const items = res.data?.items || [];
      setFolders(items);
      setActiveFolderId((prev) => {
        if (prev && items.some((f) => f.id === prev)) return prev;
        const firstRoot = items.find((f) => !f.parent_id);
        return firstRoot ? firstRoot.id : (items[0]?.id || null);
      });
    } catch (err) {
      toast.error(t('fm_failed_to_load_folders'));
      console.error(err);
    } finally {
      setLoadingFolders(false);
    }
  }, [customerId, t]);

  const fetchFiles = useCallback(async (folderId) => {
    if (!folderId) return;
    try {
      setLoadingFiles(true);
      const res = await axios.get(
        `${API_URL}/api/customers/${customerId}/files?folder_id=${folderId}`,
        { headers: authHeaders() }
      );
      setFiles(res.data?.items || []);
    } catch (err) {
      toast.error(t('fm_failed_to_load_files'));
    } finally {
      setLoadingFiles(false);
    }
  }, [customerId, t]);

  useEffect(() => { fetchFolders(); }, [fetchFolders]);
  useEffect(() => { fetchTotals(); }, [fetchTotals]);
  useEffect(() => { if (activeFolderId) fetchFiles(activeFolderId); }, [activeFolderId, fetchFiles]);

  // Derived: only show description editor / rename for the *currently active* folder.
  const descEditing = descEditFolderId && descEditFolderId === activeFolderId;

  // Keyboard navigation in preview gallery
  useEffect(() => {
    if (!previewFile) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape') setPreviewFile(null);
      if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && imageFiles.length > 1 && previewIndex >= 0) {
        const dir = e.key === 'ArrowRight' ? 1 : -1;
        const next = (previewIndex + dir + imageFiles.length) % imageFiles.length;
        setPreviewFile(imageFiles[next]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [previewFile, imageFiles, previewIndex]);

  // Mutations ----------------------------------------------------------
  const uploadFiles = async (filesList) => {
    if (!activeFolderId || !filesList?.length) return;
    if (!canWrite) { toast.error(t('fm_no_permission_upload')); return; }
    setUploading(true);
    let okCount = 0;
    for (const file of filesList) {
      const fd = new FormData();
      fd.append('file', file);
      try {
        await axios.post(
          `${API_URL}/api/customers/${customerId}/folders/${activeFolderId}/upload`,
          fd,
          { headers: { ...authHeaders(), 'Content-Type': 'multipart/form-data' } }
        );
        okCount++;
      } catch (err) {
        const detail = err.response?.data?.detail || err.message;
        toast.error(`${file.name}: ${detail}`);
      }
    }
    setUploading(false);
    if (okCount > 0) {
      toast.success(t('fm_uploaded_n_files').replace('{n}', okCount));
      await Promise.all([fetchFiles(activeFolderId), fetchFolders(), fetchTotals()]);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (!canWrite) { toast.error(t('fm_no_permission_upload')); return; }
    const dropped = Array.from(e.dataTransfer.files || []);
    uploadFiles(dropped);
  };

  const handleFileInput = (e) => {
    const list = Array.from(e.target.files || []);
    if (list.length) uploadFiles(list);
    e.target.value = '';
  };

  const handleCreateFolder = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    try {
      await axios.post(
        `${API_URL}/api/customers/${customerId}/folders`,
        { name, description: newFolderDesc.trim() || undefined },
        { headers: authHeaders() }
      );
      toast.success(`${t('fm_create_folder')}: ${name}`);
      setNewFolderName('');
      setNewFolderDesc('');
      setCreatingFolder(false);
      await fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_create_folder_failed'));
    }
  };

  const handleCreateSubfolder = async (parentId, stageLabel) => {
    if (!parentId || !canWrite) return;
    try {
      const res = await axios.post(
        `${API_URL}/api/customers/${customerId}/folders`,
        { name: stageLabel, parent_id: parentId },
        { headers: authHeaders() }
      );
      const newId = res.data?.folder?.id;
      toast.success(`${t('fm_subfolders')}: ${stageLabel}`);
      await fetchFolders();
      if (newId) setActiveFolderId(newId);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_create_folder_failed'));
    }
  };

  const handleDeleteFile = async (file) => {
    if (!file) return;
    if (isManager && file.uploaded_by !== myId) {
      toast.error(t('fm_no_permission_delete'));
      return;
    }
    if (!window.confirm(t('fm_delete_confirm'))) return;
    try {
      await axios.delete(`${API_URL}/api/file-manager/files/${file.id}`, { headers: authHeaders() });
      toast.success(t('fm_delete'));
      await Promise.all([fetchFiles(activeFolderId), fetchFolders(), fetchTotals()]);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_delete_failed'));
    }
  };

  const handleMoveFile = async (targetFolderId) => {
    if (!movingFile) return;
    try {
      await axios.patch(
        `${API_URL}/api/file-manager/files/${movingFile.id}/move`,
        { folder_id: targetFolderId },
        { headers: authHeaders() }
      );
      const target = folders.find((f) => f.id === targetFolderId);
      toast.success(`${t('fm_move')}: ${target ? (target.is_system ? folderDisplayName(target, lang) : target.name) : ''}`);
      setMovingFile(null);
      await Promise.all([fetchFiles(activeFolderId), fetchFolders()]);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_move_failed'));
    }
  };

  const handleDeleteFolder = async (folder) => {
    const fileCount = Number(folder.file_count || 0);
    let cascade = false;
    if (fileCount > 0) {
      const msg = (t('fm_delete_folder_with_files') || 'Folder contains {n} file(s). Delete folder with all its contents?').replace('{n}', fileCount);
      if (!window.confirm(msg)) return;
      cascade = true;
    } else if (!window.confirm(t('fm_delete_folder_confirm'))) {
      return;
    }
    try {
      await axios.delete(
        `${API_URL}/api/folders/${folder.id}${cascade ? '?cascade=true' : ''}`,
        { headers: authHeaders() }
      );
      toast.success(t('fm_delete'));
      if (activeFolderId === folder.id) setActiveFolderId(folder.parent_id || null);
      await Promise.all([fetchFolders(), fetchTotals()]);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_delete_failed'));
    }
  };

  // Open inline rename / comment editor for a file
  const handleOpenEditFile = (file) => {
    if (!canWrite) return;
    setEditingFile(file);
    setEditFileName(file.original_name || file.name || '');
    setEditFileComment(file.comment || '');
  };

  const handleSaveEditFile = async () => {
    if (!editingFile) return;
    const name = editFileName.trim();
    const comment = editFileComment;
    if (!name) { toast.error(t('fm_file_name')); return; }
    try {
      await axios.patch(
        `${API_URL}/api/file-manager/files/${editingFile.id}`,
        { name, comment },
        { headers: authHeaders() }
      );
      toast.success(t('fm_save'));
      setEditingFile(null);
      await fetchFiles(activeFolderId);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_rename_failed'));
    }
  };

  const handleStartRename = (folder, e) => {
    e.stopPropagation();
    setRenamingFolderId(folder.id);
    setRenameValue(folder.name);
  };

  const handleConfirmRename = async (folder, e) => {
    if (e) e.stopPropagation();
    const newName = renameValue.trim();
    if (!newName || newName === folder.name) {
      setRenamingFolderId(null);
      return;
    }
    try {
      await axios.patch(
        `${API_URL}/api/folders/${folder.id}`,
        { name: newName },
        { headers: authHeaders() }
      );
      toast.success(t('fm_rename'));
      setRenamingFolderId(null);
      await fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_rename_failed'));
    }
  };

  const handleSaveDescription = async () => {
    if (!activeFolder) return;
    try {
      await axios.patch(
        `${API_URL}/api/folders/${activeFolder.id}`,
        { description: descValue.trim() },
        { headers: authHeaders() }
      );
      toast.success(t('fm_description_saved'));
      setDescEditFolderId(null);
      await fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('fm_rename_failed'));
    }
  };

  const downloadUrl = (file) => `${API_URL}/api/file-manager/files/${file.id}/download`;

  if (loadingFolders) {
    return (
      <div className="flex items-center justify-center h-40" data-testid="file-manager-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="file-manager-tab">
      {/* ════════ Customer-wide totals strip ════════ */}
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#52525B] px-3 py-2 bg-[#FAFAFA] border border-[#E4E4E7] rounded-lg"
        data-testid="files-customer-totals"
      >
        <span className="font-medium text-[#18181B]">{t('fm_customer_total')}:</span>
        <span data-testid="files-total-count">
          {(t('fm_customer_total_files') || '{n} file(s)').replace('{n}', totals.total_files)}
        </span>
        <span>· {t('fm_total_size')}: <span data-testid="files-total-size">{humanSize(totals.total_size_bytes)}</span></span>
        <span>· {t('fm_folders')}: {totals.folders_count}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px,1fr] gap-4">
      {/* ════════ Folder sidebar ════════ */}
      <div className="section-card !p-3">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-bold text-[#18181B] uppercase tracking-wider">
            {t('fm_folders')}
          </h3>
          {canWrite && (
            <button
              onClick={() => setCreatingFolder((v) => !v)}
              className="p-1.5 hover:bg-[#F4F4F5] rounded-lg transition-colors"
              title={t('fm_create_folder')}
              data-testid="create-folder-btn"
            >
              <FolderPlus size={16} className="text-[#4F46E5]" />
            </button>
          )}
        </div>

        {creatingFolder && canWrite && (
          <div className="mb-3 space-y-2" data-testid="create-folder-panel">
            <input
              type="text"
              autoFocus
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
              placeholder={t('fm_folder_name')}
              maxLength={80}
              className="w-full px-2.5 py-1.5 text-sm border border-[#E4E4E7] rounded-lg focus:outline-none focus:border-[#4F46E5]"
              data-testid="create-folder-input"
            />
            <textarea
              value={newFolderDesc}
              onChange={(e) => setNewFolderDesc(e.target.value)}
              placeholder={t('fm_optional_description')}
              rows={2}
              maxLength={500}
              className="w-full px-2.5 py-1.5 text-xs border border-[#E4E4E7] rounded-lg focus:outline-none focus:border-[#4F46E5] resize-none"
              data-testid="create-folder-desc"
            />
            <div className="flex gap-1">
              <button
                onClick={handleCreateFolder}
                className="flex-1 px-2 py-1 text-xs bg-[#18181B] text-white rounded-lg hover:bg-[#3F3F46]"
                data-testid="create-folder-confirm"
              >
                {t('fm_create')}
              </button>
              <button
                onClick={() => { setCreatingFolder(false); setNewFolderName(''); setNewFolderDesc(''); }}
                className="flex-1 px-2 py-1 text-xs text-[#71717A] hover:bg-[#F4F4F5] rounded-lg"
                data-testid="create-folder-cancel"
              >
                {t('fm_cancel')}
              </button>
            </div>
          </div>
        )}

        <div className="space-y-0.5">
          {rootFolders.map((f) => {
            const slug = f.slug;
            const Icon = SYSTEM_FOLDER_ICON[slug] || SYSTEM_FOLDER_ICON[f.name] || (f.is_system ? Folder : FolderOpen);
            const displayName = f.is_system ? folderDisplayName(f, lang) : f.name;
            const isActive = f.id === activeFolderId || (activeFolder?.parent_id === f.id);
            const isRenaming = renamingFolderId === f.id;
            return (
              <div
                key={f.id}
                className={`group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${
                  isActive ? 'bg-[#18181B] text-white' : 'hover:bg-[#F4F4F5] text-[#3F3F46]'
                }`}
                onClick={() => !isRenaming && setActiveFolderId(f.id)}
                data-testid={`folder-row-${slug || f.name}`}
              >
                <Icon size={16} className={isActive ? 'text-white' : (f.is_system ? 'text-[#4F46E5]' : 'text-[#71717A]')} />
                {isRenaming ? (
                  <input
                    autoFocus
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleConfirmRename(f, e);
                      if (e.key === 'Escape') setRenamingFolderId(null);
                    }}
                    onBlur={(e) => handleConfirmRename(f, e)}
                    maxLength={80}
                    className="flex-1 text-sm px-1 bg-transparent border-b border-white outline-none"
                    data-testid={`folder-rename-input-${f.id}`}
                  />
                ) : (
                  <span className="text-sm flex-1 truncate" title={f.name}>
                    {displayName}
                  </span>
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${isActive ? 'bg-white/20 text-white' : 'bg-[#F4F4F5] text-[#71717A]'}`}>
                  {f.file_count || 0}
                </span>
                {!isRenaming && !f.is_system && canWrite && (
                  <div className="flex opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => handleStartRename(f, e)}
                      className={`p-0.5 rounded ${isActive ? 'hover:bg-white/20' : 'hover:bg-[#E4E4E7]'}`}
                      title={t('fm_rename')}
                      data-testid={`folder-rename-btn-${f.id}`}
                    >
                      <PencilSimple size={11} className={isActive ? 'text-white' : 'text-[#4F46E5]'} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteFolder(f); }}
                      className={`p-0.5 rounded ${isActive ? 'hover:bg-white/20' : 'hover:bg-red-100'}`}
                      title={t('fm_delete')}
                      data-testid={`folder-delete-btn-${f.id}`}
                    >
                      <Trash size={11} className={isActive ? 'text-white' : 'text-red-600'} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ════════ Files pane ════════ */}
      <div
        className={`section-card relative transition-colors ${dragOver ? 'border-2 border-dashed border-[#4F46E5] bg-[#EEF2FF]' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        data-testid="files-pane"
      >
        {/* Header — title + breadcrumb + actions */}
        <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
          <div className="min-w-0 flex-1">
            {parentFolder && (
              <button
                onClick={() => setActiveFolderId(parentFolder.id)}
                className="inline-flex items-center gap-1 text-xs text-[#4F46E5] hover:underline mb-1"
                data-testid="folder-breadcrumb-back"
              >
                <CaretLeftIcon size={12} />
                {t('fm_back_to')} {parentFolder.is_system ? folderDisplayName(parentFolder, lang) : parentFolder.name}
              </button>
            )}
            <h3 className="text-lg font-bold text-[#18181B] truncate" data-testid="active-folder-name">
              {activeFolder ? (activeFolder.is_system ? folderDisplayName(activeFolder, lang) : activeFolder.name) : t('fm_no_folder_selected')}
            </h3>
            <div className="flex items-center gap-3 flex-wrap text-xs text-[#71717A] mt-0.5" data-testid="folder-meta">
              <span>
                {loadingFiles
                  ? `${t('fm_uploading')}`
                  : `${activeFolder?.file_count ?? files.length} ${t('fm_files')}`}
              </span>
              {(activeFolder?.total_size_bytes || 0) > 0 && (
                <span>· {t('fm_total_size')}: {humanSize(activeFolder?.total_size_bytes)}</span>
              )}
              <span>
                · {t('fm_last_upload')}: {activeFolder?.last_upload_at
                  ? formatDate(activeFolder.last_upload_at, lang)
                  : t('fm_never_uploaded')}
              </span>
              {activeFolder?.is_system && <span>· {t('fm_system_folder')}</span>}
            </div>
          </div>
          {canWrite && activeFolderId && (
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileInput}
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.doc,.docx,.xls,.xlsx"
                data-testid="file-input"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#4F46E5] text-white text-sm rounded-lg hover:bg-[#4338CA] disabled:opacity-50"
                data-testid="upload-btn"
              >
                <UploadSimple size={14} />
                {uploading ? t('fm_uploading') : t('fm_upload')}
              </button>
            </div>
          )}
        </div>

        {/* Description block — visible for any folder, editable by staff */}
        {activeFolder && (
          <div className="mb-3 px-3 py-2 bg-[#FAFAFA] border border-[#E4E4E7] rounded-lg" data-testid="folder-description-block">
            {descEditing && canWrite ? (
              <div className="space-y-2">
                <textarea
                  autoFocus
                  rows={2}
                  maxLength={500}
                  value={descValue}
                  onChange={(e) => setDescValue(e.target.value)}
                  placeholder={t('fm_folder_description')}
                  className="w-full text-xs px-2 py-1.5 border border-[#E4E4E7] rounded-lg focus:outline-none focus:border-[#4F46E5] resize-none bg-white"
                  data-testid="folder-description-input"
                />
                <div className="flex gap-1.5 justify-end">
                  <button
                    onClick={() => { setDescEditFolderId(null); setDescValue(activeFolder.description || ''); }}
                    className="px-2.5 py-1 text-xs text-[#71717A] hover:bg-[#F4F4F5] rounded-lg"
                    data-testid="folder-desc-cancel"
                  >
                    {t('fm_cancel')}
                  </button>
                  <button
                    onClick={handleSaveDescription}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs bg-[#4F46E5] text-white rounded-lg hover:bg-[#4338CA]"
                    data-testid="folder-desc-save"
                  >
                    <FloppyDisk size={11} /> {t('fm_save')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2">
                <p className="text-xs text-[#52525B] flex-1 whitespace-pre-wrap">
                  {activeFolder.description || (canWrite ? t('fm_optional_description') : '—')}
                </p>
                {canWrite && (
                  <button
                    onClick={() => { setDescEditFolderId(activeFolder.id); setDescValue(activeFolder.description || ''); }}
                    className="p-1 hover:bg-[#F4F4F5] rounded-md shrink-0"
                    title={t('fm_folder_description')}
                    data-testid="folder-desc-edit-btn"
                  >
                    <PencilSimple size={12} className="text-[#71717A]" />
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Vehicle Photos sub-folder chip strip */}
        {isVehiclePhotosFolder && (
          <div className="mb-4" data-testid="vehicle-photos-subfolders">
            <p className="text-[11px] uppercase tracking-wider text-[#71717A] mb-1.5">
              {t('fm_subfolders')}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {VEHICLE_PHOTO_STAGES.map((stage) => {
                const label = t(stage.tk);
                const existing = currentSubfolders.find((sf) => sf.name === label);
                if (existing) {
                  return (
                    <button
                      key={stage.key}
                      onClick={() => setActiveFolderId(existing.id)}
                      className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-[#EEF2FF] text-[#4F46E5] hover:bg-[#E0E7FF] border border-[#C7D2FE]"
                      data-testid={`subfolder-chip-existing-${stage.key}`}
                    >
                      <Folder size={11} />
                      {label}
                      <span className="ml-0.5 px-1.5 py-0.5 text-[10px] rounded-full bg-white/70 text-[#4F46E5]">
                        {existing.file_count || 0}
                      </span>
                    </button>
                  );
                }
                if (!canWrite) return null;
                return (
                  <button
                    key={stage.key}
                    onClick={() => handleCreateSubfolder(activeFolder.id, label)}
                    className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-white text-[#3F3F46] hover:bg-[#F4F4F5] border border-dashed border-[#A1A1AA]"
                    data-testid={`subfolder-chip-suggest-${stage.key}`}
                  >
                    <Plus size={11} />
                    {label}
                  </button>
                );
              })}
              {/* Render any "extra" custom subfolders that don't match a stage */}
              {currentSubfolders
                .filter((sf) => !VEHICLE_PHOTO_STAGES.some((s) => t(s.tk) === sf.name))
                .map((sf) => (
                  <button
                    key={sf.id}
                    onClick={() => setActiveFolderId(sf.id)}
                    className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-[#F4F4F5] text-[#3F3F46] hover:bg-[#E4E4E7] border border-[#E4E4E7]"
                    data-testid={`subfolder-chip-custom-${sf.id}`}
                  >
                    <Folder size={11} />
                    {sf.name}
                    <span className="ml-0.5 px-1.5 py-0.5 text-[10px] rounded-full bg-white text-[#71717A]">
                      {sf.file_count || 0}
                    </span>
                  </button>
                ))}
            </div>
            <p className="text-[11px] text-[#A1A1AA] mt-1.5">{t('fm_subfolder_chip_hint')}</p>
          </div>
        )}

        {dragOver && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center">
              <CloudArrowUp size={48} className="mx-auto text-[#4F46E5]" />
              <p className="text-[#4F46E5] font-medium mt-2">{t('fm_drop_files')}</p>
            </div>
          </div>
        )}

        {loadingFiles ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin w-6 h-6 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <CloudArrowUp size={32} className="mx-auto text-[#A1A1AA] mb-2" />
            <p className="text-[#71717A]">{t('fm_no_files')}</p>
            {canWrite && <p className="text-xs text-[#A1A1AA] mt-1">{t('fm_drag_files_here')}</p>}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {files.map((f) => {
              const Icon = fileIcon(f.mime_type);
              const isImage = (f.mime_type || '').startsWith('image/');
              const canDelete = canWrite && (!isManager || f.uploaded_by === myId);
              return (
                <div
                  key={f.id}
                  className="group relative bg-white border border-[#E4E4E7] rounded-xl overflow-hidden hover:border-[#4F46E5] hover:shadow-md transition-all"
                  data-testid={`file-card-${f.id}`}
                >
                  <div
                    className="h-28 bg-[#F4F4F5] flex items-center justify-center cursor-pointer relative"
                    onClick={() => setPreviewFile(f)}
                  >
                    {isImage ? (
                      <img src={downloadUrl(f)} alt={f.original_name} className="h-full w-full object-cover" loading="lazy" />
                    ) : (
                      <Icon size={36} className="text-[#71717A]" />
                    )}
                  </div>
                  <div className="p-2">
                    <p className="text-xs font-medium text-[#18181B] truncate" title={f.original_name}>
                      {f.original_name}
                    </p>
                    <p className="text-[10px] text-[#A1A1AA] mt-0.5">
                      {humanSize(f.size)} · {formatDate(f.created_at, lang)}
                    </p>
                    {f.comment && (
                      <p className="text-[10px] text-[#4F46E5] italic mt-1 truncate" title={f.comment}>
                        {f.comment}
                      </p>
                    )}
                  </div>
                  <div className="absolute top-1 right-1 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={(e) => { e.stopPropagation(); setPreviewFile(f); }} className="p-1 bg-white/90 rounded-md shadow hover:bg-white" title={t('fm_preview')} data-testid={`file-preview-${f.id}`}>
                      <Eye size={12} className="text-[#18181B]" />
                    </button>
                    <a href={downloadUrl(f)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="p-1 bg-white/90 rounded-md shadow hover:bg-white" title={t('fm_download')} data-testid={`file-download-${f.id}`}>
                      <DownloadIcon size={12} className="text-[#18181B]" />
                    </a>
                    {canWrite && (
                      <button onClick={(e) => { e.stopPropagation(); handleOpenEditFile(f); }} className="p-1 bg-white/90 rounded-md shadow hover:bg-white" title={t('fm_edit_file')} data-testid={`file-edit-${f.id}`}>
                        <PencilSimple size={12} className="text-[#18181B]" />
                      </button>
                    )}
                    {canWrite && (
                      <button onClick={(e) => { e.stopPropagation(); setMovingFile(f); }} className="p-1 bg-white/90 rounded-md shadow hover:bg-white" title={t('fm_move')} data-testid={`file-move-${f.id}`}>
                        <ArrowRight size={12} className="text-[#4F46E5]" />
                      </button>
                    )}
                    {canDelete && (
                      <button onClick={(e) => { e.stopPropagation(); handleDeleteFile(f); }} className="p-1 bg-white/90 rounded-md shadow hover:bg-red-50" title={t('fm_delete')} data-testid={`file-delete-${f.id}`}>
                        <Trash size={12} className="text-red-600" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ════════ Preview Modal with gallery navigation ════════ */}
      {previewFile && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-2 sm:p-4" onClick={() => setPreviewFile(null)} data-testid="preview-modal">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[95vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-3 border-b border-[#E4E4E7] gap-2">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[#18181B] truncate" data-testid="preview-file-name">{previewFile.original_name}</p>
                <p className="text-xs text-[#71717A]">{humanSize(previewFile.size)} · {previewFile.mime_type}</p>
              </div>
              {imageFiles.length > 1 && previewIndex >= 0 && (
                <span
                  className="text-xs text-[#71717A] px-2 py-1 bg-[#F4F4F5] rounded-md whitespace-nowrap"
                  data-testid="preview-counter"
                >
                  {t('fm_image_x_of_y').replace('{i}', previewIndex + 1).replace('{n}', imageFiles.length)}
                </span>
              )}
              <div className="flex items-center gap-2">
                <a href={downloadUrl(previewFile)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-[#4F46E5] text-white rounded-lg hover:bg-[#4338CA]" data-testid="preview-download-btn">
                  <DownloadIcon size={12} /> <span className="hidden sm:inline">{t('fm_download')}</span>
                </a>
                <button onClick={() => setPreviewFile(null)} className="p-1.5 hover:bg-[#F4F4F5] rounded-lg" data-testid="preview-close-btn">
                  <X size={16} className="text-[#71717A]" />
                </button>
              </div>
            </div>
            <div className="flex-1 bg-[#F4F4F5] overflow-auto relative">
              {(previewFile.mime_type || '').startsWith('image/') ? (
                <img src={downloadUrl(previewFile)} alt={previewFile.original_name} className="max-w-full max-h-[80vh] mx-auto block" />
              ) : (previewFile.mime_type === 'application/pdf') ? (
                <iframe src={downloadUrl(previewFile)} title="PDF preview" className="w-full h-[80vh] border-0" />
              ) : (
                <div className="text-center py-12">
                  <FileText size={48} className="mx-auto text-[#A1A1AA] mb-2" />
                  <p className="text-[#71717A]">{t('fm_no_preview')}</p>
                  <a href={downloadUrl(previewFile)} target="_blank" rel="noreferrer" className="inline-block mt-3 px-3 py-1.5 text-sm bg-[#4F46E5] text-white rounded-lg">{t('fm_download_to_view')}</a>
                </div>
              )}
              {/* Prev/Next arrows — only for images and only when more than 1 image */}
              {imageFiles.length > 1 && previewIndex >= 0 && (previewFile.mime_type || '').startsWith('image/') && (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = (previewIndex - 1 + imageFiles.length) % imageFiles.length;
                      setPreviewFile(imageFiles[next]);
                    }}
                    className="absolute left-2 top-1/2 -translate-y-1/2 p-2 bg-black/50 hover:bg-black/70 text-white rounded-full"
                    title={t('fm_back_to')}
                    data-testid="preview-prev-btn"
                  >
                    <CaretLeft size={20} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = (previewIndex + 1) % imageFiles.length;
                      setPreviewFile(imageFiles[next]);
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-black/50 hover:bg-black/70 text-white rounded-full"
                    title={t('fm_image_x_of_y')}
                    data-testid="preview-next-btn"
                  >
                    <CaretRight size={20} />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ════════ Move dialog ════════ */}
      {movingFile && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3 sm:p-4" onClick={() => setMovingFile(null)} data-testid="move-dialog">
          <div className="bg-white rounded-2xl max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-[#18181B] mb-2">{t('fm_move_file')}</h3>
            <p className="text-sm text-[#71717A] mb-4 truncate">{movingFile.original_name}</p>
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {folders.filter((f) => f.id !== movingFile.folder_id).map((f) => {
                const display = f.is_system ? folderDisplayName(f, lang) : f.name;
                const parent = f.parent_id ? folders.find((p) => p.id === f.parent_id) : null;
                const parentDisplay = parent ? (parent.is_system ? folderDisplayName(parent, lang) : parent.name) : null;
                return (
                  <button
                    key={f.id}
                    onClick={() => handleMoveFile(f.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[#F4F4F5] rounded-lg text-left"
                    data-testid={`move-target-${f.slug || f.id}`}
                  >
                    <Folder size={14} className="text-[#4F46E5]" />
                    <span className="text-sm flex-1 truncate">
                      {parentDisplay ? `${parentDisplay} / ` : ''}{display}
                    </span>
                    <CaretRight size={12} className="text-[#A1A1AA]" />
                  </button>
                );
              })}
            </div>
            <button onClick={() => setMovingFile(null)} className="mt-3 w-full px-3 py-2 text-sm text-[#71717A] hover:bg-[#F4F4F5] rounded-lg" data-testid="move-cancel-btn">
              {t('fm_cancel')}
            </button>
          </div>
        </div>
      )}

      {/* ════════ Edit file (rename + comment) dialog ════════ */}
      {editingFile && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3 sm:p-4" onClick={() => setEditingFile(null)} data-testid="edit-file-dialog">
          <div className="bg-white rounded-2xl max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-[#18181B] mb-3">{t('fm_edit_file')}</h3>
            <label className="block text-xs font-medium text-[#71717A] mb-1">{t('fm_file_name')}</label>
            <input
              type="text"
              autoFocus
              value={editFileName}
              onChange={(e) => setEditFileName(e.target.value)}
              maxLength={200}
              className="w-full px-3 py-2 mb-3 text-sm border border-[#E4E4E7] rounded-lg focus:outline-none focus:border-[#4F46E5]"
              data-testid="edit-file-name-input"
            />
            <label className="block text-xs font-medium text-[#71717A] mb-1">{t('fm_file_comment')}</label>
            <textarea
              rows={3}
              value={editFileComment}
              onChange={(e) => setEditFileComment(e.target.value)}
              maxLength={1000}
              placeholder={t('fm_file_comment_placeholder')}
              className="w-full px-3 py-2 mb-4 text-sm border border-[#E4E4E7] rounded-lg focus:outline-none focus:border-[#4F46E5] resize-none"
              data-testid="edit-file-comment-input"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditingFile(null)} className="px-3 py-1.5 text-sm text-[#71717A] hover:bg-[#F4F4F5] rounded-lg" data-testid="edit-file-cancel">
                {t('fm_cancel')}
              </button>
              <button onClick={handleSaveEditFile} className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-[#4F46E5] text-white rounded-lg hover:bg-[#4338CA]" data-testid="edit-file-save">
                <FloppyDisk size={12} /> {t('fm_save')}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default FileManagerTab;
