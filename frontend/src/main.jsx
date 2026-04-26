import React from "react";
import ReactDOM from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import App from "./App";
import "./styles.css";

const cognitoAuthConfig = {
  authority: import.meta.env.VITE_AWS_COGNITO_AUTHORITY,
  client_id: import.meta.env.VITE_AWS_USER_POOL_CLIENT_ID,
  redirect_uri: import.meta.env.VITE_AWS_REDIRECT_URI || window.location.origin,
  response_type: "code",
  scope: import.meta.env.VITE_AWS_OIDC_SCOPE || "openid email profile",
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider {...cognitoAuthConfig}>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
