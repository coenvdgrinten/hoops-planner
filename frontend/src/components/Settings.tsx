import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTeamSettings,
  updateTeamSettings,
} from "../api";
import type { Team } from "../types";
import styles from "./Settings.module.css";

export function Settings() {
  const queryClient = useQueryClient();
  const { data: teams = [], isLoading, error } = useQuery({
    queryKey: ["team-settings"],
    queryFn: getTeamSettings,
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
    </div>
  );
}
