export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "sans-serif"] },
      colors: {
        surface: "#F9F9F8",
        border: "#E5E5E3",
        accent: "#1D4ED8",
        danger: "#DC2626",
        text: { primary: "#1A1A1A", secondary: "#737373" },
      },
      boxShadow: {
        panel: "0 16px 40px rgba(15, 23, 42, 0.08)",
      },
    },
  },
}
