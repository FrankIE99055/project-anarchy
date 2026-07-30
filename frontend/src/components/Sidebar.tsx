"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Building2, BarChart3, TrendingUp, Menu, X } from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/properties", label: "Properties", icon: Building2 },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/market-report", label: "Market Report", icon: TrendingUp },
];

function SidebarContent({ pathname }: { pathname: string }) {
  return (
    <>
      <div className="px-6 py-5 border-b border-slate-800">
        <h1 className="text-lg font-bold text-white tracking-tight">
          Project Anarchy
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Propensity to Sell &middot; Ireland
        </p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-slate-800 text-xs text-slate-500">
        Data: PPR &middot; Planning &middot; Daft &middot; Derelict Sites
      </div>
    </>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar - always visible, fixed width */}
      <aside className="hidden lg:flex w-64 shrink-0 bg-slate-900 text-slate-200 flex-col h-screen sticky top-0">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Mobile topbar with hamburger button */}
      <div className="lg:hidden fixed top-0 inset-x-0 z-40 flex items-center justify-between bg-slate-900 text-white px-4 py-3">
        <span className="font-bold">Project Anarchy</span>
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          className="p-1.5 rounded-md hover:bg-slate-800"
        >
          <Menu size={22} />
        </button>
      </div>

      {/* Mobile slide-over sidebar */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative w-64 bg-slate-900 text-slate-200 flex flex-col h-full">
            <button
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
              className="absolute top-4 right-4 p-1 rounded-md hover:bg-slate-800"
            >
              <X size={20} />
            </button>
            <SidebarContent pathname={pathname} />
          </aside>
        </div>
      )}
    </>
  );
}
