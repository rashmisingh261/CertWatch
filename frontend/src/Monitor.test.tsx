import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { MonitorStatusBadge } from "./components/MonitorStatusBadge";
import { MonitorPage } from "./pages/MonitorPage";
import type { MonitoredDomain, MonitoredDomainDetail, MonitorStatus, Observation } from "./types";

const dom = (over: Partial<MonitoredDomain> = {}): MonitoredDomain => ({
  id: 1, domain: "example.com", added_at: "2026-01-01T00:00:00+00:00",
  last_checked_at: "2026-02-01T10:00:00+00:00", last_changed_at: null, status: "HEALTHY",
  issuer: "Test CA", not_after: "2026-06-01T00:00:00+00:00", days_remaining: 90,
  fingerprint_sha256: "AA:BB", tls_version: "TLSv1.3", last_error: null, ...over,
});

const obs = (over: Partial<Observation> = {}): Observation => ({
  id: 1, observed_at: "2026-02-01T10:00:00+00:00", outcome: "ok", status: "HEALTHY", ip_address: "1.2.3.4",
  fingerprint_sha256: "AA:BB", issuer: "CN=Test CA", subject: "CN=example.com", serial_number: "1",
  not_before: null, not_after: "2026-06-01T00:00:00+00:00", tls_version: "TLSv1.3",
  signature_algorithm: "sha256", public_key: "EC", sans: [], trusted: true, trust_error: null,
  hostname_match: true, changed: false, changes: null, error_code: null, error_message: null, ...over,
});

const detail = (d: MonitoredDomain, observations: Observation[]): MonitoredDomainDetail => ({ ...d, observations });

interface Api {
  domains: MonitoredDomain[];
  details: Record<number, MonitoredDomainDetail>;
  onAdd?: (domain: string) => { status: number; body: unknown };
  onCheck?: (id: number) => { status: number; body: unknown };
}

