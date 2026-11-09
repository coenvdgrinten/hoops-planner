import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createReservation, updateReservation, deleteReservation } from "../api";
import type { GymReservation } from "../types";
import styles from "./GameEditModal.module.css";

interface Props {
  reservation?: GymReservation;
  seasonId: number;
  defaultDate?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function ReservationModal({
  reservation,
  seasonId,
  defaultDate,
  onClose,
  onSuccess,
}: Props) {
  const queryClient = useQueryClient();
  const isCreateMode = !reservation;

  const [date, setDate] = useState(reservation?.date || defaultDate || "");
  // The API returns "HH:MM:SS"; <input type="time"> prefers "HH:MM".
  const [startTime, setStartTime] = useState(reservation?.start_time?.slice(0, 5) || "09:00");
  const [endTime, setEndTime] = useState(reservation?.end_time?.slice(0, 5) || "17:00");
  const [note, setNote] = useState(reservation?.note || "");
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["reservations"] });
    queryClient.invalidateQueries({ queryKey: ["gym-coverage"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createReservation({
        season: seasonId,
        date,
        start_time: startTime,
        end_time: endTime,
        note,
      }),
    onSuccess: () => {
      invalidate();
      onSuccess();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Create failed"),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateReservation(reservation!.id, {
        date,
        start_time: startTime,
        end_time: endTime,
        note,
      }),
    onSuccess: () => {
      invalidate();
      onSuccess();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Update failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteReservation(reservation!.id),
    onSuccess: () => {
      invalidate();
      onSuccess();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Delete failed"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!date) {
      setError("Please select a date.");
      return;
    }
    if (endTime <= startTime) {
      setError("End time must be after start time.");
      return;
    }
    if (isCreateMode) {
      createMutation.mutate();
    } else {
      updateMutation.mutate();
    }
  };

  const pending =
    createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{isCreateMode ? "Add Reservation" : "Edit Reservation"}</h3>
        <form onSubmit={handleSubmit}>
          <div className={styles["form-row"]}>
            <label htmlFor="res-date">Date</label>
            <input
              id="res-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>
          <div className={styles["form-row"]}>
            <label htmlFor="res-start">Start time</label>
            <input
              id="res-start"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
          </div>
          <div className={styles["form-row"]}>
            <label htmlFor="res-end">End time</label>
            <input
              id="res-end"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              required
            />
          </div>
          <div className={styles["form-row"]}>
            <label htmlFor="res-note">Note (optional)</label>
            <input
              id="res-note"
              type="text"
              value={note}
              placeholder="e.g. Full day booking"
              maxLength={200}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          {error && <p className="error">{error}</p>}
          {showDeleteConfirm && !isCreateMode && (
            <div className={styles["delete-confirm"]}>
              <p>Delete this reservation?</p>
              <div className={styles["form-actions"]}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={pending}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className={styles["btn-delete"]}
                  onClick={() => deleteMutation.mutate()}
                  disabled={pending}
                >
                  Delete
                </button>
              </div>
            </div>
          )}
          <div className={styles["form-actions"]}>
            {!isCreateMode && (
              <button
                type="button"
                className={styles["btn-delete"]}
                style={{ marginRight: "auto" }}
                onClick={() => setShowDeleteConfirm(true)}
                disabled={pending}
              >
                Delete
              </button>
            )}
            <button type="button" className="btn-secondary" onClick={onClose} disabled={pending}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={pending}>
              {isCreateMode ? "Add" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
