import { useState } from "react";
import { CertDiffPage } from "./pages/CertDiffPage";
import { Dashboard } from "./pages/Dashboard";
import { MonitorPage } from "./pages/MonitorPage";

type Tab = "inspect" | "diff" | "monitor";

export default function App() {
  const [tab, setTab] = useState<Tab>("inspect");
  return (
    <main className="container">
      <nav className="tabs" aria-label="Tools">
        <button type="button" className={tab === "inspect" ? "tab active" : "tab"} aria-current={tab === "inspect" ? "page" : undefined} onClick={() => setTab("inspect")}>
          Inspector
        </button>
        <button type="button" className={tab === "diff" ? "tab active" : "tab"} aria-current={tab === "diff" ? "page" : undefined} onClick={() => setTab("diff")}>
          CertDiff
        </button>
        <button type="button" className={tab === "monitor" ? "tab active" : "tab"} aria-current={tab === "monitor" ? "page" : undefined} onClick={() => setTab("monitor")}>
          Monitor
        </button>
      </nav>
      {tab === "inspect" ? <Dashboard /> : tab === "diff" ? <CertDiffPage /> : <MonitorPage />}
    </main>
  );
}
