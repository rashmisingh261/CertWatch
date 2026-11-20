import { FormEvent, useState } from "react";

interface Props {
  loading: boolean;
  /** May return a promise resolving to true to clear the input after success. */
  onSubmit: (domain: string) => void | boolean | Promise<boolean | void>;
  buttonLabel?: string;
  busyLabel?: string;
}

export function DomainForm({ loading, onSubmit, buttonLabel = "Inspect", busyLabel = "Inspecting…" }: Props) {
  const [value, setValue] = useState("");

  async function handle(e: FormEvent) {
    e.preventDefault();
    if (!value.trim() || loading) return;
    const ok = await onSubmit(value.trim());
    if (ok === true) setValue("");
  }

  return (
    <form className="domain-form" onSubmit={handle}>
      <label htmlFor="domain" className="sr-only">
        Domain name
      </label>
      <input
        id="domain"
        type="text"
        inputMode="url"
        autoComplete="off"
        autoCapitalize="off"
        spellCheck={false}
        placeholder="example.com"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={loading}
      />
      <button type="submit" disabled={loading || !value.trim()}>
        {loading ? busyLabel : buttonLabel}
      </button>
    </form>
  );
}
