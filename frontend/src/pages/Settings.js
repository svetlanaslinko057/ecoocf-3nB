import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang, getLocale } from '../i18n';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Gear, Bell, Shield, Globe, Key, User, Plus, Trash, Check, X,
  ArrowsClockwise, Lightning, ShieldCheck, Warning, Eye, EyeSlash, Database, Plugs
} from '@phosphor-icons/react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import WhiteSelect from '../components/ui/WhiteSelect';
import BillingRequisites from '../components/admin/BillingRequisites';

const Settings = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('general');
  const [profileData, setProfileData] = useState({ firstName: '', lastName: '', email: '', phone: '' });
  const [passwordData, setPasswordData] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [proxies, setProxies] = useState([]);
  const [proxyStatus, setProxyStatus] = useState(null);
  const [proxyLoading, setProxyLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [showPasswords, setShowPasswords] = useState({});
  const [newProxy, setNewProxy] = useState({ host: '', port: '', protocol: 'http', username: '', password: '', priority: 1 });
  const isMasterAdmin = ['master_admin'].includes(user?.role);
  const isAdmin = ['master_admin', 'owner', 'admin', 'team_lead'].includes(user?.role);

  useEffect(() => { fetchSettings(); if (user) { setProfileData({ firstName: user.firstName || '', lastName: user.lastName || '', email: user.email || '', phone: user.phone || '' }); } }, [user]);
  useEffect(() => { if (activeTab === 'proxy' && isMasterAdmin) fetchProxyStatus(); }, [activeTab, isMasterAdmin]);

  const fetchSettings = async () => { try { const res = await axios.get(`${API_URL}/api/settings`); setSettings(res.data || []); } catch (err) { toast.error(t('error')); } finally { setLoading(false); } };

  const handleProfileUpdate = async (e) => { e.preventDefault(); try { await axios.put(`${API_URL}/api/users/me`, profileData); toast.success(t('profileUpdated')); } catch (err) { toast.error(t('error')); } };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (passwordData.newPassword !== passwordData.confirmPassword) { toast.error(t('passwordsMismatch')); return; }
    try { await axios.post(`${API_URL}/api/auth/change-password`, { currentPassword: passwordData.currentPassword, newPassword: passwordData.newPassword }); toast.success(t('passwordChanged')); setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' }); }
    catch (err) { toast.error(err.response?.data?.message || t('error')); }
  };

  const fetchProxyStatus = async () => { setProxyLoading(true); try { const res = await axios.get(`${API_URL}/api/admin/proxy/status`); setProxyStatus(res.data); setProxies(res.data.proxies || []); } catch (err) { console.error('Proxy fetch error:', err); } finally { setProxyLoading(false); } };

  const handleAddProxy = async (e) => {
    e.preventDefault();
    if (!newProxy.host || !newProxy.port) { toast.error(t('proxyHostPortRequired')); return; }
    try { await axios.post(`${API_URL}/api/admin/proxy/add`, { host: newProxy.host, port: parseInt(newProxy.port), protocol: newProxy.protocol, username: newProxy.username || undefined, password: newProxy.password || undefined, priority: parseInt(newProxy.priority) || 1 }); toast.success(t('proxyAdded')); setNewProxy({ host: '', port: '', protocol: 'http', username: '', password: '', priority: 1 }); setShowAddForm(false); fetchProxyStatus(); }
    catch (err) { toast.error(err.response?.data?.message || t('error')); }
  };

  const handleRemoveProxy = async (id) => { if (!window.confirm(t('deleteProxyConfirm'))) return; try { await axios.delete(`${API_URL}/api/admin/proxy/remove/${id}`); toast.success(t('proxyRemoved')); fetchProxyStatus(); } catch (err) { toast.error(t('error')); } };

  const handleToggleProxy = async (id, enabled) => {
    try { if (enabled) { await axios.post(`${API_URL}/api/admin/proxy/disable/${id}`); } else { await axios.post(`${API_URL}/api/admin/proxy/enable/${id}`); } toast.success(enabled ? t('proxyDisabled') : t('proxyEnabled')); fetchProxyStatus(); }
    catch (err) { toast.error(t('error')); }
  };

  const handleTestProxy = async (id) => {
    setTestingId(id);
    try { const res = await axios.post(`${API_URL}/api/admin/proxy/test/${id}`); if (res.data.success) { toast.success(`${t('proxyWorking')} IP: ${res.data.ip || 'ok'}`); } else { toast.error(`${t('error')}: ${res.data.error || '?'}`); } fetchProxyStatus(); }
    catch (err) { toast.error(t('error')); } finally { setTestingId(null); }
  };

  const handleSetPriority = async (id, priority) => { try { await axios.post(`${API_URL}/api/admin/proxy/priority/${id}`, { priority }); toast.success(t('priorityUpdated')); fetchProxyStatus(); } catch (err) { toast.error(t('error')); } };
  const handleReloadProxies = async () => { try { await axios.post(`${API_URL}/api/admin/proxy/reload`); toast.success(t('proxiesReloaded')); fetchProxyStatus(); } catch (err) { toast.error(t('error')); } };
  const togglePasswordVisibility = (id) => { setShowPasswords(prev => ({ ...prev, [id]: !prev[id] })); };

  const parseServer = (server) => { try { const url = new URL(server); return { protocol: url.protocol.replace(':', ''), host: url.hostname, port: url.port }; } catch { return { protocol: 'http', host: server, port: '' }; } };

  const settingLabels = {
    lead_statuses: t('settingLeadStatuses'), deal_statuses: t('settingDealStatuses'),
    deposit_statuses: t('settingDepositStatuses'), lead_sources: t('settingLeadSources'),
    sla_first_response_minutes: t('settingSlaFirstResponse'), sla_callback_minutes: t('settingSlaCallback')
  };

  const settingIcons = {
    lead_statuses: <Database size={22} weight="duotone" />, deal_statuses: <Database size={22} weight="duotone" />,
    deposit_statuses: <Database size={22} weight="duotone" />, lead_sources: <Globe size={22} weight="duotone" />
  };

  const roleLabels = {
    master_admin: t('roleMasterAdmin'), owner: t('roleMasterAdmin'), team_lead: 'Team Lead',
    admin: t('roleAdmin'), moderator: t('roleModerator'),
    manager: t('roleManager'), finance: t('roleFinance')
  };

  return (
    <motion.div data-testid="settings-page" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="flex items-start gap-3 mb-8">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <Gear size={20} weight="bold" />
        </div>
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-[#18181B] leading-tight" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('settingsTitle')}</h1>
          <p className="text-[12px] text-[#71717A] mt-0.5">{t('settingsSubtitle')}</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-[#F4F4F5] p-1 rounded-xl inline-flex">
          <TabsTrigger value="general" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><Gear size={16} />{t('settingsGeneral')}</TabsTrigger>
          <TabsTrigger value="profile" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><User size={16} />{t('settingsProfile')}</TabsTrigger>
          <TabsTrigger value="security" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><Shield size={16} />{t('settingsSecurity')}</TabsTrigger>
          <TabsTrigger value="notifications" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><Bell size={16} />{t('settingsNotifications')}</TabsTrigger>
          {isMasterAdmin && <TabsTrigger value="proxy" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><Globe size={16} />{t('settingsProxy')}</TabsTrigger>}
          {isAdmin && <TabsTrigger value="requisites" className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2"><Key size={16} />Реквізити для оплати</TabsTrigger>}
        </TabsList>

        {/* General */}
        <TabsContent value="general">
          {loading ? <div className="text-center py-12 text-[#71717A]">{t('loading')}</div> : (
            <div className="space-y-5">
              {settings.map(setting => (
                <div key={setting.id || setting.key} className="section-card" data-testid={`setting-${setting.key}`}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="text-[#4F46E5]">{settingIcons[setting.key] || <Gear size={22} weight="duotone" />}</div>
                    <div><h3 className="font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{settingLabels[setting.key] || setting.key}</h3><p className="text-xs text-[#71717A]">{setting.description}</p></div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Array.isArray(setting.value) ? setting.value.map((val, i) => <span key={i} className="px-3 py-1.5 bg-[#F4F4F5] text-sm rounded-lg text-[#3F3F46] font-medium">{val}</span>) : <span className="text-sm text-[#3F3F46] font-medium">{JSON.stringify(setting.value)}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Profile */}
        <TabsContent value="profile">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="section-card">
              <div className="flex flex-col items-center text-center">
                <div className="w-20 h-20 bg-[#18181B] rounded-2xl flex items-center justify-center text-2xl font-bold text-white mb-4">{user?.firstName?.[0]}{user?.lastName?.[0]}</div>
                <h3 className="font-semibold text-[#18181B] text-lg" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{user?.firstName} {user?.lastName}</h3>
                <p className="text-sm text-[#71717A]">{user?.email}</p>
                <span className="badge status-new mt-3">{roleLabels[user?.role] || user?.role}</span>
              </div>
            </div>
            <div className="section-card lg:col-span-2">
              <h3 className="font-semibold text-[#18181B] mb-6" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('editProfile')}</h3>
              <form onSubmit={handleProfileUpdate} className="space-y-5">
                <div className="grid grid-cols-2 gap-4">
                  <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('firstName')}</label><input type="text" value={profileData.firstName} onChange={(e) => setProfileData({...profileData, firstName: e.target.value})} className="input w-full" data-testid="profile-firstname" /></div>
                  <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('lastName')}</label><input type="text" value={profileData.lastName} onChange={(e) => setProfileData({...profileData, lastName: e.target.value})} className="input w-full" data-testid="profile-lastname" /></div>
                </div>
                <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('email')}</label><input type="email" value={profileData.email} onChange={(e) => setProfileData({...profileData, email: e.target.value})} className="input w-full" disabled data-testid="profile-email" /><p className="text-xs text-[#71717A] mt-1">{t('emailCannotChange')}</p></div>
                <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('phone')}</label><input type="tel" value={profileData.phone} onChange={(e) => setProfileData({...profileData, phone: e.target.value})} className="input w-full" data-testid="profile-phone" /></div>
                <button type="submit" className="btn-primary" data-testid="save-profile-btn">{t('saveChanges')}</button>
              </form>
            </div>
          </div>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="section-card">
              <div className="flex items-center gap-3 mb-6"><Key size={22} weight="duotone" className="text-[#DC2626]" /><h3 className="font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('changePassword')}</h3></div>
              <form onSubmit={handlePasswordChange} className="space-y-5">
                <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('currentPassword')}</label><input type="password" value={passwordData.currentPassword} onChange={(e) => setPasswordData({...passwordData, currentPassword: e.target.value})} required className="input w-full" data-testid="current-password" /></div>
                <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('newPassword')}</label><input type="password" value={passwordData.newPassword} onChange={(e) => setPasswordData({...passwordData, newPassword: e.target.value})} required className="input w-full" data-testid="new-password" /></div>
                <div><label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('confirmPassword')}</label><input type="password" value={passwordData.confirmPassword} onChange={(e) => setPasswordData({...passwordData, confirmPassword: e.target.value})} required className="input w-full" data-testid="confirm-password" /></div>
                <button type="submit" className="btn-primary" data-testid="change-password-btn">{t('changePassword')}</button>
              </form>
            </div>
            <div className="section-card">
              <div className="flex items-center gap-3 mb-6"><Shield size={22} weight="duotone" className="text-[#059669]" /><h3 className="font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('securityInfo')}</h3></div>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-[#F4F4F5] rounded-xl"><div><p className="font-medium text-[#18181B]">{t('twoFactor')}</p><p className="text-xs text-[#71717A]">{t('twoFactorDesc')}</p></div><span className="badge status-contacted">{t('comingSoon')}</span></div>
                <div className="flex items-center justify-between p-4 bg-[#F4F4F5] rounded-xl"><div><p className="font-medium text-[#18181B]">{t('lastLogin')}</p><p className="text-xs text-[#71717A]">{user?.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString(getLocale()) : t('unknown')}</p></div></div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Notifications */}
        <TabsContent value="notifications">
          <div className="section-card max-w-2xl">
            <div className="flex items-center gap-3 mb-6"><Bell size={22} weight="duotone" className="text-[#7C3AED]" /><h3 className="font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('notificationSettings')}</h3></div>
            <div className="space-y-4">
              {[
                { key: 'new_lead', label: t('notifNewLead'), desc: t('notifNewLeadDesc') },
                { key: 'task_due', label: t('notifTaskDue'), desc: t('notifTaskDueDesc') },
                { key: 'callback', label: t('notifCallback'), desc: t('notifCallbackDesc') },
                { key: 'deal_update', label: t('notifDealUpdate'), desc: t('notifDealUpdateDesc') },
                { key: 'deposit', label: t('notifDeposit'), desc: t('notifDepositDesc') },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between p-4 bg-[#F4F4F5] rounded-xl"><div><p className="font-medium text-[#18181B]">{item.label}</p><p className="text-xs text-[#71717A]">{item.desc}</p></div><Switch defaultChecked data-testid={`notification-${item.key}`} /></div>
              ))}
            </div>
          </div>
        </TabsContent>

        {/* Proxy */}
        {isMasterAdmin && (
          <TabsContent value="proxy">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3"><Globe size={22} weight="duotone" className="text-[#16A34A]" /><div><h3 className="font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{t('proxyManagement')}</h3><p className="text-xs text-[#71717A]">{t('proxyManagementDesc')}</p></div></div>
              <div className="flex gap-3">
                <button onClick={handleReloadProxies} className="px-4 py-2 text-sm font-medium text-[#18181B] bg-[#F4F4F5] hover:bg-[#E4E4E7] rounded-lg flex items-center gap-2 transition-colors"><ArrowsClockwise size={16} />{t('reload')}</button>
                <button onClick={() => setShowAddForm(true)} className="px-4 py-2 text-sm font-medium text-white bg-[#0A0A0B] hover:bg-[#18181B] rounded-lg flex items-center gap-2 transition-colors"><Plus size={16} />{t('addProxy')}</button>
              </div>
            </div>

            {proxyStatus && (
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="kpi-card"><div className="mb-3"><Globe size={24} weight="duotone" className="text-[#16A34A]" /></div><div className="kpi-value">{proxyStatus.total}</div><div className="kpi-label">{t('total')}</div></div>
                <div className="kpi-card"><div className="mb-3"><Check size={24} weight="duotone" className="text-[#059669]" /></div><div className="kpi-value text-[#059669]">{proxyStatus.active}</div><div className="kpi-label">{t('active')}</div></div>
                <div className="kpi-card"><div className="mb-3"><Warning size={24} weight="duotone" className="text-[#D97706]" /></div><div className="kpi-value text-[#D97706]">{proxyStatus.onCooldown}</div><div className="kpi-label">{t('adm_cooldown')}</div></div>
                <div className="kpi-card"><div className="mb-3"><Plugs size={24} weight="duotone" className="text-[#71717A]" /></div><div className="kpi-value text-[#71717A]">{proxyStatus.disabled}</div><div className="kpi-label">{t('disabled')}</div></div>
              </div>
            )}

            <div className="bg-white rounded-xl border border-[#E4E4E7] overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#FAFAFA] border-b border-[#E4E4E7]">
                  <tr>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">ID</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('server')}</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('auth')}</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('priority')}</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('statistics')}</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('status')}</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-[#71717A] uppercase">{t('actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E4E4E7]">
                  {proxyLoading ? (
                    <tr><td colSpan={7} className="px-6 py-12 text-center"><div className="animate-spin w-6 h-6 border-2 border-[#0A0A0B] border-t-transparent rounded-full mx-auto"></div></td></tr>
                  ) : proxies.length === 0 ? (
                    <tr><td colSpan={7} className="px-6 py-12 text-center text-sm text-[#71717A]">{t('noProxies')}</td></tr>
                  ) : proxies.map((proxy) => {
                    const serverInfo = parseServer(proxy.server);
                    const isOnCooldown = proxy.cooldown_until && proxy.cooldown_until > Date.now();
                    return (
                      <tr key={proxy.id} className="hover:bg-[#FAFAFA] transition-colors">
                        <td className="px-6 py-4"><span className="text-sm font-mono text-[#18181B]">#{proxy.id}</span></td>
                        <td className="px-6 py-4"><div className="flex flex-col"><span className="text-sm font-medium text-[#18181B]">{serverInfo.host}</span><span className="text-xs text-[#71717A]">{serverInfo.protocol.toUpperCase()}:{serverInfo.port}</span></div></td>
                        <td className="px-6 py-4">{proxy.username ? <div className="flex items-center gap-2"><span className="text-sm text-[#18181B]">{proxy.username}</span><button onClick={() => togglePasswordVisibility(proxy.id)} className="text-[#71717A] hover:text-[#18181B]">{showPasswords[proxy.id] ? <EyeSlash size={14} /> : <Eye size={14} />}</button>{showPasswords[proxy.id] && proxy.password && <span className="text-xs text-[#71717A]">/ {proxy.password}</span>}</div> : <span className="text-sm text-[#71717A]">—</span>}</td>
                        <td className="px-6 py-4"><WhiteSelect value={proxy.priority} onChange={e => handleSetPriority(proxy.id, parseInt(e.target.value))}>{[1,2,3,4,5,6,7,8,9,10].map(p => <option key={p} value={p}>{p}</option>)}</WhiteSelect></td>
                        <td className="px-6 py-4"><div className="flex items-center gap-3"><span className="text-xs px-2 py-1 bg-[#ECFDF5] text-[#059669] rounded-full">{proxy.success_count} ok</span><span className="text-xs px-2 py-1 bg-[#FEF2F2] text-[#DC2626] rounded-full">{proxy.error_count} err</span></div></td>
                        <td className="px-6 py-4">{!proxy.enabled ? <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[#F4F4F5] text-[#71717A]"><X size={12} />{t('disabled')}</span> : isOnCooldown ? <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[#FEF3C7] text-[#D97706]"><Warning size={12} />{t('adm_cooldown')}</span> : <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[#ECFDF5] text-[#059669]"><Check size={12} />{t('active')}</span>}</td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => handleTestProxy(proxy.id)} disabled={testingId === proxy.id} className="p-2 text-[#71717A] hover:text-[#18181B] hover:bg-[#F4F4F5] rounded-lg transition-colors disabled:opacity-50" title={t('test')}>{testingId === proxy.id ? <ArrowsClockwise size={16} className="animate-spin" /> : <Lightning size={16} />}</button>
                            <button onClick={() => handleToggleProxy(proxy.id, proxy.enabled)} className="p-2 text-[#71717A] hover:text-[#18181B] hover:bg-[#F4F4F5] rounded-lg transition-colors" title={proxy.enabled ? t('disable') : t('enable')}>{proxy.enabled ? <X size={16} /> : <Check size={16} />}</button>
                            <button onClick={() => handleRemoveProxy(proxy.id)} className="p-2 text-[#71717A] hover:text-[#DC2626] hover:bg-[#FEF2F2] rounded-lg transition-colors" title={t('delete')}><Trash size={16} /></button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-6 bg-[#F0F9FF] rounded-xl p-5 border border-[#BAE6FD]"><div className="flex gap-3"><ShieldCheck size={24} weight="duotone" className="text-[#0EA5E9] flex-shrink-0" /><div><h3 className="text-sm font-semibold text-[#0C4A6E] mb-1">{t('howProxiesWork')}</h3><p className="text-sm text-[#0369A1]">{t('howProxiesWorkDesc')}</p></div></div></div>

            <AnimatePresence>
              {showAddForm && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowAddForm(false)}>
                  <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
                    <h2 className="text-lg font-semibold text-[#18181B] mb-6">{t('addNewProxy')}</h2>
                    <form onSubmit={handleAddProxy} className="space-y-4">
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('protocol')}</label><WhiteSelect value={newProxy.protocol} onChange={e => setNewProxy({ ...newProxy, protocol: e.target.value })} className="w-full"><option value="http">HTTP</option><option value="https">HTTPS</option><option value="socks5">{t('adm_socks5')}</option></WhiteSelect></div>
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('ipAddress')} *</label><input type="text" value={newProxy.host} onChange={e => setNewProxy({ ...newProxy, host: e.target.value })} placeholder="192.168.1.1" className="w-full px-4 py-2.5 bg-[#F4F4F5] border-0 rounded-lg text-sm focus:ring-2 focus:ring-[#0A0A0B] outline-none" required /></div>
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('port')} *</label><input type="number" value={newProxy.port} onChange={e => setNewProxy({ ...newProxy, port: e.target.value })} placeholder="8080" className="w-full px-4 py-2.5 bg-[#F4F4F5] border-0 rounded-lg text-sm focus:ring-2 focus:ring-[#0A0A0B] outline-none" required /></div>
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('login')}</label><input type="text" value={newProxy.username} onChange={e => setNewProxy({ ...newProxy, username: e.target.value })} placeholder="username" className="w-full px-4 py-2.5 bg-[#F4F4F5] border-0 rounded-lg text-sm focus:ring-2 focus:ring-[#0A0A0B] outline-none" /></div>
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('password')}</label><input type="password" value={newProxy.password} onChange={e => setNewProxy({ ...newProxy, password: e.target.value })} placeholder="••••••••" className="w-full px-4 py-2.5 bg-[#F4F4F5] border-0 rounded-lg text-sm focus:ring-2 focus:ring-[#0A0A0B] outline-none" /></div>
                      <div><label className="block text-sm font-medium text-[#18181B] mb-2">{t('priority')} (1-10)</label><input type="number" min="1" max="10" value={newProxy.priority} onChange={e => setNewProxy({ ...newProxy, priority: e.target.value })} className="w-full px-4 py-2.5 bg-[#F4F4F5] border-0 rounded-lg text-sm focus:ring-2 focus:ring-[#0A0A0B] outline-none" /></div>
                      <div className="flex gap-3 pt-4">
                        <button type="button" onClick={() => setShowAddForm(false)} className="flex-1 px-4 py-2.5 text-sm font-medium text-[#18181B] bg-[#F4F4F5] hover:bg-[#E4E4E7] rounded-lg">{t('cancel')}</button>
                        <button type="submit" className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-[#0A0A0B] hover:bg-[#18181B] rounded-lg">{t('add')}</button>
                      </div>
                    </form>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </TabsContent>
        )}

        {isAdmin && (
          <TabsContent value="requisites">
            <BillingRequisites />
          </TabsContent>
        )}
      </Tabs>
    </motion.div>
  );
};

export default Settings;
