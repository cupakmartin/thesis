import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const korenovyPrvek = document.getElementById("korenovy-prvek");
if (!korenovyPrvek) {
  throw new Error("Kořenový prvek rozhraní nebyl v dokumentu nalezen.");
}

createRoot(korenovyPrvek).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