function mockApi(api: Api) {
  const calls: Array<{ method: string; url: string; body?: unknown }> = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    calls.push({ method, url, body });
    const reply = (status: number, data?: unknown) => ({ ok: status < 400, status, json: async () => data });
    if (url === "/api/monitor" && method === "GET") return reply(200, api.domains);
    if (url === "/api/monitor" && method === "POST") {
      const r = api.onAdd!(body.domain);
      return reply(r.status, r.body);
    }
    const id = Number(url.split("/")[3]);
    if (url.endsWith("/check")) {
      const r = api.onCheck!(id);
      return reply(r.status, r.body);
    }
    if (method === "DELETE") {
      api.domains = api.domains.filter((d) => d.id !== id);
      return reply(204);
    }
    return reply(200, api.details[id]);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("MonitorPage", () => {
  it("lists monitored domains with issuer, expiry, days, last checked and status", async () => {
    mockApi({ domains: [dom(), dom({ id: 2, domain: "soon.example.org", status: "EXPIRING_SOON", days_remaining: 5, issuer: "Other CA" })], details: {} });
    render(<MonitorPage />);
    const row = await screen.findByTestId("row-example.com");
    expect(within(row).getByText("Test CA")).toBeInTheDocument();
    expect(within(row).getByTestId("status-HEALTHY")).toHaveTextContent("Healthy");
    expect(screen.getByTestId("days-example.com")).toHaveTextContent("90 days");
    expect(within(row).getByText(/Feb 1, 2026/)).toBeInTheDocument();
    expect(within(screen.getByTestId("row-soon.example.org")).getByTestId("status-EXPIRING_SOON")).toBeInTheDocument();
    expect(screen.getByTestId("days-soon.example.org")).toHaveTextContent("5 days");
  });

  it("shows an empty state", async () => {
    mockApi({ domains: [], details: {} });
    render(<MonitorPage />);
    expect(await screen.findByText(/no domains are being monitored/i)).toBeInTheDocument();
  });

  it("shows expired and failed states clearly", async () => {
    mockApi({
      domains: [
        dom({ id: 1, domain: "old.example.com", status: "EXPIRED", days_remaining: -3 }),
        dom({ id: 2, domain: "down.example.com", status: "CHECK_FAILED", last_error: "Could not connect to the server on port 443." }),
      ],
      details: {},
    });
    render(<MonitorPage />);
    expect(await screen.findByTestId("days-old.example.com")).toHaveTextContent("Expired 3d ago");
    expect(screen.getByText(/Could not connect/)).toBeInTheDocument();
  });

  it("adds a domain, clears the input and refreshes the list", async () => {
    const api: Api = {
      domains: [], details: {},
      onAdd: (d) => {
        const created = dom({ domain: d });
        api.domains = [created];
        return { status: 201, body: detail(created, [obs()]) };
      },
    };
    const calls = mockApi(api);
    render(<MonitorPage />);
    await screen.findByText(/no domains/i);
    await userEvent.type(screen.getByLabelText(/domain name/i), "new.example.com");
    await userEvent.click(screen.getByRole("button", { name: /add domain/i }));

    expect(await screen.findByTestId("row-new.example.com")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ domain: "new.example.com" });
    expect(screen.getByLabelText(/domain name/i)).toHaveValue("");
    expect(screen.getByRole("region", { name: /history for new.example.com/i })).toBeInTheDocument();
  });

  it("shows duplicate errors and keeps the typed domain", async () => {
    mockApi({
      domains: [dom()], details: {},
      onAdd: () => ({ status: 409, body: { error: { code: "duplicate_domain", message: "'example.com' is already being monitored." } } }),
    });
    render(<MonitorPage />);
    await screen.findByTestId("row-example.com");
    await userEvent.type(screen.getByLabelText(/domain name/i), "example.com");
    await userEvent.click(screen.getByRole("button", { name: /add domain/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already being monitored");
    expect(screen.getByLabelText(/domain name/i)).toHaveValue("example.com");
  });

  it("Check now calls the API and updates the row", async () => {
    const api: Api = {
      domains: [dom()], details: {},
      onCheck: () => {
        api.domains = [dom({ status: "CHANGED", fingerprint_sha256: "CC:DD" })];
        return { status: 200, body: detail(api.domains[0], [obs()]) };
      },
    };
    const calls = mockApi(api);
    render(<MonitorPage />);
    await userEvent.click(await screen.findByRole("button", { name: /check example.com now/i }));
    await waitFor(() => expect(screen.getByTestId("status-CHANGED")).toBeInTheDocument());
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/monitor/1/check")).toBe(true);
  });

  it("shows the server message when a check is rate limited", async () => {
    mockApi({
      domains: [dom()], details: {},
      onCheck: () => ({ status: 429, body: { error: { code: "rate_limited", message: "'example.com' was checked moments ago. Please wait 8s." } } }),
    });
    render(<MonitorPage />);
    await userEvent.click(await screen.findByRole("button", { name: /check example.com now/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please wait 8s");
  });

  it("removes a domain after confirmation", async () => {
    const calls = mockApi({ domains: [dom()], details: {} });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<MonitorPage />);
    await userEvent.click(await screen.findByRole("button", { name: /remove example.com/i }));
    await waitFor(() => expect(screen.queryByTestId("row-example.com")).not.toBeInTheDocument());
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/monitor/1")).toBe(true);
  });

  it("does not remove when the confirmation is cancelled", async () => {
    const calls = mockApi({ domains: [dom()], details: {} });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<MonitorPage />);
    await userEvent.click(await screen.findByRole("button", { name: /remove example.com/i }));
    expect(screen.getByTestId("row-example.com")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("shows certificate history with fingerprint changes and what changed", async () => {
    const changed = obs({
      id: 2, observed_at: "2026-03-01T10:00:00+00:00", status: "CHANGED", fingerprint_sha256: "NEW:FP", changed: true,
      changes: {
        hint: "Issued by a different CA. This is expected if you switched CA; otherwise it is worth verifying.",
        fields: [{ key: "issuer", label: "Issuer", before: "CN=CA One", after: "CN=CA Two" }],
        sans_added: ["api.example.com"], sans_removed: ["www.example.com"],
      },
    });
    const failed = obs({ id: 3, observed_at: "2026-03-02T10:00:00+00:00", outcome: "failed", status: "CHECK_FAILED", fingerprint_sha256: null, error_message: "Connection timed out." });
    const d = dom({ status: "CHECK_FAILED" });
    mockApi({ domains: [d], details: { 1: detail(d, [failed, changed, obs({ fingerprint_sha256: "OLD:FP" })]) } });
    render(<MonitorPage />);
    await userEvent.click(await screen.findByRole("button", { name: /view history for example.com/i }));

    const items = await screen.findAllByTestId("observation");
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByText(/Connection timed out/)).toBeInTheDocument();
    const box = within(items[1]).getByTestId("change-box");
    expect(within(box).getByText("CN=CA One")).toBeInTheDocument();
    expect(within(box).getByText("CN=CA Two")).toBeInTheDocument();
    expect(within(box).getByText(/different CA/)).toBeInTheDocument();
    expect(within(box).getByText(/api.example.com/)).toHaveClass("chip-added");
    expect(within(box).getByText(/www.example.com/)).toHaveClass("chip-removed");
    // previous fingerprint is still visible alongside the new one
    expect(screen.getByText("OLD:FP")).toBeInTheDocument();
    expect(screen.getByText("NEW:FP")).toBeInTheDocument();
    // wording stays neutral
    expect(screen.queryByText(/malicious|attack|compromis/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("region", { name: /history for/i })).not.toBeInTheDocument();
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    render(<MonitorPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/backend running/i);
  });
});

describe("MonitorStatusBadge", () => {
  it.each<[MonitorStatus, string]>([
    ["HEALTHY", "Healthy"], ["EXPIRING_SOON", "Expiring soon"], ["EXPIRED", "Expired"],
    ["INVALID", "Invalid"], ["CHECK_FAILED", "Check failed"], ["CHANGED", "Changed"],
  ])("renders %s", (status, label) => {
    render(<MonitorStatusBadge status={status} />);
    expect(screen.getByTestId(`status-${status}`)).toHaveTextContent(label);
  });
});

describe("navigation", () => {
  it("opens the Monitor tab", async () => {
    mockApi({ domains: [], details: {} });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Monitor" }));
    expect(screen.getByRole("heading", { name: /monitor/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add domain/i })).toBeInTheDocument();
  });
});
