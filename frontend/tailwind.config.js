export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        podklad: "rgb(var(--barva-podklad) / <alpha-value>)",
        plocha: "rgb(var(--barva-plocha) / <alpha-value>)",
        plocha2: "rgb(var(--barva-plocha-2) / <alpha-value>)",
        plocha3: "rgb(var(--barva-plocha-3) / <alpha-value>)",
        obrys: "rgb(var(--barva-obrys) / <alpha-value>)",
        obrys2: "rgb(var(--barva-obrys-2) / <alpha-value>)",
        text: "rgb(var(--barva-text) / <alpha-value>)",
        textTlumeny: "rgb(var(--barva-text-tlumeny) / <alpha-value>)",
        textSlaby: "rgb(var(--barva-text-slaby) / <alpha-value>)",
        akcent: "rgb(var(--barva-akcent) / <alpha-value>)",
        akcentTlumeny: "rgb(var(--barva-akcent-tlumeny) / <alpha-value>)",
        akcentText: "rgb(var(--barva-akcent-text) / <alpha-value>)",
        vystraha: "rgb(var(--barva-vystraha) / <alpha-value>)",
        vystrahaTlumena: "rgb(var(--barva-vystraha-tlumena) / <alpha-value>)",
        uspech: "rgb(var(--barva-uspech) / <alpha-value>)",
        uspechTlumeny: "rgb(var(--barva-uspech-tlumeny) / <alpha-value>)",
        chyba: "rgb(var(--barva-chyba) / <alpha-value>)",
        chybaTlumena: "rgb(var(--barva-chyba-tlumena) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["system-ui", "Segoe UI", "Arial", "sans-serif"],
        mono: ["Consolas", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: { xs: "0", sm: "0", md: "0", lg: "0", xl: "0" },
      boxShadow: { panel: "none", vyzdvih: "none", sm: "none", DEFAULT: "none" },
      animation: {
        nastup: "none",
        rozsvit: "none",
        pulz: "none",
        posuv: "none",
      },
    },
  },
  plugins: [],
};
