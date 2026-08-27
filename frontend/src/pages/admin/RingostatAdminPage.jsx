import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import RingostatStatsPanel from '../../components/ringostat/RingostatStatsPanel';
import RingostatUiPrefsCard from '../../components/ringostat/RingostatUiPrefsCard';
import { Phone as PhonePhosphor } from '@phosphor-icons/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { AlertTriangle, Phone, CheckCircle2, XCircle, Copy, PlayCircle, Eye, EyeOff, ChevronDown, ChevronRight, HelpCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import HelpTooltip from '@/components/ui/HelpTooltip';

import { useLang } from '../../i18n';
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

/**
 * Auth-aware fetch wrapper.
 *
 * Every admin Ringostat endpoint is guarded by Depends(require_admin) on the
 * backend, so requests without ``Authorization: Bearer <jwt>`` come back as
 * 401 and the page used to render empty. This helper attaches the token from
 * localStorage automatically and forwards 401 to the global session handler.
 */
const apiFetch = (path, init = {}) => {
  const token = (typeof window !== 'undefined' && localStorage.getItem('token')) || '';
  const headers = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
};

const RingostatAdminPage = () => {
  const { t } = useLang();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [staff, setStaff] = useState([]);
  const [calls, setCalls] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [engineerOpen, setEngineerOpen] = useState(false);

  // Filters for calls history
  const [filters, setFilters] = useState({
    period: 'today',
    manager: null,
    status: null,
    direction: null
  });

  // Load data
  useEffect(() => {
    loadHealth();
    loadSettings();
    loadMappings();
    loadCalls();
    loadEvents();
  }, []);

  const loadHealth = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/health`);
      const data = await res.json();
      setHealth(data);
    } catch (error) {
      console.error('Failed to load health:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/settings`);
      const data = await res.json();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMappings = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/mappings`);
      const data = await res.json();
      setMappings(data.mappings || []);
      setStaff(data.staff || []);
    } catch (error) {
      console.error('Failed to load mappings:', error);
    }
  };

  const loadCalls = async () => {
    try {
      // Filter only contains non-null values; URLSearchParams would otherwise
      // serialize `null` as the literal string "null" and the backend would
      // filter by status="null" → empty result set.
      const cleaned = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== null && v !== undefined && v !== ''),
      );
      const params = new URLSearchParams(cleaned).toString();
      const res = await apiFetch(`/api/admin/ringostat/calls?${params}`);
      const data = await res.json();
      setCalls(data.calls || []);
    } catch (error) {
      console.error('Failed to load calls:', error);
    }
  };

  const loadEvents = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/events`);
      const data = await res.json();
      setEvents(data.events || []);
    } catch (error) {
      console.error('Failed to load events:', error);
    }
  };

  const handleSaveSettings = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      
      if (res.ok) {
        toast({ title: t('adm_settings_saved') });
        loadHealth();
      }
    } catch (error) {
      toast({ title: t('adm_save_error'), variant: 'destructive' });
    }
  };

  const handleTestConnection = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/test-connection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: settings.api_key,
          project_id: settings.project_id
        })
      });
      
      const data = await res.json();
      
      if (data.success) {
        toast({ title: t('adm_connection_successful') });
      } else {
        toast({ title: data.error, variant: 'destructive' });
      }
    } catch (error) {
      toast({ title: t('adm_testing_error'), variant: 'destructive' });
    }
  };

  const handleTestWebhook = async () => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/test-webhook`, {
        method: 'POST'
      });
      
      if (res.ok) {
        toast({ title: t('adm_test_event_sent') });
        setTimeout(() => {
          loadEvents();
          loadHealth();
        }, 1000);
      }
    } catch (error) {
      toast({ title: t('errorGeneric2'), variant: 'destructive' });
    }
  };

  const handleAddMapping = async (extension, managerId) => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/mappings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extension, manager_id: managerId })
      });
      
      if (res.ok) {
        toast({ title: t('adm_mapping_created') });
        loadMappings();
        loadHealth();
      }
    } catch (error) {
      toast({ title: t('errorGeneric2'), variant: 'destructive' });
    }
  };

  const handleDeleteMapping = async (extension) => {
    try {
      const res = await apiFetch(`/api/admin/ringostat/mappings/${extension}`, {
        method: 'DELETE'
      });
      
      if (res.ok) {
        toast({ title: t('adm_mapping_deleted') });
        loadMappings();
        loadHealth();
      }
    } catch (error) {
      toast({ title: t('errorGeneric2'), variant: 'destructive' });
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast({ title: t('adm_copied') });
  };

  if (loading) {
    return <div className="p-8">{t('adm_loading_4')}</div>;
  }

  const getAttentionAlerts = () => {
    const alerts = [];
    
    if (health?.unassigned?.extensions > 0) {
      alerts.push({
        type: 'warning',
        message: `${health.unassigned.extensions}${t('r9_ext_not_assigned_to_mgr')}`
      });
    }
    
    if (health?.connection?.status === 'disconnected') {
      alerts.push({
        type: 'error',
        message: t('adm_ringostat_is_not_connected')
      });
    }
    
    if (health?.unassigned?.calls_today > 0) {
      alerts.push({
        type: 'warning',
        message: `${health.unassigned.calls_today}${t('r9_calls_today_no_manager')}`
      });
    }
    
    return alerts;
  };

  const webhookUrl = `${window.location.origin}/api/integrations/ringostat/webhook`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3 min-w-0">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <PhonePhosphor size={20} weight="bold" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <h1 className="text-2xl font-bold text-[#18181B] leading-tight" data-testid="telephony-title">
              {t('telephonyTitle')}
            </h1>
            <HelpTooltip text={t('telephonyTooltip')} side="bottom" align="start">
              <button
                type="button"
                aria-label="Help"
                className="inline-flex w-5 h-5 items-center justify-center rounded-full text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 transition-colors"
                data-testid="telephony-title-tip"
              >
                <HelpCircle className="w-3.5 h-3.5" />
              </button>
            </HelpTooltip>
          </div>
          <p className="text-[12px] text-[#71717A] mt-0.5">{t('telephonySubtitle')}</p>
        </div>
      </div>

      {/* Health Cards — 2x2 on mobile, 4-col on lg+ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-zinc-500">{t('adm_connection')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div>
              {health?.connection?.status === 'connected' ? (
                <div className="flex items-center text-green-600 text-sm sm:text-base font-medium">
                  <CheckCircle2 className="h-4 w-4 mr-1.5 shrink-0" />
                  <span className="truncate">{t('connected')}</span>
                </div>
              ) : (
                <div className="flex items-center text-red-600 text-sm sm:text-base font-medium">
                  <XCircle className="h-4 w-4 mr-1.5 shrink-0" />
                  <span className="truncate">{t('disconnected')}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-zinc-500">{t('lastWebhook')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm sm:text-base font-medium text-zinc-900">
              {health?.webhook?.last_event ? (
                <span>{new Date(health.webhook.last_event).toLocaleTimeString()}</span>
              ) : (
                <span className="text-zinc-400">{t('adm_no_data_3')}</span>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-zinc-500">{t('adm_calls_today_3')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl sm:text-3xl font-bold text-zinc-900 leading-none">{health?.calls_today || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-zinc-500">{t('adm_requires_attention')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl sm:text-3xl font-bold text-amber-600 leading-none">
              {getAttentionAlerts().length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Attention Alerts */}
      {getAttentionAlerts().length > 0 && (
        <div className="space-y-2">
          {getAttentionAlerts().map((alert, i) => (
            <Alert key={i} variant={alert.type === 'error' ? 'destructive' : 'default'}>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{alert.message}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      {/* Tabs — scrollable on narrow */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="overflow-x-auto -mx-1 px-1 pb-1">
          <TabsList className="inline-flex w-auto min-w-full sm:min-w-0">
            <TabsTrigger value="overview" className="whitespace-nowrap">{t('adm_overview')}</TabsTrigger>
            <TabsTrigger value="stats" className="whitespace-nowrap">{t('rs_tab_stats')}</TabsTrigger>
            <TabsTrigger value="settings" className="whitespace-nowrap">{t('adm_settings')}</TabsTrigger>
            <TabsTrigger value="calls" className="whitespace-nowrap">{t('adm_call_history')}</TabsTrigger>
            <TabsTrigger value="debug" className="whitespace-nowrap">{t('adm_debugging')}</TabsTrigger>
          </TabsList>
        </div>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('operationalStatus')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('webhookLabel')}</div>
                  <div className="mt-1 text-sm">{health?.webhook?.events_today > 0 ? `🟢 ${t('activeAdj')}` : `⚪ ${t('inactiveAdj')}`}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('apiKey')}</div>
                  <div className="mt-1 text-sm">{health?.connection?.api_key_set ? `✅ ${t('configured')}` : `⚠️ ${t('notConfigured')}`}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('projectId')}</div>
                  <div className="mt-1 text-sm">{health?.connection?.project_id_set ? `✅ ${t('configured')}` : `⚠️ ${t('notConfigured')}`}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('managerMappings')}</div>
                  <div className="mt-1 text-sm">{(health?.mappings?.total ?? 0) - (health?.mappings?.unmapped ?? 0)} {t('adm3_b98ccbc2df')} {health?.mappings?.total ?? 0}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('quickActions')}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={handleTestConnection}>{t('testConnectionAction')}</Button>
              <Button onClick={handleTestWebhook} variant="outline">{t('sendTestEvent')}</Button>
              <Button onClick={() => setActiveTab('settings')} variant="outline">{t('openSettings')}</Button>
              <Button onClick={() => setActiveTab('calls')} variant="outline">{t('callHistory')}</Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Stats Tab — operational KPI dashboard */}
        <TabsContent value="stats" className="space-y-4">
          <RingostatStatsPanel />
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          {/* Connection & Auth — Engineer-only, collapsible */}
          <Card>
            <CardHeader className="pb-3">
              <button
                type="button"
                onClick={() => setEngineerOpen((v) => !v)}
                className="flex items-center gap-2 text-left w-full"
                data-testid="btn-engineer-toggle"
              >
                {engineerOpen ? (
                  <ChevronDown className="h-4 w-4 text-zinc-500 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-zinc-500 shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <CardTitle className="text-[15px]">{t('advancedEngineering')}</CardTitle>
                  <CardDescription className="text-[12px] mt-1">
                    {t('advancedEngineeringHint')}
                  </CardDescription>
                </div>
              </button>
            </CardHeader>
            {engineerOpen ? (
              <CardContent className="space-y-4" data-testid="engineer-panel">
                <div className="space-y-2">
                  <Label>{t('apiKey')}</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showApiKey ? 'text' : 'password'}
                      value={settings?.api_key || ''}
                      onChange={(e) => setSettings({ ...settings, api_key: e.target.value })}
                      placeholder={t('adm_enter_api_key')}
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>{t('projectId')}</Label>
                  <Input
                    value={settings?.project_id || ''}
                    onChange={(e) => setSettings({ ...settings, project_id: e.target.value })}
                    placeholder="12345"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Webhook Secret (token query-string for Ringostat auth)</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showApiKey ? 'text' : 'password'}
                      value={settings?.webhook_secret || ''}
                      onChange={(e) => setSettings({ ...settings, webhook_secret: e.target.value })}
                      placeholder="auto-generated"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => {
                        const fresh = Array.from(crypto.getRandomValues(new Uint8Array(32)))
                          .map(b => ('0' + b.toString(16)).slice(-2)).join('');
                        setSettings({ ...settings, webhook_secret: fresh });
                      }}
                      title="Rotate"
                    >
                      🔄
                    </Button>
                  </div>
                  {settings?.webhook_secret && (
                    <div className="text-xs text-muted-foreground break-all">
                      Webhook URL: <code>{window.location.origin}/api/integrations/ringostat/webhook?token={settings.webhook_secret}</code>
                    </div>
                  )}
                </div>
                {settings?.defaults_applied && Object.values(settings.defaults_applied).some(Boolean) && (
                  <div className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-300 p-2 rounded">
                    ℹ️ Some fields are on baked-in defaults:&nbsp;
                    {Object.entries(settings.defaults_applied).filter(([_,v]) => v).map(([k]) => k).join(', ')}
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleTestConnection}>{t('testConnectionAction')}</Button>
                  <Button onClick={handleSaveSettings}>{t('saveAction')}</Button>
                  <Button
                    variant="outline"
                    onClick={async () => {
                      if (!window.confirm('Reset Ringostat configuration to baked-in defaults?')) return;
                      try {
                        const r = await apiFetch('/api/admin/ringostat/settings/reset', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({}),
                        });
                        if (r.ok) {
                          toast({ title: 'Settings reset to defaults' });
                          await loadSettings();
                        } else {
                          toast({ title: 'Reset failed', variant: 'destructive' });
                        }
                      } catch (e) {
                        toast({ title: 'Reset error: ' + e.message, variant: 'destructive' });
                      }
                    }}
                  >
                    Reset to defaults
                  </Button>
                </div>
              </CardContent>
            ) : null}
          </Card>

          {/* Webhook Setup */}
          <Card>
            <CardHeader>
              <CardTitle>{t('webhookConfiguration')}</CardTitle>
              <CardDescription>{t('adm_configure_this_url_in_ringostat')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>{t('webhookUrl')}</Label>
                <div className="flex gap-2">
                  <Input value={webhookUrl} readOnly />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => copyToClipboard(webhookUrl)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="grid gap-4 text-sm [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
                <div>
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('lastWebhook')}</div>
                  <div className="mt-1">{health?.webhook?.last_event ? new Date(health.webhook.last_event).toLocaleString() : t('adm3_dee9a2d8d9')}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">{t('eventsToday')}</div>
                  <div className="mt-1">{health?.webhook?.events_today || 0}</div>
                </div>
              </div>
              <Button onClick={handleTestWebhook} variant="outline">{t('sendTestWebhook')}</Button>
            </CardContent>
          </Card>

          {/* Manager Mapping */}
          <Card>
            <CardHeader>
              <CardTitle>{t('adm_extension_manager_mapping')}</CardTitle>
              <CardDescription>{t('adm3_crm_core_0f564fb39d')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto -mx-6 px-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="whitespace-nowrap">{t('extensionLabel')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('adm_crm_manager')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('statusGeneric')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('actionsLabel')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mappings.map((mapping) => (
                      <TableRow key={mapping.extension}>
                        <TableCell className="whitespace-nowrap font-mono">{mapping.extension}</TableCell>
                        <TableCell>
                          {mapping.manager_name ? (
                            <div className="min-w-0">
                              <div className="font-medium truncate">{mapping.manager_name}</div>
                              <div className="text-sm text-muted-foreground truncate">{mapping.manager_email}</div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">{t('notAssigned')}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={mapping.status === 'assigned' ? 'default' : 'destructive'}>
                            {mapping.status === 'assigned' ? '✅' : '⚠️'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDeleteMapping(mapping.extension)}
                          >
                            {t('deleteAction')}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="mt-4 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
                <Input placeholder={t('adm_extension_101')} id="newExt" />
                <Select onValueChange={(value) => {
                  const ext = document.getElementById('newExt').value;
                  if (ext) handleAddMapping(ext, value);
                }}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('selectManager')} />
                  </SelectTrigger>
                  <SelectContent>
                    {staff.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Automation Rules */}
          <Card>
            <CardHeader>
              <CardTitle>{t('automationRules')}</CardTitle>
              <CardDescription>{t('adm_critical_automation_rules')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>{t('autoCreateLeadOnUnknown')}</Label>
                <Switch
                  checked={settings?.automation_rules?.auto_create_lead}
                  onCheckedChange={(checked) =>
                    setSettings({
                      ...settings,
                      automation_rules: { ...settings.automation_rules, auto_create_lead: checked }
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between">
                <Label>{t('createCallbackOnMissed')}</Label>
                <Switch
                  checked={settings?.automation_rules?.missed_call_task}
                  onCheckedChange={(checked) =>
                    setSettings({
                      ...settings,
                      automation_rules: { ...settings.automation_rules, missed_call_task: checked }
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Missed call task deadline (minutes)</Label>
                <Input
                  type="number"
                  value={settings?.automation_rules?.missed_call_task_minutes || 5}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      automation_rules: { ...settings.automation_rules, missed_call_task_minutes: parseInt(e.target.value) }
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between">
                <Label>{t('requireOutcomeAfterAnswered')}</Label>
                <Switch
                  checked={settings?.automation_rules?.require_outcome}
                  onCheckedChange={(checked) =>
                    setSettings({
                      ...settings,
                      automation_rules: { ...settings.automation_rules, require_outcome: checked }
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Show outcome form if duration &gt; (seconds)</Label>
                <Input
                  type="number"
                  value={settings?.automation_rules?.require_outcome_duration || 10}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      automation_rules: { ...settings.automation_rules, require_outcome_duration: parseInt(e.target.value) }
                    })
                  }
                />
              </div>
              <Button onClick={handleSaveSettings}>{t('saveRules')}</Button>
            </CardContent>
          </Card>

          {/* Per-user UI preferences (Phase IV-6: role-aware UX) */}
          <RingostatUiPrefsCard />
        </TabsContent>

        {/* Calls History Tab */}
        <TabsContent value="calls" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('mobileFiltersTitle')}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              <Select value={filters.period} onValueChange={(v) => setFilters({ ...filters, period: v })}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">{t('adm_today')}</SelectItem>
                  <SelectItem value="week">{t('adm_week')}</SelectItem>
                  <SelectItem value="month">{t('adm_month')}</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={loadCalls} className="w-full sm:w-auto">{t('adm_apply')}</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('callsHistory')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto -mx-6 px-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="whitespace-nowrap">{t('adm_time')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('adm_number')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('adm_direction')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('adm_duration')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('statusGeneric')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('leadLabel')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('actionsLabel')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {calls.map((call) => (
                      <TableRow key={call.id}>
                        <TableCell className="whitespace-nowrap">{new Date(call.started_at).toLocaleString()}</TableCell>
                        <TableCell className="whitespace-nowrap font-mono">{call.from}</TableCell>
                        <TableCell>
                          <Badge variant={call.direction === 'inbound' ? 'default' : 'secondary'}>
                            {call.direction}
                          </Badge>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{call.duration}s</TableCell>
                        <TableCell>
                          <Badge variant={call.status === 'answered' ? 'default' : 'destructive'}>
                            {call.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {call.lead ? call.lead.name : <span className="text-muted-foreground">—</span>}
                        </TableCell>
                        <TableCell>
                          <Button size="sm" variant="outline" onClick={() => setSelectedCall(call)}>
                            {t('adm_view')}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Debug Tab */}
        <TabsContent value="debug" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('debugStatus')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="break-words">Last webhook payload: {health?.webhook?.last_event ? new Date(health.webhook.last_event).toLocaleString() : t('adm3_dee9a2d8d9')}</div>
              <div>Events today: {health?.webhook?.events_today || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('recentEvents')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto -mx-6 px-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="whitespace-nowrap">{t('timestampLabel')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('eventType')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('callIdLabel')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('direction')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('fromLabel')}</TableHead>
                      <TableHead className="whitespace-nowrap">{t('durationGeneric')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {events.slice(0, 10).map((evt) => (
                      <TableRow key={evt.id}>
                        <TableCell className="whitespace-nowrap">{new Date(evt.timestamp).toLocaleString()}</TableCell>
                        <TableCell><Badge>{evt.event_type}</Badge></TableCell>
                        <TableCell className="font-mono text-sm whitespace-nowrap">{evt.call_id}</TableCell>
                        <TableCell>{evt.direction}</TableCell>
                        <TableCell className="whitespace-nowrap">{evt.from}</TableCell>
                        <TableCell className="whitespace-nowrap">{evt.duration}s</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('manualTools')}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={handleTestConnection}>{t('testConnectionAction')}</Button>
              <Button onClick={handleTestWebhook} variant="outline">{t('testWebhook')}</Button>
              <Button onClick={() => { loadHealth(); loadEvents(); }} variant="outline">{t('reloadData')}</Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Call Details Drawer */}
      <Sheet open={!!selectedCall} onOpenChange={() => setSelectedCall(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{t('callDetailsTitle')}</SheetTitle>
            <SheetDescription>{t('adm_call_details')}</SheetDescription>
          </SheetHeader>
          {selectedCall && (
            <div className="mt-6 space-y-4">
              <div>
                <div className="text-sm text-muted-foreground">{t('callIdLabel')}</div>
                <div className="font-mono text-sm">{selectedCall.call_id}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">{t('time')}</div>
                <div>{new Date(selectedCall.started_at).toLocaleString()}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">{t('direction')}</div>
                <Badge>{selectedCall.direction}</Badge>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">{t('durationGeneric')}</div>
                <div>{selectedCall.duration} seconds</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">{t('adm_phone')}</div>
                <div>{selectedCall.from}</div>
              </div>
              {selectedCall.lead && (selectedCall.lead.name || selectedCall.lead.phone) && (
                <div>
                  <div className="text-sm text-muted-foreground">{t('leadLabel')}</div>
                  {selectedCall.lead.name ? (
                    <div className="font-medium">{selectedCall.lead.name}</div>
                  ) : null}
                  {selectedCall.lead.phone ? (
                    <div className="text-sm text-muted-foreground">{selectedCall.lead.phone}</div>
                  ) : null}
                </div>
              )}
              {selectedCall.recording_url ? (
                <div className="space-y-2 pt-2 border-t border-[#F4F4F5]">
                  <div className="text-sm font-semibold text-[#18181B] flex items-center gap-2">
                    <PlayCircle className="h-4 w-4" />
                    {t('playRecording') || 'Call recording'}
                  </div>
                  {/* Inline HTML5 player. We point at our backend recording
                      proxy so the browser doesn't fight Ringostat's signed/
                      expired URLs — the proxy re-issues fresh ones via API
                      and 302-redirects. Falls back to direct URL if proxy
                      route isn't reachable. */}
                  <audio
                    controls
                    preload="none"
                    src={`${BACKEND_URL}/api/admin/ringostat/calls/${encodeURIComponent(selectedCall.call_id)}/recording`}
                    className="w-full h-10 rounded-lg"
                    data-testid="call-recording-audio"
                    onError={(e) => {
                      // Fallback to raw URL if proxy fails
                      const raw = selectedCall.recording_url;
                      if (raw && e.currentTarget.src !== raw) {
                        e.currentTarget.src = raw;
                      }
                    }}
                  >
                    Your browser does not support audio playback.
                  </audio>
                  <div className="flex items-center gap-2">
                    <a
                      href={selectedCall.recording_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center justify-center gap-1.5 h-8 px-3 rounded-lg bg-white border border-[#E4E4E7] text-[#18181B] text-[11.5px] font-semibold hover:border-[#18181B] transition-colors"
                      data-testid="call-recording-open"
                    >
                      Open in new tab
                    </a>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard?.writeText(selectedCall.recording_url)}
                      className="inline-flex items-center justify-center gap-1.5 h-8 px-3 rounded-lg bg-white border border-[#E4E4E7] text-[#52525B] hover:text-[#18181B] hover:border-[#18181B] text-[11.5px] font-semibold transition-colors"
                      data-testid="call-recording-copy"
                    >
                      <Copy className="h-3 w-3" />
                      Copy URL
                    </button>
                  </div>
                  <p className="text-[10.5px] text-[#71717A] leading-snug">
                    Played through <span className="font-mono">/api/admin/ringostat/calls/&lt;id&gt;/recording</span> proxy —
                    auto-refreshes expired Ringostat signed URLs via their API.
                  </p>
                </div>
              ) : (
                <div className="px-3 py-2.5 rounded-lg bg-[#FAFAFA] border border-[#E4E4E7] text-[11.5px] text-[#71717A]">
                  No recording for this call yet. Ringostat normally posts the recording_url
                  in the <span className="font-mono">CALL_END</span> webhook ~10-30 s after the call ends;
                  the CRON also retries every 5 min.
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default RingostatAdminPage;