import React, { useState, Suspense } from "react";
import { NavLink, Outlet, useNavigate, Navigate, Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Building2, ClipboardList, Workflow, Leaf, LogOut, Menu,
  Banknote, ShieldCheck, Database, ListTodo, Phone, Receipt, FileStack, Bell,
  FolderArchive, Briefcase, Users, Trophy, CalendarClock, PhoneCall, Lock,
  UsersRound, Shuffle, BookText, PanelLeftClose, PanelLeftOpen, ChevronDown,
  Inbox, Settings as SettingsIcon, UserPlus, PanelBottom, Contact, MessageSquare, Zap,
  Crown, BarChart3, ScrollText, Search, FileText, Command, Sparkles, Activity,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/context/AuthContext";
import NotificationBell from "@/components/portal/NotificationBell";
import CrmSearch from "@/components/portal/CrmSearch";
import CommandPalette from "@/components/unified/CommandPalette";
import UnifiedNotifications from "@/components/unified/UnifiedNotifications";
import CallsLiveLayer from "@/components/ringostat/CallsLiveLayer";
import { cn } from "@/lib/utils";
import RouteFallback from "@/components/RouteFallback";

// ── Меню МЕНЕДЖЕРА — згруповано по сенсу, блоково (видно лише ролі manager) ──
// Дрібніші тематичні блоки: персональний кабінет, робота з клієнтами,
// операції, командний CRM, фінанси/документи, довідники, безпека.
const MANAGER_SECTIONS = [
  {
    title: "Мій кабінет",
    accent: true,
    links: [
      { to: "/app/cabinet", label: "Огляд", icon: Briefcase, end: true },
      { to: "/app/cabinet/leads", label: "Мої ліди", icon: Users },
      { to: "/app/cabinet/deals", label: "Мої угоди", icon: Trophy },
    ],
  },
  {
    title: "Моя робота",
    links: [
      { to: "/app/cabinet/tasks", label: "Мої завдання", icon: CalendarClock },
      { to: "/app/cabinet/calls", label: "Мої дзвінки", icon: PhoneCall },
    ],
  },
  {
    title: "Клієнти та продажі",
    links: [
      { to: "/app/companies", label: "Компанії", icon: Building2 },
      { to: "/app/customers", label: "Клієнти", icon: Users },
      { to: "/app/leads", label: "Ліди", icon: UserPlus },
      { to: "/app/requests", label: "Заявки", icon: ClipboardList },
      { to: "/app/inquiries", label: "Звернення", icon: Inbox },
    ],
  },
  {
    title: "Операції",
    links: [
      { to: "/app", label: "Дашборд", icon: LayoutDashboard, end: true },
      { to: "/app/operations", label: "Операції", icon: Workflow },
      { to: "/app/operations360", label: "Операції 360", icon: BarChart3 },
    ],
  },
  {
    title: "Команда · CRM",
    links: [
      { to: "/app/crm", label: "CRM-хаб", icon: LayoutDashboard, end: true },
      { to: "/app/crm/actions", label: "Центр дій", icon: Zap },
      { to: "/app/crm/tasks", label: "Завдання команди", icon: ListTodo },
      { to: "/app/crm/calls", label: "Дзвінки команди", icon: Phone },
      { to: "/app/crm/messages", label: "Повідомлення", icon: MessageSquare },
      { to: "/app/crm/notifications", label: "Сповіщення", icon: Bell },
    ],
  },
  {
    title: "Документи та рахунки",
    links: [
      { to: "/app/contracts", label: "Договори 360", icon: ShieldCheck },
      { to: "/app/contract-flow", label: "Універсальні договори", icon: FileStack },
      { to: "/app/contract-flow/types", label: "Типи договорів", icon: Database },
      { to: "/app/contract-flow/templates", label: "Шаблони договорів", icon: FileStack },
      { to: "/app/finance", label: "Фінанси 360", icon: BarChart3 },
      { to: "/app/crm/invoices", label: "Рахунки", icon: Receipt },
      { to: "/app/crm/documents", label: "Документи", icon: FileStack },
      { to: "/app/crm/files", label: "Файли", icon: FolderArchive },
    ],
  },
  {
    title: "Каталог · Ліцензії · Тарифи",
    links: [
      { to: "/app/directory", label: "Довідник кодів", icon: Database },
      { to: "/app/licenses", label: "Ліцензії", icon: ShieldCheck },
      { to: "/app/pricing", label: "Тарифи", icon: Banknote },
    ],
  },
  {
    title: "Безпека",
    links: [
      { to: "/app/cabinet/security", label: "Безпека (2FA)", icon: Lock },
    ],
  },
];

// ── Загальні розділи (видно всім ролям робочого простору) ────────────
const COMMON_SECTIONS = [
  {
    title: "Операційна діяльність",
    links: [
      { to: "/app", label: "Дашборд", icon: LayoutDashboard, end: true },
      { to: "/app/companies", label: "Компанії", icon: Building2 },
      { to: "/app/customers", label: "Клієнти", icon: Users },
      { to: "/app/leads", label: "Ліди", icon: UserPlus },
      { to: "/app/requests", label: "Заявки", icon: ClipboardList },
      { to: "/app/operations", label: "Операції", icon: Workflow },
      { to: "/app/inquiries", label: "Звернення", icon: Inbox },
    ],
  },
  {
    title: "Каталог · Ліцензії · Тарифи",
    links: [
      { to: "/app/directory", label: "Довідник кодів", icon: Database },
      { to: "/app/licenses", label: "Ліцензії", icon: ShieldCheck },
      { to: "/app/pricing", label: "Тарифи", icon: Banknote },
    ],
  },
  {
    title: "CRM · Команда",
    links: [
      { to: "/app/crm", label: "CRM-хаб", icon: LayoutDashboard, end: true },
      { to: "/app/crm/tasks", label: "Завдання", icon: ListTodo },
      { to: "/app/crm/calls", label: "Дзвінки", icon: Phone },
      { to: "/app/crm/invoices", label: "Рахунки", icon: Receipt },
      { to: "/app/crm/documents", label: "Документи", icon: FileStack },
      { to: "/app/crm/files", label: "Файли", icon: FolderArchive },
      { to: "/app/crm/messages", label: "Повідомлення", icon: MessageSquare },
      { to: "/app/crm/notifications", label: "Сповіщення", icon: Bell },
    ],
  },
];

// ── CRM · Команда ────────────────────────────────────────────────────
// (split below)

// ── Меню АДМІНА — згруповано по сенсу, блоково (видно лише ролі admin) ──────
const ADMIN_SECTIONS = [
  {
    title: "Огляд",
    accent: true,
    links: [
      { to: "/app/hub", label: "Єдиний центр", icon: Sparkles, end: true },
      { to: "/app/activity", label: "Стрічка активності", icon: Activity },
      { to: "/app", label: "Дашборд", icon: LayoutDashboard, end: true },
      { to: "/app/executive", label: "Директорський центр", icon: Crown },
      { to: "/app/operations", label: "Операції", icon: Workflow },
      { to: "/app/operations360", label: "Операції 360", icon: BarChart3 },
    ],
  },
  {
    title: "Клієнти та продажі",
    links: [
      { to: "/app/companies", label: "Компанії", icon: Building2 },
      { to: "/app/customers", label: "Клієнти", icon: Users },
      { to: "/app/leads", label: "Ліди", icon: UserPlus },
      { to: "/app/requests", label: "Заявки", icon: ClipboardList },
      { to: "/app/inquiries", label: "Звернення", icon: Inbox },
    ],
  },
  {
    title: "Команда · CRM",
    links: [
      { to: "/app/crm", label: "CRM-хаб", icon: LayoutDashboard, end: true },
      { to: "/app/crm/actions", label: "Центр дій", icon: Zap },
      { to: "/app/crm/tasks", label: "Завдання команди", icon: ListTodo },
      { to: "/app/crm/calls", label: "Дзвінки команди", icon: Phone },
      { to: "/app/ringostat", label: "Ringostat (кол-трекінг)", icon: PhoneCall },
      { to: "/app/call-intelligence", label: "AI-розшифровка дзвінків", icon: Sparkles },
      { to: "/app/crm/messages", label: "Повідомлення", icon: MessageSquare },
      { to: "/app/crm/notifications", label: "Сповіщення", icon: Bell },
    ],
  },
  {
    title: "Документи та рахунки",
    links: [
      { to: "/app/contracts", label: "Договори 360", icon: ShieldCheck },
      { to: "/app/contract-flow", label: "Універсальні договори", icon: FileStack },
      { to: "/app/contract-flow/types", label: "Типи договорів", icon: Database },
      { to: "/app/contract-flow/templates", label: "Шаблони договорів", icon: FileStack },
      { to: "/app/finance", label: "Фінанси 360", icon: BarChart3 },
      { to: "/app/crm/invoices", label: "Рахунки", icon: Receipt },
      { to: "/app/crm/documents", label: "Документи", icon: FileStack },
      { to: "/app/crm/files", label: "Файли", icon: FolderArchive },
    ],
  },
  {
    title: "Каталог · Ліцензії · Тарифи",
    links: [
      { to: "/app/directory", label: "Довідник кодів", icon: Database },
      { to: "/app/waste-codes", label: "Каталог відходів", icon: BookText },
      { to: "/app/licenses", label: "Ліцензії", icon: ShieldCheck },
      { to: "/app/pricing", label: "Тарифи", icon: Banknote },
    ],
  },
  {
    title: "Контент сайту",
    links: [
      { to: "/app/blog", label: "Статті блогу", icon: BookText },
      { to: "/app/content", label: "Content Center", icon: FileText },
      { to: "/app/info", label: "Політики та інфо", icon: ScrollText },
      { to: "/app/settings/footer", label: "Футер сайту", icon: PanelBottom },
      { to: "/app/settings/contacts", label: "Контакти сайту", icon: Contact },
      { to: "/app/seo", label: "SEO Center", icon: Search },
    ],
  },
  {
    title: "Адміністрування",
    links: [
      { to: "/app/staff", label: "Центр персоналу", icon: UsersRound, end: true },
      { to: "/app/staff/assignment", label: "Розподіл лідів", icon: Shuffle },
      { to: "/app/settings", label: "Налаштування", icon: SettingsIcon },
      { to: "/app/cabinet/security", label: "Безпека (2FA)", icon: Lock },
    ],
  },
];

function buildSections(role) {
  const sections = [];
  if (role === "manager") {
    // Менеджер бачить власну, згруповану по сенсу структуру блоків.
    sections.push(...MANAGER_SECTIONS);
    return sections;
  }
  if (role === "admin") {
    // Адмін бачить власну розширену, згруповану структуру блоків.
    sections.push(...ADMIN_SECTIONS);
    return sections;
  }
  // Інші ролі (fallback) — базові спільні розділи.
  sections.push(...COMMON_SECTIONS);
  return sections;
}

const SidebarInner = ({ onNav, role, collapsed = false, onToggle }) => {
  const sections = buildSections(role);
  const location = useLocation();
  const pathname = location.pathname;

  // Чи активне посилання для поточного маршруту.
  const linkActive = (l) =>
    l.end ? pathname === l.to : (pathname === l.to || pathname.startsWith(l.to + "/"));
  const sectionHasActive = (section) => section.links.some(linkActive);

  // Акордеон розділів: ВСІ блоки за замовчуванням ЗАКРИТІ. Виняток — блок,
  // що містить активну сторінку (авто-відкривається для орієнтації).
  // Користувацькі перемикання зберігаються в localStorage (явні true/false).
  const [openSections, setOpenSections] = useState(() => {
    try { return JSON.parse(localStorage.getItem("eco_open_sections_v2") || "{}"); } catch { return {}; }
  });
  const isSectionOpen = (section) => {
    if (Object.prototype.hasOwnProperty.call(openSections, section.title)) {
      return openSections[section.title]; // явний вибір користувача має пріоритет
    }
    return sectionHasActive(section); // інакше: закрито, окрім активного блоку
  };
  const toggleSection = (section) => {
    const next = { ...openSections, [section.title]: !isSectionOpen(section) };
    setOpenSections(next);
    try { localStorage.setItem("eco_open_sections_v2", JSON.stringify(next)); } catch { /* empty */ }
  };

  const linkCls = ({ isActive }) =>
    cn(
      "group relative flex items-center rounded-xl text-sm font-medium transition-colors duration-150",
      collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
      isActive
        ? "bg-[#5BC47A] text-[#0B1A14] font-semibold shadow-sm shadow-[#5BC47A]/20"
        : "text-white/70 hover:bg-white/10 hover:text-white"
    );

  return (
    <div className="flex h-full flex-col bg-[#0B1A14] text-white">
      {/* Header / brand + collapse toggle */}
      <div className={cn("flex items-center px-3 py-4", collapsed ? "flex-col gap-3" : "gap-2 px-4")}>
        <Link to="/app" onClick={onNav} className="flex items-center gap-2 min-w-0">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#0E5E3A] text-[#5BC47A] ring-1 ring-white/10">
            <Leaf className="h-5 w-5" />
          </span>
          {!collapsed && (
            <>
              <span className="text-lg font-bold tracking-tight text-white">ECO<span className="text-[#5BC47A]">.</span><span className="text-white/55 font-semibold">NOVA</span></span>
              <span className="ml-1 rounded-md bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white/70">CRM</span>
            </>
          )}
        </Link>
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            title={collapsed ? "Розгорнути меню" : "Згорнути меню"}
            aria-label={collapsed ? "Розгорнути меню" : "Згорнути меню"}
            data-testid="sidebar-collapse-toggle"
            className={cn(
              "rounded-lg p-2 text-white/55 transition-colors hover:bg-white/10 hover:text-white",
              collapsed ? "" : "ml-auto"
            )}
          >
            {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto overflow-x-hidden px-3 pb-4">
        {sections.map((section, idx) => {
          const open = isSectionOpen(section);
          return (
            <div key={section.title} className={idx > 0 ? "mt-1.5" : ""}>
              {collapsed ? (
                idx > 0 && <div className="mx-1 my-2 border-t border-white/10" />
              ) : (
                <button
                  type="button"
                  onClick={() => toggleSection(section)}
                  data-testid={`sidebar-section-${section.title}`}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg px-2 pb-1 pt-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-colors hover:text-white",
                    section.accent ? "text-[#5BC47A]/80" : "text-white/40"
                  )}
                >
                  <span className="truncate">{section.title}</span>
                  <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-200", open ? "" : "-rotate-90")} />
                </button>
              )}
              {(collapsed || open) && (
                <div className="flex flex-col gap-0.5">
                  {section.links.map((l) => (
                    <NavLink
                      key={l.to}
                      to={l.to}
                      end={l.end}
                      className={linkCls}
                      onClick={onNav}
                      title={collapsed ? l.label : undefined}
                      data-testid={`sidebar-${l.label}-link`}
                    >
                      <l.icon className="h-[18px] w-[18px] shrink-0" />
                      {!collapsed && <span className="truncate">{l.label}</span>}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className={cn("border-t border-white/10 py-4 text-[11px] text-white/40", collapsed ? "px-2 text-center" : "px-5")}>
        {collapsed ? "UA" : "Платформа утилізації · Україна"}
      </div>
    </div>
  );
};

export default function PortalLayout() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("eco_sidebar_collapsed") === "1"; } catch { return false; }
  });
  const navigate = useNavigate();

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c;
      try { localStorage.setItem("eco_sidebar_collapsed", next ? "1" : "0"); } catch { /* empty */ }
      return next;
    });
  };

  if (loading) return <div className="flex h-screen items-center justify-center bg-[#EEF4EF] text-slate-400">Завантаження…</div>;
  if (!user) return <Navigate to="/admin" replace />;
  const initials = (user.name || user.email || "?").trim().charAt(0).toUpperCase();

  return (
    <div className="flex min-h-screen bg-[#EEF4EF] bg-[radial-gradient(120%_120%_at_0%_0%,#F2F8F3_0%,#E7F0EA_55%,#E1ECE4_100%)]">
      {/* Desktop sidebar — collapsible */}
      <aside
        className={cn(
          "hidden shrink-0 transition-[width] duration-200 ease-in-out lg:block",
          collapsed ? "w-[76px]" : "w-[260px]"
        )}
      >
        <div className="sticky top-0 h-screen">
          <SidebarInner role={user.role} collapsed={collapsed} onToggle={toggleCollapsed} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-[#0B1A14]/10 bg-white/80 px-4 backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-3">
            {/* Mobile menu */}
            <div className="lg:hidden">
              <Sheet open={open} onOpenChange={setOpen}>
                <SheetTrigger asChild><Button variant="ghost" size="icon" data-testid="mobile-menu-button"><Menu className="h-5 w-5" /></Button></SheetTrigger>
                <SheetContent side="left" className="w-[260px] border-0 p-0"><SidebarInner role={user.role} onNav={() => setOpen(false)} /></SheetContent>
              </Sheet>
            </div>
            {/* Desktop collapse toggle (also in header for discoverability) */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleCollapsed}
              className="hidden lg:inline-flex"
              title={collapsed ? "Розгорнути меню" : "Згорнути меню"}
              data-testid="header-collapse-toggle"
            >
              {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
            </Button>
            <div className="hidden text-sm font-medium text-slate-500 md:block">Робочий простір оператора</div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
              className="hidden items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-400 shadow-sm transition-colors hover:border-[#5BC47A]/50 hover:text-slate-700 lg:flex"
              title="Командна палітра (Ctrl+K)"
              data-testid="header-command-palette-trigger"
            >
              <Command className="h-3.5 w-3.5" />
              <kbd className="rounded border border-slate-200 bg-slate-50 px-1 text-[10px]">⌘K</kbd>
            </button>
            <CrmSearch />
            <UnifiedNotifications />
            <NotificationBell />
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium text-slate-800">{user.name || user.email}</div>
              <div className="text-xs font-medium text-[#0E5E3A]">{user.role}</div>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#0E5E3A] text-sm font-semibold text-[#5BC47A]">{initials}</span>
            <Button variant="ghost" size="icon" onClick={() => { logout(); navigate("/admin"); }} data-testid="logout-button"><LogOut className="h-[18px] w-[18px]" /></Button>
          </div>
        </header>
        <CallsLiveLayer />
        <div className="min-w-0 flex-1 overflow-x-clip p-6 sm:px-8 sm:py-8 lg:p-[50px]"><Suspense fallback={<RouteFallback />}><Outlet /></Suspense></div>
      </div>
      <CommandPalette />
    </div>
  );
}
