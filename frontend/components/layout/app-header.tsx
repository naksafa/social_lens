import Link from "next/link";

import { Brand } from "@/components/brand";
import { NAV_ITEMS } from "@/components/layout/nav-items";
import { BackendStatus } from "@/components/system/backend-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";

export function AppHeader() {
  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b px-4 md:px-8">
      <div className="flex items-center gap-1 md:hidden">
        <Brand href="/dashboard" />
        <nav className="ml-2 flex gap-1" aria-label="Main">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} aria-label={label} className={buttonVariants({ variant: "ghost", size: "icon" })}>
              <Icon />
            </Link>
          ))}
        </nav>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <div className="hidden sm:block">
          <BackendStatus />
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
