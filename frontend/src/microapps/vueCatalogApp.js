let vueRuntimePromise;

function getVueRuntime() {
  if (!vueRuntimePromise) {
    vueRuntimePromise = import(
      /* @vite-ignore */ "https://esm.sh/vue@3.5.13"
    );
  }
  return vueRuntimePromise;
}

export async function mountVueCatalogApp(container, props) {
  const { createApp, h } = await getVueRuntime();

  const app = createApp({
    render() {
      const items = Array.isArray(props.items) ? props.items : [];
      const isHost = props.mode === "host";
      const summary = props.summary || "No summary";

      return h("section", { class: "panel" }, [
        h("h2", isHost ? "Host Console (Vue Guest App)" : "Guest Storefront (Vue Guest App)"),
        h("p", { class: "summaryLine" }, summary),
        h(
          "div",
          { class: "cardGrid" },
          items.map((item) =>
            h("article", { class: "catalogCard", key: item.sku }, [
              h("p", { class: "sku" }, String(item.sku || "-")),
              h("h3", item.name || "Unnamed item"),
              h(
                "p",
                isHost
                  ? `Customer price: ${formatCurrency(item.customer_price_gbp)}`
                  : `Public unit price: ${formatCurrency(item.unit_price_gbp)}`,
              ),
              h(
                "span",
                { class: isHost ? "badge badgeHost" : "badge badgeGuest" },
                isHost ? "Host price" : "Guest price",
              ),
            ]),
          ),
        ),
      ]);
    },
  });

  app.mount(container);
  return () => app.unmount();
}

function formatCurrency(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "-";
  }
  return `£${amount.toFixed(2)}`;
}
