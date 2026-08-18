import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

/* Ant Design base reset */
import "antd/dist/reset.css";

import "./index.css";

/* Must be imported before the app so translations are ready on first render. */
import i18n from "./i18n";

import App from "./App.tsx";

/* Keep the document language in sync for assistive technology and search. */
document.documentElement.lang = i18n.resolvedLanguage ?? "en";
i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
