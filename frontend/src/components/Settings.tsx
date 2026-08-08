import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToastContext } from "./ToastContext";
import {
  getTeamSettings,
  updateTeamSettings,
  getPendingUsers,
  approveUser,
  rejectUser,
} from "../api";
import type { Team } from "../types";
import styles from "./Settings.module.css";

export function Settings() {
  const queryClient = useQueryClient();
  const { addToast } = useToastContext();

  const { data: teams = [], isLoading, error } = useQuery({
    queryKey: ["team-settings"],
    queryFn: getTeamSettings,
  });

  const { data: pendingUsers = [] } = useQuery({
    queryKey: ["pending-users"],
    queryFn: getPendingUsers,
  });

  const teamMutation = useMutation({
    mutationFn: ({
      teamId,
      data,
    }: {
      teamId: number;
      data: Partial<Team>;
    }) => updateTeamSettings(teamId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-settings"] });
    },
    onError: (err) => {
      addToast(err instanceof Error ? err.message : "Failed to update team settings", "error");
    },
  });

  const approveMutation = useMutation({
    mutationFn: approveUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-users"] });
    },
    onError: (err) => {
      addToast(err instanceof Error ? err.message : "Failed to approve user", "error");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: rejectUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-users"] });
    },
    onError: (err) => {
      addToast(err instanceof Error ? err.message : "Failed to reject user", "error");
    },
  });

  if (isLoading) return <p>Loading settings...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;

  const handleChange = (
    teamId: number,
    field: keyof Team,
    value: number | boolean,
  ) => {
    teamMutation.mutate({ teamId, data: { [field]: value } });
  };

  const sorted = [...teams].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className={styles.settings}>
      <div className={styles["settings-header"]}>
        <h2>Settings</h2>
        <p className={styles["settings-subtitle"]}>
          Configure how many task slots are created per team. Changes
          apply to games imported or created afterwards.
          Parents Responsible excludes players from Scorer/Timer suggestions.
        </p>
      </div>
      <table className={styles["settings-table"]}>
        <thead>
          <tr>
            <th>Team</th>
            <th>Referees (req.)</th>
            <th>Referees (opt.)</th>
            <th>Scorer</th>
            <th>Timer</th>
            <th>24-sec Operator</th>
            <th title="Applies to Scorer and Timer tasks only">Parents Responsible</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => (
            <tr key={t.id}>
              <td className={styles["settings-category"]}>
                <span className={styles["settings-team-name"]}>{t.name}</span>
                <span className={styles["settings-age-category"]}>{t.age_category}</span>
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={4}
                  value={t.required_referees}
                  onChange={(e) =>
                    handleChange(t.id, "required_referees", Math.max(0, Number(e.target.value)))
                  }
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={4}
                  value={t.optional_referees}
                  onChange={(e) =>
                    handleChange(t.id, "optional_referees", Math.max(0, Number(e.target.value)))
                  }
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={t.require_scorer}
                  onChange={(e) => handleChange(t.id, "require_scorer", e.target.checked)}
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={t.require_timer}
                  onChange={(e) => handleChange(t.id, "require_timer", e.target.checked)}
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={t.requires_24_second_operator}
                  onChange={(e) => handleChange(t.id, "requires_24_second_operator", e.target.checked)}
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={t.parent_responsible}
                  onChange={(e) => handleChange(t.id, "parent_responsible", e.target.checked)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pending Users */}
      <div className={styles["settings-section"]}>
        <h3>Pending Users</h3>
        <p className={styles["settings-subtitle"]}>
          Users who have registered and verified their email, awaiting your approval.
        </p>
        {pendingUsers.length === 0 ? (
          <p className={styles["empty-msg"]}>No pending users</p>
        ) : (
          <table className={styles["settings-table"]}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Registered</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingUsers.map((u) => (
                <tr key={u.id}>
                  <td className={styles["settings-member-name"]}>{u.username}</td>
                  <td>{u.email}</td>
                  <td>{new Date(u.date_joined).toLocaleDateString()}</td>
                  <td className={styles["pending-actions"]}>
                    <button
                      className={styles["btn-approve"]}
                      onClick={() => approveMutation.mutate(u.id)}
                      disabled={approveMutation.isPending}
                    >
                      Approve
                    </button>
                    <button
                      className={styles["btn-reject"]}
                      onClick={() => {
                        if (confirm(`Reject user "${u.username}"?`)) {
                          rejectMutation.mutate(u.id);
                        }
                      }}
                      disabled={rejectMutation.isPending}
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
