import React from "react";
import { Link } from "react-router-dom";
import { House, BookOpen } from "@phosphor-icons/react";import BlogArticlesEditor from "./BlogArticlesEditor";

/**
 * Standalone admin page for managing blog articles.
 * Promoted out of `AdminInfoPage` (where it used to live as a tab) into its
 * own page mounted at `/app/blog` so navigation is shallower and the editor
 * has the full canvas to itself.
 */
export default function AdminBlogPage() {
  return (
    <div className="min-h-screen bg-[#F4F4F5]">
      {/* Top header strip */}
      <div className="border-b border-[#E4E4E7] bg-white">
        <div className="px-6 lg:px-10 py-5 flex items-center justify-between gap-4">
          <div>
            <nav className="text-[11px] uppercase tracking-[0.18em] text-[#71717A] flex items-center gap-2 mb-2">
              <Link to="/app" className="hover:text-[#18181B] inline-flex items-center gap-1.5">
                <House weight="regular" size={12}/> Адмінка
              </Link>
              <span aria-hidden="true">·</span>
              <span className="text-[#71717A]">Контент сайту</span>
              <span aria-hidden="true">·</span>
              <strong className="text-[#18181B] font-semibold">Блог</strong>
            </nav>
            <h1 className="text-[28px] lg:text-[34px] font-bold tracking-tight text-[#18181B] leading-tight flex items-center gap-3">
              <span className="inline-flex w-9 h-9 rounded-xl bg-[#5BC47A]/15 text-[#365314] items-center justify-center">
                <BookOpen weight="duotone" size={20}/>
              </span>
              Статті блогу
            </h1>
            <p className="mt-2 text-sm text-[#52525B] max-w-2xl">
              Створюйте, редагуйте та публікуйте статті блогу. Редактор підтримує
              форматування, зображення, посилання, відео, таблиці та шорткоди.
              Двомовність: основна — українська, опціональна — англійська.
            </p>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs text-[#71717A]">
            <a
              href="/blog"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 rounded-full border border-[#E4E4E7] bg-white hover:bg-[#F4F4F5] transition text-[#18181B] font-semibold"
              data-testid="open-public-blog"
            >
              Відкрити публічний блог ↗
            </a>
          </div>
        </div>
      </div>

      {/* Editor body */}
      <div className="px-6 lg:px-10 py-6 lg:py-8">
        <BlogArticlesEditor />
      </div>
    </div>
  );
}
