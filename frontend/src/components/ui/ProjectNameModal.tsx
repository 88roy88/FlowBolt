import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Dialog, DialogContent, DialogClose, DialogTitle } from "./dialog";
import { Button } from "./button";
import { Input } from "./input";

interface ProjectNameModalProps {
  open: boolean;
  onSubmit: (name: string) => Promise<void>;
  onCancel: () => void;
}

export function ProjectNameModal({
  open,
  onSubmit,
  onCancel,
}: ProjectNameModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName(t("sidebar.untitledProjectDefault"));
      setError(null);
      setSubmitting(false);
    }
  }, [open, t]);

  // Slight delay before auto-focus feels more natural
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 150);
    return () => clearTimeout(timer);
  }, [open]);

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit(trimmed);
    } catch {
      setError(t("sidebar.createProjectError"));
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (submitting) return;
    onCancel();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleCancel()}>
      <DialogContent
        className="w-[340px] animate-card-in"
        onKeyDown={(e) => {
          if (e.key === "Escape") handleCancel();
        }}
      >
        <DialogTitle>{t("sidebar.nameYourProject")}</DialogTitle>
        <DialogClose onClose={handleCancel} />
        <div className="mt-4 space-y-3">
          <Input
            ref={inputRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSubmit();
            }}
            placeholder={t("sidebar.untitledProjectDefault")}
            disabled={submitting}
          />
          {error && (
            <p className="text-[12px] text-destructive">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button
              variant="ghost"
              onClick={handleCancel}
              disabled={submitting}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!name.trim() || submitting}
            >
              {submitting ? `${t("common.loading")}…` : t("common.create")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
