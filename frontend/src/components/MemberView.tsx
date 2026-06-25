import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTeams, getPlayers, updatePlayerCert } from "../api";
import type { Player } from "../types";

// Age category display order
const CATEGORY_ORDER = ["X10", "X14", "X16", "M16", "VSE", "MSE", "X14"];

const CERT_OPTIONS = ["NONE", "T1", "T2", "T3", "T4", "T5", "T6"];

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

  const players = allPlayers.filter((pl) => !pl.is_coach);
  const [expandedTeams, setExpandedTeams] = useState<Set<number>>(new Set());

  const certMutation = useMutation({
    mutationFn: ({ playerId, cert }: { playerId: number; cert: string }) => updatePlayerCert(playerId, cert),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });

  const handleCertChange = (playerId: number, cert: string) => {
    certMutation.mutate({ playerId, cert });
  };

  const getCertClass = (cert: string) => {
    if (cert === "NONE") return "cert-none";
    if (["T1", "T2"].includes(cert)) return "cert-low";
    if (["T3", "T4"].includes(cert)) return "cert-mid";
    if (["T5", "T6"].includes(cert)) return "cert-high";
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
                          <span className="roster-member-name">{player.full_name}</span>
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
