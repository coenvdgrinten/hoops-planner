import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTeams, getPlayers, updatePlayerCert, updatePlayerCoachedTeams } from "../api";
import type { Player } from "../types";

// Age category display order (descending: oldest to youngest)
const CATEGORY_ORDER = ["MSE", "VSE", "M16", "X16", "X14", "X10"];

const CERT_OPTIONS = ["NONE", "F", "SENIOR"];

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

  const certMutation = useMutation({
    mutationFn: ({ playerId, cert }: { playerId: number; cert: string }) => updatePlayerCert(playerId, cert),
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

  const handleCertChange = (playerId: number, cert: string) => {
    certMutation.mutate({ playerId, cert });
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
    <div className="member-roster">
      <div className="roster-header">
        <h2>Member Roster</h2>
        <div className="roster-summary">
          <span className="summary-badge">{totalTeams} teams</span>
          <span className="summary-badge">{totalMembers} members</span>
        </div>
      </div>
      <div className="roster-teams-list">
        {sortedTeams.map((team) => {
          const isExpanded = expandedTeams.has(team.id);
          const teamPlayers = playersByTeam.get(team.id) || [];

          return (
            <div key={team.id} className="roster-team-group">
              <button
                className={`roster-team-header ${isExpanded ? "expanded" : ""}`}
                onClick={() => toggleTeam(team.id)}
              >
                <span className="team-chevron">{isExpanded ? "▾" : "▸"}</span>
                <span className="team-age-badge">{team.age_category}</span>
                <span className="team-name">{team.name}</span>
                <span className="team-member-count">{teamPlayers.length}</span>
              </button>
              {isExpanded && (
                <div className="roster-members-list">
                  {teamPlayers.length === 0 ? (
                    <div className="no-members">No members</div>
                  ) : (
                    teamPlayers.map((player) => (
                      <div key={player.id} className="roster-member-row">
                        <div className="roster-member-avatar">
                          {player.full_name
                            .split(" ")
                            .map((n) => n[0])
                            .join("")
                            .slice(0, 2)
                            .toUpperCase()}
                        </div>
                        <div className="roster-member-info">
                          <span className="roster-member-name">
                            {player.full_name}
                            {(player.is_coach || (player.coached_teams && player.coached_teams.length > 0)) && (
                              <span className="coach-badge">Coach</span>
                            )}
                          </span>
                        </div>
                        <div className="coached-teams-editor">
                          <span className="coached-label">Coaches</span>
                          {editingCoachedTeams === player.id ? (
                            <div className="coached-teams-edit">
                              <div className="coached-teams-checkboxes">
                                {sortedTeams.map((t) => (
                                  <label key={t.id} className="coached-team-checkbox">
                                    <input
                                      type="checkbox"
                                      checked={tempCoachedTeams.includes(t.id)}
                                      onChange={() => toggleTeamInCoached(t.id)}
                                    />
                                    {t.name}
                                  </label>
                                ))}
                              </div>
                              <div className="coached-teams-actions">
                                <button className="btn-save" onClick={() => saveCoachedTeams(player.id)}>Save</button>
                                <button className="btn-cancel" onClick={cancelEditCoachedTeams}>Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button
                              className="coached-teams-display"
                              onClick={() => startEditCoachedTeams(player.id, player.coached_teams || [])}
                            >
                              {(player.coached_teams || []).length === 0
                                ? "None"
                                : (player.coached_teams || []).map((id) => getTeamName(id)).join(", ")}
                            </button>
                          )}
                        </div>
                        <div className="cert-editor">
                          <span className="cert-label">Cert</span>
                          <select
                            className={`cert-select ${getCertClass(player.referee_certification)}`}
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
                      </div>
                    ))
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
