import { useState } from "react";

import { USER_STORAGE_KEY } from "../config";
import { readStoredUser } from "../utils/formatters";

export function useStoredUser() {
  const [user, setUser] = useState(() => readStoredUser(USER_STORAGE_KEY));

  function updateUser(nextUser) {
    if (nextUser)
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser));
    else localStorage.removeItem(USER_STORAGE_KEY);
    setUser(nextUser);
  }

  return [user, updateUser];
}
