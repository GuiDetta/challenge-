import { useCallback, useState } from "react";

import { USER_STORAGE_KEY } from "../config";
import { readStoredUser } from "../utils/formatters";

export function useStoredUser(key = USER_STORAGE_KEY) {
  const [user, setUser] = useState(() => readStoredUser(key));

  const updateUser = useCallback(
    (nextUser) => {
      if (nextUser) localStorage.setItem(key, JSON.stringify(nextUser));
      else localStorage.removeItem(key);
      setUser(nextUser);
    },
    [key],
  );

  return [user, updateUser];
}
