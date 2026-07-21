import { useState, useEffect } from "react";
import { login, register, setAuth, passwordResetRequest, passwordResetConfirm, verifyEmailRequest, verifyEmailConfirm } from "../api";
import type { AuthResponse } from "../api";
import styles from "./Login.module.css";

interface Props {
  onLogin: () => void;
}

type Mode = "login" | "register" | "password_reset" | "password_reset_confirm" | "verify_email";

export function Login({ onLogin }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetUid, setResetUid] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
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
    setSuccess(null);
    setLoading(true);

    try {
      switch (mode) {
        case "login": {
          const result: AuthResponse = await login(username, password);
          setAuth(result.token, result.user);
          onLogin();
          break;
        }
        case "register": {
          const result: AuthResponse = await register(username, password, email);
          setAuth(result.token, result.user);
          onLogin();
          break;
        }
        case "password_reset": {
          const data = await passwordResetRequest(email);
          // In dev, the backend returns the token directly
          if (data.token && data.uid) {
            setResetToken(data.token);
            setResetUid(String(data.uid));
            setSuccess("Reset link sent. Enter new password below.");
            setMode("password_reset_confirm");
          } else {
            setSuccess("If the email exists, a reset link has been sent.");
          }
          break;
        }
        case "password_reset_confirm": {
          await passwordResetConfirm(resetToken, parseInt(resetUid), password);
          setSuccess("Password has been reset. You can now log in.");
          setMode("login");
          break;
        }
        case "verify_email": {
          const data = await verifyEmailRequest();
          if (data.token) {
            await verifyEmailConfirm(data.token);
            setSuccess("Email verified successfully.");
          } else {
            setSuccess("Verification email sent.");
          }
          break;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setMode("login");
    setError(null);
    setSuccess(null);
    setUsername("");
    setPassword("");
    setEmail("");
    setResetToken("");
    setResetUid("");
  };

  return (
    <div className={styles["auth-container"]}>
      <div className={styles["auth-card"]}>
        <div className={styles["auth-header"]}>
          <img src="/logo.png" alt="BC Vido" className={styles["auth-logo"]} />
          <h2>Hoops Planner</h2>
          <p className={styles["auth-subtitle"]}>BC Vido — Task Planning</p>
        </div>

        <form onSubmit={handleSubmit} className={styles["auth-form"]}>
          <h3>
            {mode === "login" && "Sign In"}
            {mode === "register" && "Create Account"}
            {mode === "password_reset" && "Reset Password"}
            {mode === "password_reset_confirm" && "Set New Password"}
            {mode === "verify_email" && "Verify Email"}
          </h3>

          {error && <div className={styles["auth-error"]}>{error}</div>}
          {success && <div className={styles["auth-success"]}>{success}</div>}

          {(mode === "login" || mode === "register") && (
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
          )}

          {mode === "register" && (
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

          {(mode === "login" || mode === "register") && (
            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                autoComplete={mode === "register" ? "new-password" : "current-password"}
              />
            </div>
          )}

          {mode === "password_reset" && (
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                required
                autoComplete="email"
              />
            </div>
          )}

          {mode === "password_reset_confirm" && (
            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter new password"
                required
                autoComplete="new-password"
              />
            </div>
          )}

          <button type="submit" disabled={loading} className={styles["auth-submit"]}>
            {loading
              ? "Processing..."
              : mode === "login"
                ? "Sign In"
                : mode === "register"
                  ? "Create Account"
                  : mode === "password_reset"
                    ? "Send Reset Link"
                    : mode === "password_reset_confirm"
                      ? "Reset Password"
                      : "Verify Email"}
          </button>

          <p className={styles["auth-toggle"]}>
            {mode === "login" && (
              <>
                <button type="button" onClick={() => { setMode("password_reset"); setError(null); setSuccess(null); }}>
                  Forgot password?
                </button>
                <br />
                Don't have an account?{" "}
                <button type="button" onClick={() => { setMode("register"); setError(null); setSuccess(null); }}>
                  Register
                </button>
              </>
            )}
            {mode === "register" && (
              <>
                Already have an account?{" "}
                <button type="button" onClick={() => { setMode("login"); setError(null); setSuccess(null); }}>
                  Sign in
                </button>
              </>
            )}
            {(mode === "password_reset" || mode === "password_reset_confirm") && (
              <>
                <button type="button" onClick={resetForm}>Back to Sign In</button>
              </>
            )}
            {mode === "verify_email" && (
              <>
                <button type="button" onClick={resetForm}>Back to Sign In</button>
              </>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}
