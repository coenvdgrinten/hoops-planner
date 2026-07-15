import { useState, useEffect } from "react";
import { login, register, setAuth } from "../api";
import type { AuthResponse } from "../api";
import styles from "./Login.module.css";

interface Props {
  onLogin: () => void;
}

export function Login({ onLogin }: Props) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // Optional: could close modal if we had one
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let result: AuthResponse;
      if (isRegister) {
        result = await register(username, password, email);
      } else {
        result = await login(username, password);
      }
      setAuth(result.token, result.user);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles["auth-container"]}>
      <div className={styles["auth-card"]}>
        <div className={styles["auth-header"]}>
          <img src="/logo.png" alt="BC Vido" className={styles["auth-logo"]} />
          <h2>Sixth Man</h2>
          <p className={styles["auth-subtitle"]}>BC Vido — Task Planning</p>
        </div>

        <form onSubmit={handleSubmit} className={styles["auth-form"]}>
          <h3>{isRegister ? "Create Account" : "Sign In"}</h3>

          {error && <div className={styles["auth-error"]}>{error}</div>}

          <div className="form-group">
            <label>Username or Email</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username or email"
              required
              autoComplete="username"
            />
          </div>

          {isRegister && (
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                autoComplete="email"
              />
            </div>
          )}

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete={isRegister ? "new-password" : "current-password"}
            />
          </div>

          <button type="submit" disabled={loading} className={styles["auth-submit"]}>
            {loading
              ? isRegister
                ? "Creating account..."
                : "Signing in..."
              : isRegister
                ? "Create Account"
                : "Sign In"}
          </button>

          <p className={styles["auth-toggle"]}>
            {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister);
                setError(null);
              }}
            >
              {isRegister ? "Sign in" : "Register"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
