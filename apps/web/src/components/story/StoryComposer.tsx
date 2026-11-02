"use client";
import { useEffect, useState } from "react";
import { Button, ErrorNote, Field, Input, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Story } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { FRAME_OPTIONS, StoryFrame } from "./frames";

const selectClass = "min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] sm:text-sm";

export function StoryComposer({ file, onClose, onShared }: { file: File; onClose: () => void; onShared: () => void }) {
  const [preview, setPreview] = useState("");
  const [audience, setAudience] = useState("everyone");
  const [frame, setFrame] = useState("");
  const [kind, setKind] = useState("");
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState(["", ""]);
  const [correct, setCorrect] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const filled = options.map((o) => o.trim()).filter(Boolean);
  const stickerReady = !kind || (question.trim() && filled.length >= 2 && filled.length === options.length);

  const share = async () => {
    setBusy(true);
    setError(null);
    try {
      const asset = await uploadAsset(file, "story");
      await api<Story>("/stories", {
        json: {
          asset_id: asset.id,
          audience,
          frame: frame || null,
          sticker: kind ? { kind, question: question.trim(), options: filled, correct: kind === "quiz" ? correct : null } : null,
        },
      });
      onShared();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="New story">
      <div className="space-y-3">
        <div className="relative mx-auto h-64 w-36 overflow-hidden rounded-lg bg-black" style={{ containerType: "inline-size" }}>
          {preview && (file.type.startsWith("video") ? <video src={preview} muted autoPlay loop playsInline className="h-full w-full object-contain" /> : <img src={preview} alt="" className="h-full w-full object-contain" />)}
          <div className="absolute inset-0 origin-top-left scale-[0.32] [height:312.5%] [width:312.5%]"><StoryFrame frame={frame} /></div>
        </div>
        <Field label="Who can see this">
          <select value={audience} onChange={(e) => setAudience(e.target.value)} className={selectClass}>
            <option value="everyone">Everyone who can see my stories</option>
            <option value="close_friends">Close friends only</option>
          </select>
        </Field>
        <Field label="Festival frame">
          <select value={frame} onChange={(e) => setFrame(e.target.value)} className={selectClass}>
            <option value="">No frame</option>
            {FRAME_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </Field>
        <Field label="Add a poll or quiz">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className={selectClass}>
            <option value="">None</option>
            <option value="poll">Poll</option>
            <option value="quiz">Quiz</option>
          </select>
        </Field>
        {kind && (
          <>
            <Field label="Question"><Input value={question} maxLength={120} onChange={(e) => setQuestion(e.target.value)} /></Field>
            {options.map((value, i) => (
              <div key={i} className="flex items-end gap-2">
                <div className="flex-1">
                  <Field label={`Option ${i + 1}`}>
                    <Input value={value} maxLength={40} onChange={(e) => setOptions(options.map((o, j) => (j === i ? e.target.value : o)))} />
                  </Field>
                </div>
                {kind === "quiz" && (
                  <label className="flex min-h-11 items-center gap-1 text-xs">
                    <input type="radio" name="correct" aria-label={`Option ${i + 1} is correct`} checked={correct === i} onChange={() => setCorrect(i)} className="h-5 w-5 accent-[#C8102E]" /> Correct
                  </label>
                )}
              </div>
            ))}
            {options.length < 4 && <Button variant="ghost" onClick={() => setOptions([...options, ""])}>Add an option</Button>}
          </>
        )}
        <ErrorNote message={error} />
        <Button className="w-full" disabled={!stickerReady} loading={busy} onClick={share}>Share story</Button>
      </div>
    </Modal>
  );
}
