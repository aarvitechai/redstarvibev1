"use client";
import { useState } from "react";
import { AdsPanel, PlansPanel, VerificationPanel } from "@/components/admin/BusinessPanels";
import { DashboardPanel } from "@/components/admin/DashboardPanel";
import { AuditPanel, PlatformPanel } from "@/components/admin/PlatformPanel";
import { ReportsPanel } from "@/components/admin/ReportsPanel";
import { RolesPanel } from "@/components/admin/RolesPanel";
import { TestDataPanel } from "@/components/admin/TestDataPanel";
import { TicketsPanel } from "@/components/admin/TicketsPanel";
import { CenterSpinner, Empty } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { cn } from "@/lib/utils";

export default function AdminPage() {
  const { data: me } = useMe();
  const [chosen, setChosen] = useState<string | null>(null);
  if (!me) return <CenterSpinner />;
  const can = (permission: string) => me.permissions.includes(permission);
  if (!can("moderate_first_level")) return <Empty title="Staff only" />;
  const superAdmin = me.role === "superadmin";
  const isAdmin = superAdmin || me.role === "admin";
  const tabs: [string, string][] = [
    ...(isAdmin ? ([["dashboard", "Dashboard"]] as [string, string][]) : []),
    ["reports", "Reports"],
    ["tickets", "Tickets"],
    ...(can("verify_accounts") ? ([["verification", "Verification"]] as [string, string][]) : []),
    ...(can("approve_ads") ? ([["ads", "Ads"]] as [string, string][]) : []),
    ...(superAdmin ? ([["platform", "Platform"], ["audit", "Audit log"], ["plans", "Plans"]] as [string, string][]) : []),
    ...(isAdmin ? ([["test-data", "Test data"]] as [string, string][]) : []),
    ...(superAdmin ? ([["roles", "Admins"]] as [string, string][]) : []),
  ];
  const tab = chosen ?? tabs[0]![0];
  const title = superAdmin ? "Super admin dashboard" : isAdmin ? "Admin dashboard" : "Staff dashboard";
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">{title}</h1>
      <div role="tablist" className="grid grid-cols-3 gap-1 sm:grid-cols-5 lg:flex lg:gap-2">
        {tabs.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={tab === value} onClick={() => setChosen(value)} className={cn("min-h-11 rounded-lg px-2 text-sm font-semibold lg:flex-1", tab === value ? "bg-brand text-white" : "bg-surface")}>
            {label}
          </button>
        ))}
      </div>
      {tab === "dashboard" && <DashboardPanel onOpenReports={() => setChosen("reports")} />}
      {tab === "reports" && <ReportsPanel />}
      {tab === "tickets" && <TicketsPanel />}
      {tab === "verification" && <VerificationPanel />}
      {tab === "ads" && <AdsPanel />}
      {tab === "platform" && <PlatformPanel />}
      {tab === "audit" && <AuditPanel />}
      {tab === "plans" && <PlansPanel />}
      {tab === "test-data" && <TestDataPanel />}
      {tab === "roles" && <RolesPanel />}
    </div>
  );
}
