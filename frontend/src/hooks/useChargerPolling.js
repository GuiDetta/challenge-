import { useEffect, useState } from "react";

import { fetchChargers } from "../services/api";

export function useChargerPolling(planId, ownerId, interval = 5000) {
  const [chargers, setChargers] = useState([]);

  useEffect(() => {
    if (!planId || !ownerId) {
      setChargers([]);
      return undefined;
    }
    let active = true;
    const refresh = async () => {
      try {
        const nextChargers = await fetchChargers(planId, ownerId);
        if (active) setChargers(nextChargers);
      } catch {
        // Mantém a última leitura durante indisponibilidades breves.
      }
    };
    refresh();
    const timer = window.setInterval(refresh, interval);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [planId, ownerId, interval]);

  return [chargers, setChargers];
}
