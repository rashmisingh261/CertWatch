import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "./pages/Dashboard";
import { validResult } from "./fixtures";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body }),
  );
}

async function submit(domain: string) {
  await userEvent.type(screen.getByLabelText(/domain name/i), domain);
  await userEvent.click(screen.getByRole("button", { name: /inspect/i }));
}

afterEach(() => vi.unstubAllGlobals());

describe("Dashboard", () => {
  it("disables Inspect when input is empty", () => {
    render(<Dashboard />);
    expect(screen.getByRole("button", { name: /inspect/i })).toBeDisabled();
  });

  it("shows certificate details on success", async () => {
    mockFetch(200, validResult);
    render(<Dashboard />);
    await submit("example.com");

    expect(await screen.findByTestId("status-title")).toHaveTextContent(/valid and trusted/i);
    expect(screen.getByTestId("days-remaining")).toHaveTextContent("42 days remaining");
    expect(screen.getByTestId("tls-version")).toHaveTextContent("TLSv1.3");
    expect(screen.getByTestId("fingerprint")).toHaveTextContent("AA:BB:CC");
    expect(screen.getByText("www.example.com")).toBeInTheDocument();
    expect(screen.getByText("Example Inc")).toBeInTheDocument();
    expect(screen.getByText("Test CA Org")).toBeInTheDocument();
  });

  it("sends the domain to the API", async () => {
    mockFetch(200, validResult);
    render(<Dashboard />);
    await submit("example.com");
    await screen.findByTestId("status-title");
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/inspect");
    expect(JSON.parse(init.body)).toEqual({ domain: "example.com" });
  });

  it("clearly separates retrieval from trust for an untrusted cert", async () => {
    mockFetch(200, {
      ...validResult,
      status: "untrusted",
      validation: { ...validResult.validation, trusted: false, trust_error: "self-signed certificate" },
    });
    render(<Dashboard />);
    await submit("self-signed.example");
    expect(await screen.findByTestId("status-title")).toHaveTextContent(/NOT trusted/i);
    expect(screen.getByText(/self-signed certificate/)).toBeInTheDocument();
    expect(screen.getByText("example.com", { selector: "dd" })).toBeInTheDocument(); // cert still shown
  });

  it("shows hostname mismatch", async () => {
    mockFetch(200, {
      ...validResult,
      status: "hostname_mismatch",
      validation: { ...validResult.validation, hostname_match: false, hostname_detail: "not covered" },
    });
    render(<Dashboard />);
    await submit("other.example");
    expect(await screen.findByTestId("status-title")).toHaveTextContent(/does not match/i);
  });

  it("shows expired information", async () => {
    mockFetch(200, {
      ...validResult,
      status: "expired",
      validity: { ...validResult.validity, days_remaining: -3, expired: true },
    });
    render(<Dashboard />);
    await submit("expired.example");
    expect(await screen.findByTestId("days-remaining")).toHaveTextContent("Expired 3 days ago");
  });

  it("shows the server's error message", async () => {
    mockFetch(422, { error: { code: "invalid_domain", message: "Enter a bare domain name." } });
    render(<Dashboard />);
    await submit("http://bad");
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a bare domain name.");
    expect(screen.queryByTestId("status-title")).not.toBeInTheDocument();
  });

  it("shows a helpful message when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<Dashboard />);
    await submit("example.com");
    expect(await screen.findByRole("alert")).toHaveTextContent(/backend running/i);
  });
});
