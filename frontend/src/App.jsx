import { useEffect, useMemo, useState } from "react";
import { useAuth } from "react-oidc-context";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { exchangeAwsTokenForAppToken, fetchAuthMe, fetchCatalog, fetchMyCatalog } from "./api";
import { mountVueCatalogApp } from "./microapps/vueCatalogApp";
import { mountAngularSessionApp } from "./microapps/angularSessionApp";

function App() {
  const auth = useAuth();
  const [appToken, setAppToken] = useState("");
  const [me, setMe] = useState(null);
  const [publicCatalog, setPublicCatalog] = useState([]);
  const [personalizedCatalog, setPersonalizedCatalog] = useState([]);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Waiting for sign in");

  const cognitoDomain = import.meta.env.VITE_AWS_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_AWS_USER_POOL_CLIENT_ID;
  const logoutUri = import.meta.env.VITE_AWS_LOGOUT_URI || window.location.origin;

  const oidcToken = useMemo(() => auth.user?.id_token || null, [auth.user]);
  const appTokenClaims = useMemo(() => decodeJwtClaims(appToken), [appToken]);
  const publicSummary = useMemo(() => summarizeCatalog(publicCatalog, "unit_price_gbp"), [publicCatalog]);
  const protectedSummary = useMemo(
    () => summarizeCatalog(personalizedCatalog, "customer_price_gbp"),
    [personalizedCatalog],
  );
  const publicSkus = useMemo(() => new Set(publicCatalog.map((item) => String(item?.sku))), [publicCatalog]);
  const personalizedOnlyCount = useMemo(
    () => personalizedCatalog.filter((item) => !publicSkus.has(String(item?.sku))).length,
    [personalizedCatalog, publicSkus],
  );
  const isHostReady = Boolean(auth.isAuthenticated && appToken);

  useEffect(() => {
    let active = true;
    async function loadPublicCatalog() {
      try {
        const data = await fetchCatalog(null);
        if (active) {
          setPublicCatalog(data);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed loading public catalog");
        }
      }
    }
    loadPublicCatalog();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadProtectedData() {
      if (!oidcToken) {
        setAppToken("");
        setMe(null);
        setPersonalizedCatalog([]);
        setStatus("Waiting for sign in");
        return;
      }
      setError("");
      setStatus("Exchanging Cognito token for app JWT...");
      try {
        const tokenResponse = await exchangeAwsTokenForAppToken(oidcToken);
        if (!active) {
          return;
        }
        setAppToken(tokenResponse.access_token);
        setStatus("Loading protected API data...");
        const [meData, catalogData] = await Promise.all([
          fetchAuthMe(tokenResponse.access_token),
          fetchMyCatalog(tokenResponse.access_token),
        ]);
        if (!active) {
          return;
        }
        setMe(meData);
        setPersonalizedCatalog(catalogData);
        setStatus("Logged in");
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Login failed");
        setStatus("Failed");
      }
    }

    loadProtectedData();
    return () => {
      active = false;
    };
  }, [oidcToken]);

  function signOutRedirect() {
    if (!cognitoDomain || !clientId) {
      setError("Missing VITE_AWS_COGNITO_DOMAIN or VITE_AWS_USER_POOL_CLIENT_ID");
      return;
    }
    window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`;
  }

  async function handleLogout() {
    setError("");
    await auth.removeUser();
    setAppToken("");
    setMe(null);
    setPersonalizedCatalog([]);
    setStatus("Logged out");
    signOutRedirect();
  }

  if (auth.isLoading) {
    return <main className="container">Loading...</main>;
  }

  if (auth.error) {
    return (
      <main className="container">
        <p className="error">Encountered OIDC error: {auth.error.message}</p>
      </main>
    );
  }

  return (
    <BrowserRouter>
      <main className="container">
        <header className="hero">
          <p className="eyebrow">Tails Architecture</p>
          <h1>Single Page Experience for Guests and Hosts</h1>
          <div className="heroMeta">
            <p className="status">{status}</p>
            <span className={auth.isAuthenticated ? "badge badgeHost" : "badge badgeGuest"}>
              {auth.isAuthenticated ? "Role: Host" : "Role: Guest"}
            </span>
          </div>
          {error ? <p className="error">{error}</p> : null}
        </header>

        <nav className="topNav" aria-label="Application pages">
          <NavLink to="/guest" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Guest
          </NavLink>
          <NavLink to="/host" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Host
          </NavLink>
          <NavLink to="/session" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Session
          </NavLink>
        </nav>

        <Routes>
          <Route
            path="/guest"
            element={
              <VueGuestContainer mode="guest" items={publicCatalog} summary={publicSummary} />
            }
          />
          <Route
            path="/host"
            element={
              <>
                {!auth.isAuthenticated ? (
                  <section className="panel">
                    <h2>Host Console</h2>
                    <div className="hostGate">
                      <p>Hosts can sign in to access personalized prices and protected APIs.</p>
                      <button type="button" onClick={() => auth.signinRedirect()}>
                        Sign in as host
                      </button>
                    </div>
                  </section>
                ) : null}

                {auth.isAuthenticated && !isHostReady ? (
                  <section className="panel">
                    <p className="status">Preparing host session...</p>
                  </section>
                ) : null}

                {isHostReady ? (
                  <>
                    <section className="panel">
                      <h2>Host Metrics</h2>
                      <div className="hostMetrics">
                        <article className="metric">
                          <span>Host SKUs</span>
                          <strong>{personalizedCatalog.length}</strong>
                        </article>
                        <article className="metric">
                          <span>Host-only SKUs</span>
                          <strong>{personalizedOnlyCount}</strong>
                        </article>
                        <article className="metric">
                          <span>Pricing summary</span>
                          <strong>{protectedSummary}</strong>
                        </article>
                      </div>
                    </section>
                    <VueGuestContainer mode="host" items={personalizedCatalog} summary={protectedSummary} />
                  </>
                ) : null}
              </>
            }
          />
          <Route
            path="/session"
            element={
              <AngularSessionContainer
                appToken={appToken}
                claims={appTokenClaims}
                me={me}
                isAuthenticated={auth.isAuthenticated}
                onSignIn={() => auth.signinRedirect()}
                onLogout={handleLogout}
              />
            }
          />
          <Route path="*" element={<Navigate to="/guest" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

function VueGuestContainer({ mode, items, summary }) {
  const [loadError, setLoadError] = useState("");
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cleanup = () => {};
    let isMounted = true;

    async function mountApp() {
      setLoadError("");
      setIsReady(false);
      try {
        const root = document.getElementById(`vue-guest-root-${mode}`);
        if (!root) {
          return;
        }
        cleanup = await mountVueCatalogApp(root, { mode, items, summary });
        if (isMounted) {
          setIsReady(true);
        }
      } catch (err) {
        if (isMounted) {
          setLoadError(err instanceof Error ? err.message : "Failed loading Vue guest app.");
        }
      }
    }

    mountApp();
    return () => {
      isMounted = false;
      cleanup();
    };
  }, [items, mode, summary]);

  return (
    <>
      {!isReady && !loadError ? <section className="panel">Loading Vue guest application...</section> : null}
      {loadError ? <section className="panel error">Vue guest app failed: {loadError}</section> : null}
      <div id={`vue-guest-root-${mode}`} />
    </>
  );
}

function AngularSessionContainer({ appToken, claims, me, isAuthenticated, onSignIn, onLogout }) {
  const [loadError, setLoadError] = useState("");
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cleanup = () => {};
    let isMounted = true;

    async function mountApp() {
      setLoadError("");
      setIsReady(false);
      try {
        const root = document.getElementById("angular-session-root");
        if (!root) {
          return;
        }
        cleanup = await mountAngularSessionApp(root, {
          appToken,
          claims,
          me,
          isAuthenticated,
          onSignIn,
          onLogout,
        });
        if (isMounted) {
          setIsReady(true);
        }
      } catch (err) {
        if (isMounted) {
          setLoadError(err instanceof Error ? err.message : "Failed loading Angular guest app.");
        }
      }
    }

    mountApp();
    return () => {
      isMounted = false;
      cleanup();
    };
  }, [appToken, claims, isAuthenticated, me, onLogout, onSignIn]);

  return (
    <>
      {!isReady && !loadError ? <section className="panel">Loading Angular guest application...</section> : null}
      {loadError ? <section className="panel error">Angular guest app failed: {loadError}</section> : null}
      <div id="angular-session-root" />
    </>
  );
}

function summarizeCatalog(items, priceField) {
  if (!Array.isArray(items) || items.length === 0) {
    return "SKUs: 0, Avg price: -";
  }
  const prices = items
    .map((item) => Number(item?.[priceField]))
    .filter((value) => Number.isFinite(value));
  const avg = prices.length ? prices.reduce((sum, value) => sum + value, 0) / prices.length : 0;
  return `SKUs: ${items.length}, Avg price: £${avg.toFixed(2)}`;
}

function decodeJwtClaims(token) {
  if (!token) {
    return { note: "No app token yet." };
  }
  const parts = token.split(".");
  if (parts.length < 2) {
    return { note: "Invalid JWT format." };
  }
  try {
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    return JSON.parse(json);
  } catch {
    return { note: "Unable to decode JWT claims." };
  }
}

export default App;
