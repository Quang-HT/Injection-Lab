import { createContext, useContext, useEffect, useState, useTransition } from "react";

import { getBootstrap } from "../api";

const AppContext = createContext(null);
const STORAGE_KEY = "sql-training-lab-user";

function createUserId() {
  if (typeof window === "undefined") {
    return "local-trainee";
  }

  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const generated = `trainee-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(STORAGE_KEY, generated);
  return generated;
}

export function AppProvider({ children }) {
  const [userId] = useState(createUserId);
  const [bootstrap, setBootstrap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function refreshBootstrap() {
    setLoading(true);
    try {
      const payload = await getBootstrap(userId);
      startTransition(() => {
        setBootstrap(payload);
        setError("");
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function applyBootstrapSnapshot(snapshot) {
    startTransition(() => {
      setBootstrap(snapshot);
    });
  }

  useEffect(() => {
    refreshBootstrap();
  }, [userId]);

  return (
    <AppContext.Provider
      value={{
        userId,
        bootstrap,
        loading,
        error,
        isPending,
        refreshBootstrap,
        applyBootstrapSnapshot,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const value = useContext(AppContext);
  if (!value) {
    throw new Error("useAppContext must be used inside AppProvider");
  }
  return value;
}
