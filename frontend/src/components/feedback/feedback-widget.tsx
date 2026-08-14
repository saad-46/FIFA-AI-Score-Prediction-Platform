"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { MessageSquare, Star, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { feedbackApi } from "@/lib/api/feedback";
import { getApiErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/**
 * Anonymous feedback — no account, nothing required.
 *
 * A quiet footer link rather than a popup or an interstitial: it should be
 * findable when someone has something to say and invisible otherwise. Rating,
 * comment and email are all optional; the only rule is that a submission
 * carries a rating or a comment, which the backend enforces too.
 */
export function FeedbackWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[11px] uppercase tracking-wider",
          "text-fg-muted transition-colors hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        )}
      >
        <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
        Help us improve
      </button>
      <FeedbackDialog open={open} onOpenChange={setOpen} />
    </>
  );
}

function FeedbackDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();

  const [rating, setRating] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = rating !== null || comment.trim().length > 0;

  function reset() {
    setRating(null);
    setHovered(null);
    setComment("");
    setEmail("");
    setError(null);
    setDone(false);
    setSubmitting(false);
  }

  async function handleSubmit() {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await feedbackApi.submit({
        rating,
        comment: comment.trim() || null,
        email: email.trim() || null,
        page: pathname ?? null,
      });
      setDone(true);
      // Leave the confirmation up briefly so it registers, then close.
      setTimeout(() => {
        onOpenChange(false);
        setTimeout(reset, 200);
      }, 1400);
    } catch (err) {
      setError(getApiErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setTimeout(reset, 200);
      }}
    >
      <DialogContent className="max-w-md border-border/60 bg-surface/85 backdrop-blur-xl">
        {done ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <motion.span
              initial={reduceMotion ? false : { scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/15 text-primary"
            >
              <Check className="h-5 w-5" aria-hidden="true" />
            </motion.span>
            <p className="pt-1 text-sm font-semibold text-foreground">Thanks — that&apos;s recorded.</p>
            <p className="text-xs text-fg-muted">We read everything that comes through.</p>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="text-lg">How was your experience?</DialogTitle>
              <DialogDescription>
                Everything here is optional, and no account is needed.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-5">
              <fieldset className="space-y-2">
                <legend className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  Rating <span className="normal-case tracking-normal">(optional)</span>
                </legend>
                <div
                  className="flex items-center gap-1"
                  onMouseLeave={() => setHovered(null)}
                >
                  {[1, 2, 3, 4, 5].map((value) => {
                    const active = (hovered ?? rating ?? 0) >= value;
                    return (
                      <button
                        key={value}
                        type="button"
                        aria-label={`${value} of 5 stars`}
                        aria-pressed={rating === value}
                        onMouseEnter={() => setHovered(value)}
                        onFocus={() => setHovered(value)}
                        onBlur={() => setHovered(null)}
                        // Tapping the active star clears it, so a rating can be
                        // undone without reloading.
                        onClick={() => setRating(rating === value ? null : value)}
                        className="rounded p-0.5 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <Star
                          className={cn(
                            "h-6 w-6 transition-colors",
                            active ? "fill-primary text-primary" : "text-fg-muted/50"
                          )}
                          aria-hidden="true"
                        />
                      </button>
                    );
                  })}
                  {rating !== null && (
                    <span className="pl-2 font-mono text-[11px] text-fg-muted">{rating}/5</span>
                  )}
                </div>
              </fieldset>

              <div className="space-y-1.5">
                <Label htmlFor="feedback-comment" className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  Comment <span className="normal-case tracking-normal">(optional)</span>
                </Label>
                <textarea
                  id="feedback-comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  maxLength={2000}
                  rows={4}
                  placeholder="Tell us what you think..."
                  className={cn(
                    "w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground",
                    "placeholder:text-fg-muted/70",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  )}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="feedback-email" className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  Email <span className="normal-case tracking-normal">(optional)</span>
                </Label>
                <Input
                  id="feedback-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Only if you'd like a reply"
                  autoComplete="email"
                />
                <p className="text-[11px] text-fg-muted">
                  Used only to reply to you. Leave it blank to stay anonymous.
                </p>
              </div>

              {error && (
                <p role="alert" className="text-xs text-loss">
                  {error}
                </p>
              )}

              <div className="flex items-center justify-end gap-2 pt-1">
                <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSubmit} disabled={!canSubmit || submitting}>
                  {submitting ? "Sending..." : "Send feedback"}
                </Button>
              </div>
              {!canSubmit && (
                <p className="text-right text-[11px] text-fg-muted">
                  Add a rating or a comment to send.
                </p>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
