"use client";
import { api, ApiError } from "./client";
import type { Asset, UploadOut } from "./types";

export type Purpose = "post" | "reel" | "story" | "avatar" | "message";

/** Direct to storage with a presigned URL: the API never handles the file. */
export function putFile(url: string, file: File, onProgress?: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status < 300 ? resolve() : reject(new ApiError(xhr.status, "upload_failed", "The upload failed"));
    xhr.onerror = () => reject(new ApiError(0, "upload_failed", "The upload failed. Check your connection."));
    xhr.send(file);
  });
}

export async function uploadAsset(file: File, purpose: Purpose, onProgress?: (f: number) => void): Promise<Asset> {
  const created = await api<UploadOut>("/media/uploads", {
    json: { filename: file.name, content_type: file.type, size: file.size, purpose },
  });
  await putFile(created.upload_url, file, onProgress);
  let asset = await api<Asset>(`/media/${created.asset_id}/complete`, { method: "POST" });
  const deadline = Date.now() + 10 * 60_000;
  while (asset.status === "pending" && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1000));
    asset = await api<Asset>(`/media/${created.asset_id}`);
  }
  if (asset.status !== "ready") throw new ApiError(400, "media_failed", asset.error ?? "That file could not be processed");
  return asset;
}
