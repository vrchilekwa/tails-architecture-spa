let angularRuntimePromise;

function getAngularRuntime() {
  if (!angularRuntimePromise) {
    angularRuntimePromise = Promise.all([
      import(/* @vite-ignore */ "https://esm.sh/@angular/compiler@18.2.13"),
      import(/* @vite-ignore */ "https://esm.sh/@angular/core@18.2.13"),
      import(/* @vite-ignore */ "https://esm.sh/@angular/platform-browser@18.2.13"),
      import(/* @vite-ignore */ "https://esm.sh/@angular/platform-browser-dynamic@18.2.13"),
      import(/* @vite-ignore */ "https://esm.sh/@angular/common@18.2.13"),
      import(/* @vite-ignore */ "https://esm.sh/zone.js@0.14.10"),
    ]);
  }
  return angularRuntimePromise;
}

export async function mountAngularSessionApp(container, props) {
  const [, core, platformBrowser, platformDynamic, ngCommon] = await getAngularRuntime();
  const { Component, NgModule } = core;
  const { BrowserModule } = platformBrowser;
  const { platformBrowserDynamic } = platformDynamic;
  const { CommonModule } = ngCommon;

  const state = {
    appToken: props.appToken || "",
    claims: props.claims || {},
    me: props.me || null,
    isAuthenticated: Boolean(props.isAuthenticated),
    onSignIn: props.onSignIn,
    onLogout: props.onLogout,
  };

  let SessionPanelComponent = class SessionPanelComponent {
    get isAuthenticated() {
      return state.isAuthenticated;
    }

    get prettyClaims() {
      return JSON.stringify(state.claims, null, 2);
    }

    get prettyMe() {
      return JSON.stringify(state.me, null, 2);
    }

    get tokenText() {
      return state.appToken || "No app token yet.";
    }

    get hostState() {
      return state.isAuthenticated ? "Host signed in" : "Guest mode";
    }

    signIn() {
      if (typeof state.onSignIn === "function") {
        state.onSignIn();
      }
    }

    logout() {
      if (typeof state.onLogout === "function") {
        state.onLogout();
      }
    }
  };

  SessionPanelComponent = Component({
    selector: "session-panel",
    standalone: false,
    template: `
      <section class="panel">
        <h2>Session Controls (Angular Guest App)</h2>
        <p class="status">{{ hostState }}</p>
        <div class="toggleRow">
          <button type="button" (click)="signIn()" [disabled]="isAuthenticated">Sign in</button>
          <button type="button" (click)="logout()" [disabled]="!isAuthenticated">Logout</button>
        </div>
        <p class="token">{{ tokenText }}</p>
      </section>

      <section class="panel">
        <h2>Protected /auth/me Result</h2>
        <pre>{{ prettyMe }}</pre>
      </section>

      <section class="panel">
        <h2>Current App JWT Claims</h2>
        <pre>{{ prettyClaims }}</pre>
      </section>
    `,
  })(SessionPanelComponent);

  let RootComponent = class RootComponent {};
  RootComponent = Component({
    selector: "angular-session-root",
    standalone: false,
    template: "<session-panel></session-panel>",
  })(RootComponent);

  let RootModule = class RootModule {};
  RootModule = NgModule({
    declarations: [RootComponent, SessionPanelComponent],
    imports: [BrowserModule, CommonModule],
    bootstrap: [RootComponent],
  })(RootModule);

  const mountNode = document.createElement("angular-session-root");
  container.innerHTML = "";
  container.appendChild(mountNode);

  const platformRef = platformBrowserDynamic();
  const moduleRef = await platformRef.bootstrapModule(RootModule);

  return () => {
    moduleRef.destroy();
    platformRef.destroy();
    container.innerHTML = "";
  };
}
