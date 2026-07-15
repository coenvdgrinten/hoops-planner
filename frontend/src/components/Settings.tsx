import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAgeCategorySettings,
  updateAgeCategorySettings,
} from "../api";
import type { AgeCategorySettings } from "../types";
import styles from "./Settings.module.css";

// Age category display order (descending: oldest to youngest)
const CATEGORY_ORDER = ["MSE", "VSE", "M16", "X16", "X14", "X12", "X10"];

export function Settings() {
  const queryClient = useQueryClient();
  const { data: settings = [], isLoading, error } = useQuery({
    queryKey: ["age-category-settings"],
    queryFn: getAgeCategorySettings,
  });

  const mutation = useMutation({
    mutationFn: ({
      ageCategory,
      data,
    }: {
      ageCategory: string;
      data: Partial<AgeCategorySettings>;
    }) => updateAgeCategorySettings(ageCategory, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["age-category-settings"] });
    },
  });

  if (isLoading) return <p>Loading settings...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;

  const sorted = [...settings].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a.age_category);
    const bi = CATEGORY_ORDER.indexOf(b.age_category);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  return (
    <div className={styles.settings}>
      <div className={styles["settings-header"]}>
        <h2>Settings</h2>
        <p className={styles["settings-subtitle"]}>
          Configure how many task slots are created per age category. Changes
          apply to games imported or created afterwards.
        </p>
      </div>
      <table className={styles["settings-table"]}>
        <thead>
          <tr>
            <th>Age Category</th>
            <th>Referees (req.)</th>
            <th>Referees (opt.)</th>
            <th>Scorer</th>
            <th>Timer</th>
            <th>24-sec Operator</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.age_category}>
              <td className={styles["settings-category"]}>{s.age_category}</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={4}
                  value={s.required_referees}
                  onChange={(e) =>
                    mutation.mutate({
                      ageCategory: s.age_category,
                      data: {
                        required_referees: Math.max(
                          0,
                          Number(e.target.value),
                        ),
                      },
                    })
                  }
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={4}
                  value={s.optional_referees}
                  onChange={(e) =>
                    mutation.mutate({
                      ageCategory: s.age_category,
                      data: {
                        optional_referees: Math.max(
                          0,
                          Number(e.target.value),
                        ),
                      },
                    })
                  }
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={s.scorer}
                  onChange={(e) =>
                    mutation.mutate({
                      ageCategory: s.age_category,
                      data: { scorer: e.target.checked },
                    })
                  }
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={s.timer}
                  onChange={(e) =>
                    mutation.mutate({
                      ageCategory: s.age_category,
                      data: { timer: e.target.checked },
                    })
                  }
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={s.requires_24_second_operator}
                  onChange={(e) =>
                    mutation.mutate({
                      ageCategory: s.age_category,
                      data: { requires_24_second_operator: e.target.checked },
                    })
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
