import { useEffect, useState } from "react";

import { fetchReport } from "../services/api";

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
