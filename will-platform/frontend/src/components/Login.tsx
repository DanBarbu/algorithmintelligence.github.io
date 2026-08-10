import { useState, FormEvent } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../i18n/config";

interface Props {
  onSuccess: () => void;
}

const DEMO_USER = "will_admin";
const DEMO_PASS = "Will@Sprint0!";

export default function Login({ onSuccess }: Props): JSX.Element {
  const { t } = useTranslation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  function handleSubmit(e: FormEvent): void {
    e.preventDefault();
    if (username === DEMO_USER && password === DEMO_PASS) {
      onSuccess();
    } else {
      setError(true);
    }
  }

  function toggleLang(): void {
    i18n.changeLanguage(i18n.language === "en" ? "ro" : "en");
  }

  return (
    <div style={styles.outer}>
      <div style={styles.card}>
        <button onClick={toggleLang} style={styles.langBtn} type="button">
          {t("lang.toggle")}
        </button>
        <h1 style={styles.title}>{t("login.title")}</h1>
        <p style={styles.subtitle}>{t("login.subtitle")}</p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            {t("login.username")}
            <input
              style={styles.input}
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(false); }}
              autoComplete="username"
            />
          </label>
          <label style={styles.label}>
            {t("login.password")}
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(false); }}
              autoComplete="current-password"
            />
          </label>
          {error && <p style={styles.error}>{t("login.error")}</p>}
          <button type="submit" style={styles.submit}>{t("login.submit")}</button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  outer: {
    display: "flex", alignItems: "center", justifyContent: "center",
    width: "100%", height: "100%", background: "#0d1117",
  },
  card: {
    background: "#161b22", borderRadius: 8, padding: "2.5rem",
    width: 360, position: "relative", boxShadow: "0 4px 24px #0008",
  },
  langBtn: {
    position: "absolute", top: 12, right: 12,
    background: "#21262d", color: "#58a6ff", border: "1px solid #30363d",
    borderRadius: 4, padding: "4px 10px", cursor: "pointer", fontSize: 13,
  },
  title: { color: "#e6edf3", fontSize: 22, marginBottom: 4 },
  subtitle: { color: "#8b949e", fontSize: 13, marginBottom: 24 },
  form: { display: "flex", flexDirection: "column", gap: 16 },
  label: { display: "flex", flexDirection: "column", gap: 6, color: "#e6edf3", fontSize: 14 },
  input: {
    background: "#0d1117", border: "1px solid #30363d", borderRadius: 6,
    padding: "8px 12px", color: "#e6edf3", fontSize: 14,
  },
  error: { color: "#f85149", fontSize: 13 },
  submit: {
    background: "#238636", color: "#fff", border: "none",
    borderRadius: 6, padding: "10px", fontSize: 15, cursor: "pointer",
  },
};
