import { useCallback, useEffect, useState } from "react";
import {
  ApiError, addMonitored, checkMonitored, getMonitored, listMonitored, removeMonitored,
} from "../api/client";
import { DomainForm } from "../components/DomainForm";
import { ErrorAlert } from "../components/ErrorAlert";
import { MonitorHistory } from "../components/MonitorHistory";
import { MonitorTable } from "../components/MonitorTable";
import type { MonitoredDomain, MonitoredDomainDetail } from "../types";

const msg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

export function MonitorPage() {
  const [domains, setDomains] = useState<MonitoredDomain[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<MonitoredDomainDetail | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDomains(await listMonitored());
    } catch (e) {
      setError(msg(e));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function add(domain: string): Promise<boolean> {
    setAdding(true);
    setError(null);
    try {
      const created = await addMonitored(domain);
      setDetail(created);
      await refresh();
      return true;
    } catch (e) {
      setError(msg(e));
      return false;
    } finally {
      setAdding(false);
    }
  }

  async function check(d: MonitoredDomain) {
    setBusyId(d.id);
    setError(null);
    try {
      const updated = await checkMonitored(d.id);
      if (detail?.id === d.id) setDetail(updated);
      await refresh();
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(d: MonitoredDomain) {
    if (!window.confirm(`Stop monitoring ${d.domain}? Its history will be deleted.`)) return;
    setBusyId(d.id);
    setError(null);
    try {
      await removeMonitored(d.id);
      if (detail?.id === d.id) setDetail(null);
      await refresh();
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusyId(null);
    }
  }

  async function select(d: MonitoredDomain) {
    setError(null);
    try {
      setDetail(await getMonitored(d.id));
    } catch (e) {
      setError(msg(e));
    }
  }

  return (
    <>
      <header>
        <h1>📡 Monitor</h1>
        <p className="muted">
          Save domains and track their certificates. Checks run only when you press <em>Check now</em>.
          Data is stored locally.
        </p>
      </header>

      <DomainForm loading={adding} onSubmit={add} buttonLabel="Add Domain" busyLabel="Adding…" />

      {error && <ErrorAlert message={error} />}
      {adding && <p className="muted" aria-live="polite">Validating and checking the certificate…</p>}

      {loadingList ? (
        <p className="muted" aria-live="polite">Loading…</p>
      ) : (
        <MonitorTable
          domains={domains}
          busyId={busyId}
          selectedId={detail?.id ?? null}
          onCheck={check}
          onRemove={remove}
          onSelect={select}
        />
      )}

      {detail && <MonitorHistory detail={detail} onClose={() => setDetail(null)} />}
    </>
  );
}
