import { useEffect, useMemo, useState } from "react";
import { useAuth } from "react-oidc-context";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { exchangeAwsTokenForAppToken, fetchAuthMe, fetchCatalog, fetchMyCatalog } from "./api";

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
              <section className="panel">
                <h2>Guest Storefront</h2>
                <p className="summaryLine">{publicSummary}</p>
                <div className="cardGrid">
                  {publicCatalog.map((item) => (
                    <article className="catalogCard" key={item.sku}>
                      <p className="sku">{item.sku}</p>
                      <h3>{item.name || "Unnamed item"}</h3>
                      <p>Public unit price: {formatCurrency(item.unit_price_gbp)}</p>
                      <span className="badge badgeGuest">Guest price</span>
                    </article>
                  ))}
                </div>
              </section>
            }
          />
          <Route
            path="/host"
            element={
              <section className="panel">
                <h2>Host Console</h2>
                {!auth.isAuthenticated ? (
                  <div className="hostGate">
                    <p>Hosts can sign in to access personalized prices and protected APIs.</p>
                    <button type="button" onClick={() => auth.signinRedirect()}>
                      Sign in as host
                    </button>
                  </div>
                ) : null}

                {auth.isAuthenticated && !isHostReady ? <p className="status">Preparing host session...</p> : null}

                {isHostReady ? (
                  <>
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
                    <div className="cardGrid">
                      {personalizedCatalog.map((item) => (
                        <article className="catalogCard" key={item.sku}>
                          <p className="sku">{item.sku}</p>
                          <h3>{item.name || "Unnamed item"}</h3>
                          <p>Customer price: {formatCurrency(item.customer_price_gbp)}</p>
                          <span className="badge badgeHost">Host price</span>
                        </article>
                      ))}
                    </div>
                  </>
                ) : null}
              </section>
            }
          />
          <Route
            path="/session"
            element={
              <>
                <section className="panel">
                  <h2>Session Controls</h2>
                  <div className="toggleRow">
                    <button type="button" onClick={() => auth.signinRedirect()} disabled={auth.isAuthenticated}>
                      Sign in
                    </button>
                    <button type="button" onClick={handleLogout} disabled={!auth.isAuthenticated}>
                      Logout
                    </button>
                  </div>
                  <p className="token">{appToken || "No app token yet."}</p>
                </section>

                <section className="panel">
                  <h2>Protected /auth/me Result</h2>
                  <pre>{JSON.stringify(me, null, 2)}</pre>
                </section>

                <section className="panel">
                  <h2>Current App JWT Claims</h2>
                  <pre>{JSON.stringify(appTokenClaims, null, 2)}</pre>
                </section>
              </>
            }
          />
          <Route path="*" element={<Navigate to="/guest" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
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

function formatCurrency(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "-";
  }
  return `£${amount.toFixed(2)}`;
}

export default App;
