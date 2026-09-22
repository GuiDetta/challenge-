import { useEffect, useState } from "react";

import { fetchErrorLog, fetchOperationsReport, fetchReport } from "../services/api";

export function useReports(ownerId) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchReport(ownerId)
      .then((nextReport) => active && setReport(nextReport))
      .catch((requestError) => active && setError(requestError.message));
    return () => {
      active = false;
    };
  }, [ownerId]);

  return { report, error };
}

export function useErrorLog(ownerId, days = 7, limit = 20) {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    let active = true;
    fetchErrorLog(ownerId, days, limit)
      .then((payload) => active && setEvents(payload.events || []))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [ownerId, days, limit]);

  return events;
}

export function useOperationsReport(ownerId, days = 7) {
  const [operations, setOperations] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchOperationsReport(ownerId, days)
      .then((next) => active && setOperations(next))
      .catch((requestError) => active && setError(requestError.message));
    return () => {
      active = false;
    };
  }, [ownerId, days]);

  return { operations, error };
}
