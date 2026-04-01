"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { isLoggedIn, logout } from "@/lib/api";
import {
  MessageSquare, SquareKanban, BookOpen,
  FileText, Calendar, Brain, LogOut, Briefcase, Settings,
} from "lucide-react";
import clsx from "clsx";
import ProviderStatus from "@/components/shared/ProviderStatus";
import FuturoLogo from "@/components/shared/FuturoLogo";

const NAV = [
  { href: "/chat",       label: "Chat",       icon: MessageSquare },
  { href: "/jobs",       label: "Jobs",       icon: Briefcase     },
  { href: "/campaign",   label: "Company",    icon: SquareKanban  },
  { href: "/stories",    label: "Stories",    icon: BookOpen      },
  { href: "/resume",     label: "Resume",     icon: FileText      },
  { href: "/interviews", label: "Interviews", icon: Calendar      },
  { href: "/memory",     label: "Memory",     icon: Brain         },
  { href: "/settings",   label: "Settings",   icon: Settings      },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoggedIn()) router.replace("/login");
  }, [router]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <FuturoLogo
              size={32}
              className="h-8 w-8 rounded-lg object-cover shadow-sm"
            />
            <span className="font-semibold text-gray-900">Futuro</span>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto scrollbar-thin">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link key={href} href={href}
                className={clsx(
                  "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                  active
                    ? "bg-futuro-50 text-futuro-600 font-medium"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <Icon size={16} className={active ? "text-futuro-500" : "text-gray-400"} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Provider status indicator */}
        <div className="border-t border-gray-100 pt-2">
          <ProviderStatus />
        </div>

        <div className="px-3 pb-3 border-t border-gray-100 pt-2">
          <button onClick={handleLogout}
            className="flex items-center gap-2.5 px-3 py-2 w-full rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <LogOut size={16} className="text-gray-400" />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-hidden flex flex-col">
        {children}
      </main>
    </div>
  );
}
