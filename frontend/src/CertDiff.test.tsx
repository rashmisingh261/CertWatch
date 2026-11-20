import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { DiffTable } from "./components/DiffTable";
import { buildReport } from "./lib/exportReport";
import { CertDiffPage } from "./pages/CertDiffPage";
import { diffResult } from "./diffFixtures";

const pem = (name: string, size = 50) =>
  new File(["-----BEGIN CERTIFICATE-----\n".padEnd(size, "x")], name, { type: "application/x-pem-file" });

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
  vi.stubGlobal("fetch", fn);
  return fn;
}

async function pickFiles() {
  await userEvent.upload(screen.getByLabelText("Certificate A"), pem("a.pem"));
  await userEvent.upload(screen.getByLabelText("Certificate B"), pem("b.pem"));
}

afterEach(() => vi.unstubAllGlobals());

describe("CertDiffPage", () => {
  it("disables Compare until both files are chosen", async () => {
    render(<CertDiffPage />);
    const btn = screen.getByRole("button", { name: /compare certificates/i });
    expect(btn).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Certificate A"), pem("a.pem"));
    expect(btn).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Certificate B"), pem("b.pem"));
    expect(btn).toBeEnabled();
    expect(screen.getByTestId("file-Certificate A")).toHaveTextContent("a.pem");
  });

  it("uploads both files as multipart and shows results", async () => {
    const fetchMock = mockFetch(200, diffResult);
    render(<CertDiffPage />);
    await pickFiles();
    await userEvent.click(screen.getByRole("button", { name: /compare certificates/i }));

    expect(await screen.findByRole("region", { name: /comparison/i })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/certdiff");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("certificate_a")).toBeInstanceOf(File);
    expect(((init.body as FormData).get("certificate_b") as File).name).toBe("b.pem");
    expect(screen.getByRole("button", { name: /export json/i })).toBeInTheDocument();
  });

  it("shows server validation errors and no results", async () => {
    mockFetch(422, { error: { code: "invalid_certificate", message: "Certificate A: the file contains a private key." } });
    render(<CertDiffPage />);
    await pickFiles();
    await userEvent.click(screen.getByRole("button", { name: /compare certificates/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("contains a private key");
    expect(screen.queryByRole("region", { name: /comparison/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /export json/i })).not.toBeInTheDocument();
  });

  it("rejects an oversized file client-side without calling the API", async () => {
    const fetchMock = mockFetch(200, diffResult);
    render(<CertDiffPage />);
    const big = new File([new Uint8Array(1_000_001)], "big.pem");
    await userEvent.upload(screen.getByLabelText("Certificate A"), big);
    expect(screen.getByRole("alert")).toHaveTextContent(/too large/i);
    expect(screen.getByRole("button", { name: /compare certificates/i })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an empty file client-side", async () => {
    render(<CertDiffPage />);
    await userEvent.upload(screen.getByLabelText("Certificate B"), new File([], "empty.pem"));
    expect(screen.getByRole("alert")).toHaveTextContent(/empty/i);
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    render(<CertDiffPage />);
    await pickFiles();
    await userEvent.click(screen.getByRole("button", { name: /compare certificates/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/backend running/i);
  });

  it("lets the user remove a chosen file", async () => {
    render(<CertDiffPage />);
    await userEvent.upload(screen.getByLabelText("Certificate A"), pem("a.pem"));
    await userEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(screen.queryByTestId("file-Certificate A")).not.toBeInTheDocument();
  });
});

describe("DiffTable", () => {
  it("shows a status for every field and summary counts", () => {
    render(<DiffTable result={diffResult} />);
    expect(within(screen.getByTestId("row-subject")).getByText(/unchanged/i)).toBeInTheDocument();
    expect(within(screen.getByTestId("row-issuer")).getByText(/modified/i)).toBeInTheDocument();
    expect(within(screen.getByTestId("row-basic_constraints")).getByText(/added/i)).toBeInTheDocument();
    expect(screen.getByTestId("count-MODIFIED")).toHaveTextContent("Modified: 2");
    expect(screen.getByTestId("count-ADDED")).toHaveTextContent("Added: 1");
  });

  it("marks removed and added SAN entries on the correct side", () => {
    render(<DiffTable result={diffResult} />);
    const [cellA, cellB] = within(screen.getByTestId("row-sans")).getAllByRole("list");
    expect(within(cellA).getByText(/DNS:www.example.com/)).toHaveClass("chip-removed");
    expect(within(cellA).getByText("DNS:example.com")).toHaveClass("chip-same");
    expect(within(cellB).getByText(/DNS:api.example.com/)).toHaveClass("chip-added");
  });

  it("shows side-by-side values and a placeholder for missing extensions", () => {
    render(<DiffTable result={diffResult} />);
    const row = within(screen.getByTestId("row-basic_constraints"));
    expect(row.getByText(/not present/)).toBeInTheDocument();
    expect(row.getByText("CA: false")).toBeInTheDocument();
  });

  it("expands details with an explanation", async () => {
    render(<DiffTable result={diffResult} />);
    expect(screen.queryByText(/Different CAs/)).not.toBeInTheDocument();
    const toggle = within(screen.getByTestId("row-issuer")).getByRole("button", { name: /details/i });
    await userEvent.click(toggle);
    expect(screen.getByText(/Different CAs/)).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("can filter to differences only", async () => {
    render(<DiffTable result={diffResult} />);
    await userEvent.click(screen.getByLabelText(/differences only/i));
    expect(screen.queryByTestId("row-subject")).not.toBeInTheDocument();
    expect(screen.getByTestId("row-issuer")).toBeInTheDocument();
  });
});

describe("export", () => {
  it("builds a report with all required sections", () => {
    const r = buildReport(diffResult);
    expect(r.compared_at).toBe(diffResult.compared_at);
    expect(r.certificate_a.filename).toBe("a.pem");
    expect(r.certificate_b.serial_number).toBe("2");
    expect(r.comparison).toHaveLength(diffResult.fields.length);
    expect(r.added_values).toContainEqual({ field: "Subject Alternative Names", values: ["DNS:api.example.com"] });
    expect(r.added_values).toContainEqual({ field: "Basic Constraints", values: ["CA: false"] });
    expect(r.removed_values).toEqual([{ field: "Subject Alternative Names", values: ["DNS:www.example.com"] }]);
    expect(r.modified_values.map((m) => m.field)).toEqual(["Issuer", "Subject Alternative Names"]);
    expect(r.unchanged_values.map((u) => u.field)).toEqual(["Subject", "Key Usage"]);
    expect(JSON.stringify(r)).not.toMatch(/BEGIN (CERTIFICATE|.*PRIVATE KEY)/);
  });

  it("downloads a JSON file when Export JSON is clicked", async () => {
    mockFetch(200, diffResult);
    const create = vi.fn(() => "blob:x");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<CertDiffPage />);
    await pickFiles();
    await userEvent.click(screen.getByRole("button", { name: /compare certificates/i }));
    await userEvent.click(await screen.findByRole("button", { name: /export json/i }));
    expect(create).toHaveBeenCalledTimes(1);
    const blob = (create.mock.calls[0] as unknown as [Blob])[0];
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.readAsText(blob);
    });
    expect(JSON.parse(text).comparison).toHaveLength(diffResult.fields.length);
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalled();
    click.mockRestore();
  });
});

describe("App navigation", () => {
  it("switches between Inspector and CertDiff", async () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /^inspect$/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "CertDiff" }));
    expect(screen.getByRole("heading", { name: /certdiff/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Inspector" }));
    expect(screen.getByLabelText(/domain name/i)).toBeInTheDocument();
  });
});
