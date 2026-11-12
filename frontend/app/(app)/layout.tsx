import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { HealthProvider } from "@/hooks/use-health";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <HealthProvider>
      <div className="flex min-h-screen">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader />
          <main className="flex-1 px-4 py-8 md:px-8">{children}</main>
        </div>
      </div>
    </HealthProvider>
  );
}
