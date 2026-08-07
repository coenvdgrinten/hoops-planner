import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTeams,
  getPlayers,
  updatePlayerCert,
  updatePlayerCoachedTeams,
  createTeam,
  updateTeam,
  deleteTeam,
  createPlayer,
  updatePlayer,
  deletePlayer,
} from "../api";
import type { Player, Team, AgeCategory } from "../types";
import styles from "./MemberView.module.css";

// Age category display order (descending: oldest to youngest)
const CATEGORY_ORDER: AgeCategory[] = [
  "MSE",
  "M22",
  "M18",
  "M16",
  "VSE",
  "X16",
  "X14",
  "X12",
  "X10",
];

const CERT_OPTIONS = ["NONE", "T1", "T2", "T3", "T4", "T5", "T6", "F", "SENIOR"];

export function MemberView() {
  const queryClient = useQueryClient();
  const { data: teams = [], isLoading: teamsLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: getTeams,
  });

  const { data: allPlayers = [], isLoading: playersLoading } = useQuery({
    queryKey: ["players"],
    queryFn: getPlayers,
  });

  // Show all players (including coaches) so coached teams can be edited/removed
  const players = allPlayers;
  const [expandedTeams, setExpandedTeams] = useState<Set<number>>(new Set());
  const [editingCoachedTeams, setEditingCoachedTeams] = useState<number | null>(null);
  const [tempCoachedTeams, setTempCoachedTeams] = useState<number[]>([]);

  // Team management state
  const [addingTeam, setAddingTeam] = useState(false);
  const [editingTeamId, setEditingTeamId] = useState<number | null>(null);
  const [newTeam, setNewTeam] = useState<{ name: string; age_category: AgeCategory }>({
    name: "",
    age_category: "X14",
  });
  const [editTeam, setEditTeam] = useState<{ name: string; age_category: AgeCategory }>({
    name: "",
    age_category: "X14",
  });

  // Player management state
  const [addingPlayerForTeam, setAddingPlayerForTeam] = useState<number | null>(null);
  const [editingPlayerId, setEditingPlayerId] = useState<number | null>(null);
  const [newPlayer, setNewPlayer] = useState<{
    first_name: string;
    last_name: string;
    is_coach: boolean;
    referee_certification: string;
  }>({ first_name: "", last_name: "", is_coach: false, referee_certification: "NONE" });
  const [editPlayer, setEditPlayer] = useState<{
    first_name: string;
    last_name: string;
    is_coach: boolean;
    referee_certification: string;
    is_exempt: boolean;
  }>({ first_name: "", last_name: "", is_coach: false, referee_certification: "NONE", is_exempt: false });

  const certMutation = useMutation({
    mutationFn: ({ playerId, cert }: { playerId: number; cert: string }) =>
      updatePlayerCert(playerId, cert),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });

  const exemptMutation = useMutation({
    mutationFn: ({ playerId, isExempt }: { playerId: number; isExempt: boolean }) =>
      updatePlayer(playerId, { is_exempt: isExempt }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });

  const coachedTeamsMutation = useMutation({
    mutationFn: ({ playerId, teamIds }: { playerId: number; teamIds: number[] }) =>
      updatePlayerCoachedTeams(playerId, teamIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });

  const teamMutation = useMutation<Team | void, Error,
    | { kind: "create" }
    | { kind: "update"; id: number }
    | { kind: "delete"; id: number }>({
    mutationFn: (op) => {
      if (op.kind === "create") return createTeam(newTeam);
      if (op.kind === "update") return updateTeam(op.id, editTeam);
      return deleteTeam(op.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      setAddingTeam(false);
      setEditingTeamId(null);
      setNewTeam({ name: "", age_category: "X14" });
    },
  });

  const playerMutation = useMutation<Player | void, Error,
    | { kind: "create"; teamId: number }
    | { kind: "update"; id: number }
    | { kind: "delete"; id: number }>({
    mutationFn: (op) => {
      if (op.kind === "create") return createPlayer({ ...newPlayer, team_id: op.teamId });
      if (op.kind === "update") return updatePlayer(op.id, editPlayer);
      return deletePlayer(op.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      setAddingPlayerForTeam(null);
      setEditingPlayerId(null);
      setNewPlayer({ first_name: "", last_name: "", is_coach: false, referee_certification: "NONE", is_exempt: false });
    },
  });

  const handleCertChange = (playerId: number, cert: string) => {
    certMutation.mutate({ playerId, cert });
  };

  const handleExemptChange = (playerId: number, isExempt: boolean) => {
    exemptMutation.mutate({ playerId, isExempt });
  };

  const startEditCoachedTeams = (playerId: number, currentTeams: number[]) => {
    setEditingCoachedTeams(playerId);
    setTempCoachedTeams([...currentTeams]);
  };

  const saveCoachedTeams = (playerId: number) => {
    coachedTeamsMutation.mutate({ playerId, teamIds: tempCoachedTeams });
    setEditingCoachedTeams(null);
  };

  const cancelEditCoachedTeams = () => {
    setEditingCoachedTeams(null);
  };

  const toggleTeamInCoached = (teamId: number) => {
    setTempCoachedTeams((prev) =>
      prev.includes(teamId) ? prev.filter((id) => id !== teamId) : [...prev, teamId]
    );
  };

  const getTeamName = (teamId: number): string => {
    return teams.find((t) => t.id === teamId)?.name ?? "";
  };

  const getCertClass = (cert: string) => {
    if (cert === "NONE") return "cert-none";
    if (cert === "F") return "cert-low";
    if (cert === "SENIOR") return "cert-high";
    return "";
  };

  // Group players by team
  const playersByTeam = new Map<number, Player[]>();
  for (const player of players) {
    const existing = playersByTeam.get(player.team.id) || [];
    existing.push(player);
    playersByTeam.set(player.team.id, existing);
  }

  // Sort teams by age category then name
  const sortedTeams = [...teams].sort((a, b) => {
    const aIdx = CATEGORY_ORDER.indexOf(a.age_category);
    const bIdx = CATEGORY_ORDER.indexOf(b.age_category);
    if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
    if (aIdx !== -1) return -1;
    if (bIdx !== -1) return 1;
    return a.name.localeCompare(b.name);
  });

  const toggleTeam = (teamId: number) => {
    setExpandedTeams((prev) => {
      const next = new Set(prev);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  };

  const isLoading = teamsLoading || playersLoading;
  if (isLoading) return <p>Loading teams...</p>;

  const totalMembers = players.length;
  const totalTeams = teams.length;

  return (
    <div className={styles["member-roster"]}>
      <div className={styles["roster-header"]}>
        <h2>Member Roster</h2>
        <div className={styles["roster-summary"]}>
          <span className={styles["summary-badge"]}>{totalTeams} teams</span>
          <span className={styles["summary-badge"]}>{totalMembers} members</span>
        </div>
        <button
          className={styles["add-team-btn"]}
          onClick={() => {
            setAddingTeam((v) => !v);
            setEditingTeamId(null);
          }}
        >
          + Add Team
        </button>
      </div>

      {addingTeam && (
        <div className={styles["team-edit-form"]}>
          <input
            type="text"
            placeholder="Team name (e.g. Vido X14-1)"
            value={newTeam.name}
            onChange={(e) => setNewTeam((t) => ({ ...t, name: e.target.value }))}
          />
          <select
            value={newTeam.age_category}
            onChange={(e) =>
              setNewTeam((t) => ({ ...t, age_category: e.target.value as AgeCategory }))
            }
          >
            {CATEGORY_ORDER.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button
            className={styles["btn-save"]}
            disabled={!newTeam.name.trim() || teamMutation.isPending}
            onClick={() => teamMutation.mutate({ kind: "create" })}
          >
            Save
          </button>
          <button className={styles["btn-cancel"]} onClick={() => setAddingTeam(false)}>
            Cancel
          </button>
        </div>
      )}

      <div className={styles["roster-teams-list"]}>
        {sortedTeams.map((team) => {
          const isExpanded = expandedTeams.has(team.id);
          const teamPlayers = playersByTeam.get(team.id) || [];
          const isEditingTeam = editingTeamId === team.id;

          return (
            <div data-testid={`team-group-${team.id}`} key={team.id} className={styles["roster-team-group"]}>
              <div className={styles["team-row"]}>
                <button
                  data-testid={`team-header-${team.id}`}
                  className={`${styles["roster-team-header"]} ${isExpanded ? styles.expanded : ""}`}
                  onClick={() => toggleTeam(team.id)}
                >
                  <span className={styles["team-chevron"]}>{isExpanded ? "▾" : "▸"}</span>
                  <span className={styles["team-age-badge"]}>{team.age_category}</span>
                  <span className={styles["team-name"]}>{team.name}</span>
                  <span className={styles["team-member-count"]}>{teamPlayers.length}</span>
                </button>
                <div className={styles["team-actions"]}>
                  <button
                    data-testid={`team-edit-${team.id}`}
                    className={styles["icon-edit"]}
                    title="Edit team"
                    onClick={() => {
                      setEditingTeamId(team.id);
                      setEditTeam({ name: team.name, age_category: team.age_category });
                      setAddingTeam(false);
                    }}
                  >
                    ✎
                  </button>
                  <button
                    data-testid={`team-delete-${team.id}`}
                    className={styles["icon-delete"]}
                    title="Delete team"
                    onClick={() => {
                      if (window.confirm(`Delete team "${team.name}"? This also removes its players.`)) {
                        teamMutation.mutate({ kind: "delete", id: team.id });
                      }
                    }}
                  >
                    🗑
                  </button>
                </div>
              </div>

              {isEditingTeam && (
                <div className={styles["team-edit-form"]}>
                  <input
                    type="text"
                    value={editTeam.name}
                    onChange={(e) => setEditTeam((t) => ({ ...t, name: e.target.value }))}
                  />
                  <select
                    value={editTeam.age_category}
                    onChange={(e) =>
                      setEditTeam((t) => ({ ...t, age_category: e.target.value as AgeCategory }))
                    }
                  >
                    {CATEGORY_ORDER.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <button
                    className={styles["btn-save"]}
                    disabled={!editTeam.name.trim() || teamMutation.isPending}
                    onClick={() => teamMutation.mutate({ kind: "update", id: team.id })}
                  >
                    Save
                  </button>
                  <button
                    className={styles["btn-cancel"]}
                    onClick={() => setEditingTeamId(null)}
                  >
                    Cancel
                  </button>
                </div>
              )}

              {isExpanded && (
                <div className={styles["roster-members-list"]}>
                  <button
                    data-testid={`add-player-${team.id}`}
                    className={styles["add-player-btn"]}
                    onClick={() => {
                      setAddingPlayerForTeam(team.id);
                      setEditingPlayerId(null);
                      setNewPlayer({
                        first_name: "",
                        last_name: "",
                        is_coach: false,
                        referee_certification: "NONE",
                        is_exempt: false,
                      });
                    }}
                  >
                    + Add player to {team.name}
                  </button>

                  {addingPlayerForTeam === team.id && (
                    <div className={styles["player-edit-form"]}>
                      <input
                        type="text"
                        placeholder="First name"
                        value={newPlayer.first_name}
                        onChange={(e) =>
                          setNewPlayer((p) => ({ ...p, first_name: e.target.value }))
                        }
                      />
                      <input
                        type="text"
                        placeholder="Last name"
                        value={newPlayer.last_name}
                        onChange={(e) =>
                          setNewPlayer((p) => ({ ...p, last_name: e.target.value }))
                        }
                      />
                      <label className={styles["inline-check"]}>
                        <input
                          type="checkbox"
                          checked={newPlayer.is_coach}
                          onChange={(e) =>
                            setNewPlayer((p) => ({ ...p, is_coach: e.target.checked }))
                          }
                        />
                        Coach
                      </label>
                      <label className={styles["inline-check"]}>
                        <input
                          type="checkbox"
                          checked={newPlayer.is_exempt ?? false}
                          onChange={(e) =>
                            setNewPlayer((p) => ({ ...p, is_exempt: e.target.checked }))
                          }
                        />
                        Exempt
                      </label>
                      <select
                        value={newPlayer.referee_certification}
                        onChange={(e) =>
                          setNewPlayer((p) => ({
                            ...p,
                            referee_certification: e.target.value,
                          }))
                        }
                      >
                        {CERT_OPTIONS.map((c) => (
                          <option key={c} value={c}>
                            {c === "NONE" ? "None" : c}
                          </option>
                        ))}
                      </select>
                      <button
                        className={styles["btn-save"]}
                        disabled={
                          !newPlayer.first_name.trim() ||
                          !newPlayer.last_name.trim() ||
                          playerMutation.isPending
                        }
                        onClick={() => playerMutation.mutate({ kind: "create", teamId: team.id })}
                      >
                        Save
                      </button>
                      <button
                        className={styles["btn-cancel"]}
                        onClick={() => setAddingPlayerForTeam(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {teamPlayers.length === 0 ? (
                    <div className={styles["no-members"]}>No members</div>
                  ) : (
                    teamPlayers.map((player) => {
                      const isEditingPlayer = editingPlayerId === player.id;
                      return (
                        <div key={player.id}>
                          {isEditingPlayer ? (
                            <div className={styles["player-edit-form"]}>
                              <input
                                type="text"
                                placeholder="First name"
                                value={editPlayer.first_name}
                                onChange={(e) =>
                                  setEditPlayer((p) => ({ ...p, first_name: e.target.value }))
                                }
                              />
                              <input
                                type="text"
                                placeholder="Last name"
                                value={editPlayer.last_name}
                                onChange={(e) =>
                                  setEditPlayer((p) => ({ ...p, last_name: e.target.value }))
                                }
                              />
                              <label className={styles["inline-check"]}>
                                <input
                                  type="checkbox"
                                  checked={editPlayer.is_coach}
                                  onChange={(e) =>
                                    setEditPlayer((p) => ({ ...p, is_coach: e.target.checked }))
                                  }
                                />
                                Coach
                              </label>
                              <label className={styles["inline-check"]}>
                                <input
                                  type="checkbox"
                                  checked={editPlayer.is_exempt ?? false}
                                  onChange={(e) =>
                                    setEditPlayer((p) => ({ ...p, is_exempt: e.target.checked }))
                                  }
                                />
                                Exempt
                              </label>
                              <select
                                value={editPlayer.referee_certification}
                                onChange={(e) =>
                                  setEditPlayer((p) => ({
                                    ...p,
                                    referee_certification: e.target.value,
                                  }))
                                }
                              >
                                {CERT_OPTIONS.map((c) => (
                                  <option key={c} value={c}>
                                    {c === "NONE" ? "None" : c}
                                  </option>
                                ))}
                              </select>
                              <button
                                className={styles["btn-save"]}
                                disabled={
                                  !editPlayer.first_name.trim() ||
                                  !editPlayer.last_name.trim() ||
                                  playerMutation.isPending
                                }
                                onClick={() => playerMutation.mutate({ kind: "update", id: player.id })}
                              >
                                Save
                              </button>
                              <button
                                className={styles["btn-cancel"]}
                                onClick={() => setEditingPlayerId(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div data-testid={`player-row-${player.id}`} className={styles["roster-member-row"]}>
                              <div className={styles["roster-member-avatar"]}>
                                {player.full_name
                                  .split(" ")
                                  .map((n) => n[0])
                                  .join("")
                                  .slice(0, 2)
                                  .toUpperCase()}
                              </div>
                              <div className={styles["roster-member-info"]}>
                                <span className={styles["roster-member-name"]}>
                                  {player.full_name}
                                  {(player.is_coach ||
                                    (player.coached_teams && player.coached_teams.length > 0)) && (
                                    <span className={styles["coach-badge"]}>Coach</span>
                                  )}
                                </span>
                              </div>
                              <div className={styles["coached-teams-editor"]}>
                                <span className={styles["coached-label"]}>Coaches</span>
                                {editingCoachedTeams === player.id ? (
                                  <div className={styles["coached-teams-edit"]}>
                                    <div className={styles["coached-teams-checkboxes"]}>
                                      {sortedTeams.map((t) => (
                                        <label key={t.id} className={styles["coached-team-checkbox"]}>
                                          <input
                                            type="checkbox"
                                            checked={tempCoachedTeams.includes(t.id)}
                                            onChange={() => toggleTeamInCoached(t.id)}
                                          />
                                          {t.name}
                                        </label>
                                      ))}
                                    </div>
                                    <div className={styles["coached-teams-actions"]}>
                                      <button
                                        className={styles["btn-save"]}
                                        onClick={() => saveCoachedTeams(player.id)}
                                      >
                                        Save
                                      </button>
                                      <button
                                        className={styles["btn-cancel"]}
                                        onClick={cancelEditCoachedTeams}
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <button
                                    className={styles["coached-teams-display"]}
                                    onClick={() =>
                                      startEditCoachedTeams(player.id, player.coached_teams || [])
                                    }
                                  >
                                    {(player.coached_teams || []).length === 0
                                      ? "None"
                                      : (player.coached_teams || []).map((id) => getTeamName(id)).join(", ")}
                                  </button>
                                )}
                              </div>
                              <div className={styles["cert-editor"]}>
                                <span className={styles["cert-label"]}>Cert</span>
                                <select
                                  data-testid={`cert-select-${player.id}`}
                                  className={`${styles["cert-select"]} ${getCertClass(player.referee_certification)}`}
                                  value={player.referee_certification}
                                  onChange={(e) => handleCertChange(player.id, e.target.value)}
                                >
                                  {CERT_OPTIONS.map((cert) => (
                                    <option key={cert} value={cert}>
                                      {cert === "NONE" ? "None" : cert}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <div className={styles["exempt-editor"]}>
                                <span className={styles["exempt-label"]}>Exempt</span>
                                <input
                                  type="checkbox"
                                  checked={player.is_exempt ?? false}
                                  onChange={(e) => handleExemptChange(player.id, e.target.checked)}
                                  className={styles["exempt-checkbox"]}
                                />
                              </div>
                              <div className={styles["member-actions"]}>
                                <button
                                  data-testid={`player-edit-${player.id}`}
                                  className={styles["icon-edit"]}
                                  title="Edit player"
                                  onClick={() => {
                                    setEditingPlayerId(player.id);
                                    setAddingPlayerForTeam(null);
                                    setEditPlayer({
                                      first_name: player.first_name,
                                      last_name: player.last_name,
                                      is_coach: player.is_coach,
                                      referee_certification: player.referee_certification,
                                      is_exempt: player.is_exempt ?? false,
                                    });
                                  }}
                                >
                                  ✎
                                </button>
                                <button
                                  data-testid={`player-delete-${player.id}`}
                                  className={styles["icon-delete"]}
                                  title="Delete player"
                                  onClick={() => {
                                    if (window.confirm(`Delete ${player.full_name}?`)) {
                                      playerMutation.mutate({ kind: "delete", id: player.id });
                                    }
                                  }}
                                >
                                  🗑
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
